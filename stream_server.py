"""
MJPEG HTTP Streaming Server & Cloudflare Tunnel untuk Kamera ALPR Smart Parking Gate FT Untirta.
Menyiarkan live feed webcam langsung ke Web Dashboard secara real-time via Localhost & HTTPS Cloudflare Tunnel.
"""

import os
import re
import sys
import time
import shutil
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import cv2

class StreamHub:
    """Hub penyimpanan frame terbaru dalam bentuk JPEG bytes untuk disiarkan ke client."""
    def __init__(self):
        self.lock = threading.Lock()
        self.latest_jpeg = None
        self.last_update = 0.0

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


GLOBAL_HUB = StreamHub()


class MJPEGHandler(BaseHTTPRequestHandler):
    """Handler HTTP untuk menyiarkan multipart MJPEG stream dan status."""
    def do_GET(self):
        # Header CORS agar dashboard Netlify / localhost bisa mengakses tanpa terblokir
        if self.path == '/status' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","camera":"active"}')
            return

        # Default: Video Feed Stream
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.end_headers()

        try:
            last_sent = 0.0
            while True:
                jpeg = GLOBAL_HUB.get_jpeg()
                if jpeg and GLOBAL_HUB.last_update != last_sent:
                    last_sent = GLOBAL_HUB.last_update
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
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
    """Server streaming HTTP MJPEG background & Cloudflare Tunnel HTTPS otomatis."""
    def __init__(self, host='0.0.0.0', port=5050):
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.tunnel_process = None
        self.tunnel_url = None

    def start(self):
        try:
            self.server = HTTPServer((self.host, self.port), MJPEGHandler)
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
                        print("  Salin URL di atas ke tombol [URL Kamera] pada Web Dashboard!")
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
