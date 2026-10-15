"""
MJPEG HTTP Streaming Server & Cloudflare Tunnel untuk Kamera ALPR Smart Parking Gate FT Untirta.
Menyiarkan live feed webcam langsung ke Web Dashboard secara real-time via Localhost & HTTPS Cloudflare Tunnel.
Mendukung concurrent ThreadedHTTPServer, /video_feed (MJPEG), dan /snapshot (Fast JPEG Polling) yang kebal terhadap Cloudflare Proxy Buffering.
"""

import os
import re
import sys
import time
import shutil
import subprocess
import threading
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler
import cv2
import numpy as np


class StreamHub:
    """Hub penyimpanan frame terbaru dalam bentuk JPEG bytes untuk disiarkan ke client."""
    def __init__(self):
        self.lock = threading.Lock()
        self.latest_jpeg = None
        self.last_update = 0.0
        self._placeholder_jpeg = None

    def update_frame(self, frame_bgr):
        if frame_bgr is None:
            return
        try:
            # Encode ke JPEG berkualitas baik namun hemat bandwidth
            ret, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ret:
                with self.lock:
                    self.latest_jpeg = buf.tobytes()
                    self.last_update = time.time()
        except Exception:
            pass

    def get_jpeg(self):
        with self.lock:
            return self.latest_jpeg

    def get_standby_placeholder(self):
        """Buat gambar standby JPEG jika belum ada frame kamera yang masuk."""
        if self._placeholder_jpeg is None:
            h, w = 480, 640
            img = np.zeros((h, w, 3), dtype=np.uint8)
            img[:] = (18, 12, 6)
            cv2.rectangle(img, (20, 20), (w - 20, h - 20), (55, 31, 26), 2)
            cv2.putText(img, "SMART PARKING GATE FT UNTIRTA", (70, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(img, "KAMERA ALPR STANDBY...", (180, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (44, 217, 255), 1)
            ret, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            self._placeholder_jpeg = buf.tobytes() if ret else b''
        return self._placeholder_jpeg


GLOBAL_HUB = StreamHub()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Server HTTP multi-thread agar setiap koneksi /frame /snapshot /status berjalan paralel tanpa saling memblokir."""
    daemon_threads = True
    allow_reuse_address = True


class MJPEGHandler(BaseHTTPRequestHandler):
    """Handler HTTP untuk menyiarkan snapshot JPEG, multipart MJPEG stream, dan status."""

    def do_OPTIONS(self):
        """Preflight CORS response untuk fetch browser dari Netlify HTTPS."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_GET(self):
        # 1. Endpoint Status / Health Check
        if self.path.startswith('/status') or self.path.startswith('/health'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","camera":"active"}')
            return

        # 2. Endpoint Snapshot JPEG (Single Frame) — 100% Kebal terhadap Cloudflare Proxy Buffering
        if self.path.startswith('/snapshot') or self.path.startswith('/frame'):
            jpeg = GLOBAL_HUB.get_jpeg()
            if not jpeg:
                jpeg = GLOBAL_HUB.get_standby_placeholder()
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(jpeg)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(jpeg)
            return

        # 3. Default: Multipart MJPEG Video Feed Stream
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, private, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.end_headers()

        try:
            last_sent = 0.0
            while True:
                jpeg = GLOBAL_HUB.get_jpeg()
                if not jpeg:
                    jpeg = GLOBAL_HUB.get_standby_placeholder()
                if jpeg and GLOBAL_HUB.last_update != last_sent:
                    last_sent = GLOBAL_HUB.last_update
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                    self.wfile.write(f'Content-Length: {len(jpeg)}\r\n\r\n'.encode('utf-8'))
                    self.wfile.write(jpeg)
                    self.wfile.write(b'\r\n')
                time.sleep(0.04)  # ~25 FPS
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            pass

    def log_message(self, format, *args):
        # Meredam logging per request frame agar terminal tetap bersih
        return


class VideoStreamServer:
    """Server streaming HTTP multi-thread & Cloudflare Tunnel HTTPS otomatis."""
    def __init__(self, host='0.0.0.0', port=5050):
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.tunnel_process = None
        self.tunnel_url = None

    def start(self):
        try:
            self.server = ThreadedHTTPServer((self.host, self.port), MJPEGHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            print(f"[OK] Live Camera Web Stream aktif di http://localhost:{self.port}/video_feed")

            # Nyalakan Cloudflare Tunnel otomatis jika tersedia
            self._start_cloudflare_tunnel()
        except Exception as e:
            print(f"[WARN] Gagal menyalakan Web Stream Server pada port {self.port}: {e}")

    def _start_cloudflare_tunnel(self):
        """Mencari cloudflared dan membuat URL HTTPS gratis untuk Netlify."""
        exe_path = None
        if os.path.isfile("cloudflared.exe"):
            exe_path = os.path.abspath("cloudflared.exe")
        elif shutil.which("cloudflared"):
            exe_path = shutil.which("cloudflared")

        if not exe_path:
            return

        def _run_tunnel():
            try:
                cmd = [exe_path, 'tunnel', '--url', f'http://localhost:{self.port}']
                self.tunnel_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
                )

                while self.tunnel_process and self.tunnel_process.poll() is None:
                    line = self.tunnel_process.stdout.readline()
                    if not line:
                        break
                    m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                    if m and not self.tunnel_url:
                        self.tunnel_url = m.group(0)
                        feed_url = f"{self.tunnel_url}/video_feed"
                        print("\n" + "=" * 70)
                        print("  [CLOUDFLARE TUNNEL AKTIF - RESMI HTTPS UNTUK NETLIFY]")
                        print(f"  URL Kamera: {feed_url}")
                        print("  Salin URL di atas ke tombol [URL Cloudflare] pada Web Dashboard!")
                        print("=" * 70 + "\n")
            except Exception as e:
                print(f"[WARN] Cloudflare Tunnel mengalami kendala: {e}")

        t = threading.Thread(target=_run_tunnel, daemon=True)
        t.start()

    def update_frame(self, frame):
        GLOBAL_HUB.update_frame(frame)

    def stop(self):
        if self.tunnel_process:
            try:
                self.tunnel_process.terminate()
            except Exception:
                pass
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
