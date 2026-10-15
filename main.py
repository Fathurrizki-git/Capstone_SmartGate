"""
Main ALPR Pipeline — Raspberry Pi 4
Konsep: RPi menangkap gambar → kirim ke Plate Recognizer API → terima hasil.

Usage:
    # Mode gambar tunggal
    python main.py --image foto_mobil.jpg

    # Mode kamera DEPLOY (Otomatis berdasarkan interval)
    python main.py --camera

    # Mode kamera TEST (Manual tekan Spasi)
    python main.py --camera --manual

    # Mode folder (batch processing)
    python main.py --folder images/
"""

import argparse
import os
import time
import cv2
import numpy as np
from datetime import datetime
import threading

import config
from plate_recognizer import PlateRecognizerAPI, draw_results

# Inisialisasi Logger sesuai pilihan di config.py
provider = getattr(config, 'DATABASE_PROVIDER', 'supabase').lower()
if provider == 'supabase':
    from supabase_logger import SupabaseLogger
else:
    from firebase_logger import FirebaseLogger


class ALPRPipeline:
    """
    Pipeline ALPR berbasis Cloud API.
    RPi hanya menangkap gambar → Plate Recognizer API melakukan recognition.
    """

    def __init__(self):
        print("=" * 50)
        print("  ALPR System — Raspberry Pi 4")
        print("  Mode: Cloud API (Plate Recognizer)")
        print(f"  Database: {provider.upper()}")
        print("=" * 50)

        # Inisialisasi API client & Database
        self.api = PlateRecognizerAPI()
        if provider == 'supabase':
            self.db = SupabaseLogger()
        else:
            self.db = FirebaseLogger()

        # Cek kuota API
        usage = self.api.check_usage()
        if usage["remaining"] >= 0:
            print(f"[INFO] API Quota: {usage['remaining']}/{usage['max_calls']} remaining")
        else:
            print("[WARN] Tidak bisa cek kuota API")

        # Buat folder output
        if config.SAVE_RESULTS:
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        self.last_api_call = 0        # Timestamp API call terakhir
        self.is_api_processing = False # Status apakah thread API sedang jalan
        self.current_results = []      # Cache hasil terakhir untuk ditampilkan
        
        print("[OK] System ready!\n")

    def process_image(self, image: np.ndarray) -> list:
        """
        Proses satu gambar: kirim ke API → terima hasil.
        (Berjalan sinkron, blocking)
        """
        start_time = time.time()

        # Kirim ke Plate Recognizer API
        api_result = self.api.recognize(image)
        self.last_api_call = time.time()

        if not api_result["success"]:
            print(f"  [ERROR] {api_result['error']}")
            return []

        results = api_result["results"]
        elapsed = time.time() - start_time

        print(f"[INFO] Processed in {elapsed:.2f}s — "
              f"Found {len(results)} plate(s)")

        return results

    def _async_recognize(self, image: np.ndarray):
        """
        Jalankan API di thread terpisah (background) agar kamera tidak lag.
        """
        try:
            results = self.process_image(image)
            if results:
                self.current_results = results
                # Print hasil ke console dan log ke Firebase
                for r in results:
                    plate_text = r.get('plate_text', '')
                    confidence = r.get('confidence', 0.0)
                    region = r.get('region', {}).get('code', '')
                    
                    print(f"  >> PLAT: {plate_text} (conf: {confidence:.0%})")
                    
                    # Log otomatis ke Firebase
                    self.db.log_vehicle(plate_text, confidence, region)
        finally:
            # Pastikan flag direset setelah selesai atau error
            self.is_api_processing = False

    def run_on_image(self, image_path: str):
        """Proses satu file gambar."""
        print(f"\n[INPUT] {image_path}")

        image = cv2.imread(image_path)
        if image is None:
            print(f"[ERROR] Gagal membaca gambar: {image_path}")
            return

        results = self.process_image(image)
        self._display_results(results)

        # Log hasil ke Supabase / Database
        for r in results:
            plate_text = r.get('plate_text', '')
            confidence = r.get('confidence', 0.0)
            region = r.get('region', {}).get('code', '')
            self.db.log_vehicle(plate_text, confidence, region)

        # Gambar anotasi
        annotated = draw_results(image, results)

        # Simpan hasil
        if config.SAVE_RESULTS:
            self._save_results(image_path, annotated, results)

        # Preview
        if config.SHOW_PREVIEW:
            cv2.imshow("ALPR Result", annotated)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    def run_on_folder(self, folder_path: str):
        """Batch processing untuk folder gambar."""
        extensions = (".jpg", ".jpeg", ".png", ".bmp")
        files = [
            f for f in os.listdir(folder_path)
            if f.lower().endswith(extensions)
        ]

        if not files:
            print(f"[ERROR] Tidak ada gambar di: {folder_path}")
            return

        print(f"\n[INFO] Processing {len(files)} gambar dari: {folder_path}")
        all_results = []

        for i, fname in enumerate(sorted(files), 1):
            print(f"\n--- [{i}/{len(files)}] ---")
            fpath = os.path.join(folder_path, fname)

            image = cv2.imread(fpath)
            if image is None:
                continue

            results = self.process_image(image)
            self._display_results(results)

            for r in results:
                plate_text = r.get('plate_text', '')
                confidence = r.get('confidence', 0.0)
                region = r.get('region', {}).get('code', '')
                self.db.log_vehicle(plate_text, confidence, region)
                r["source_file"] = fname
            all_results.extend(results)

            # Simpan gambar dengan anotasi
            if config.SAVE_RESULTS:
                annotated = draw_results(image, results)
                self._save_results(fpath, annotated, results)

        # Ringkasan
        print(f"\n{'=' * 50}")
        print(f"  RINGKASAN: {len(all_results)} plat dari {len(files)} gambar")
        print(f"{'=' * 50}")
        for r in all_results:
            print(f"  ✓ {r['plate_text']:<15} "
                  f"(conf: {r['confidence']:.0%}) "
                  f"— {r.get('source_file', '')}")

    def run_camera(self, is_manual=False):
        """Mode real-time dari kamera dengan Multithreading."""
        print("\n[INFO] Starting camera...")

        if config.USE_PICAMERA:
            cap = self._init_picamera()
        else:
            cap = cv2.VideoCapture(config.CAMERA_INDEX)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        if not cap.isOpened():
            print("[ERROR] Gagal membuka kamera!")
            return

        print("[OK] Camera started. Tekan 'q' untuk keluar.")
        if is_manual:
            print("[INFO] Mode TEST Aktif: Tekan 'SPASI' untuk mengirim gambar ke API.")
        else:
            print(f"[INFO] Mode DEPLOY Aktif: Auto-capture tiap {config.MIN_CAPTURE_INTERVAL}s")

        frame_count = 0
        fps_start = time.time()
        fps = 0.0
        
        trigger_capture = False

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                time_since_last = time.time() - self.last_api_call

                # Tentukan apakah harus kirim gambar ke API
                if is_manual:
                    # Mode Test: Hanya kirim jika tombol SPASI ditekan dan API sedang tidak sibuk
                    should_process = trigger_capture and not self.is_api_processing
                    trigger_capture = False  # Reset flag setelah dipakai
                else:
                    # Mode Deploy: Otomatis berdasarkan interval dan frameskip
                    should_process = (
                        time_since_last >= config.MIN_CAPTURE_INTERVAL and
                        not self.is_api_processing and
                        (frame_count % config.SKIP_FRAMES == 0)
                    )

                if should_process:
                    self.is_api_processing = True
                    threading.Thread(
                        target=self._async_recognize,
                        args=(frame.copy(),),
                        daemon=True
                    ).start()

                # Hitung FPS
                elapsed = time.time() - fps_start
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    frame_count = 0
                    fps_start = time.time()

                # Gambar anotasi & UI
                annotated = draw_results(frame, self.current_results)

                # Tampilkan FPS
                cv2.putText(
                    annotated, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
                )

                # Tampilkan Status Bar
                if self.is_api_processing:
                    status_text = "API Processing..."
                    status_color = (0, 0, 255) # Merah = Sibuk
                elif is_manual:
                    status_text = "Test Mode: Tekan SPASI"
                    status_color = (255, 200, 0) # Biru muda (Cyan) = Menunggu input user
                elif time_since_last < config.MIN_CAPTURE_INTERVAL:
                    cooldown_left = max(0, config.MIN_CAPTURE_INTERVAL - time_since_last)
                    status_text = f"Cooldown: {cooldown_left:.1f}s"
                    status_color = (0, 200, 255) # Kuning = Cooldown interval
                else:
                    status_text = "API Ready (Auto)"
                    status_color = (0, 255, 0) # Hijau = Siap auto-capture

                cv2.putText(
                    annotated, status_text, (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2
                )

                if config.SHOW_PREVIEW:
                    cv2.imshow("ALPR Camera", annotated)
                    key = cv2.waitKey(1) & 0xFF
                    
                    if key == ord("q"):
                        break
                    elif key == 32: # Tombol Spacebar
                        trigger_capture = True

        except KeyboardInterrupt:
            print("\n[INFO] Dihentikan oleh user.")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            print("[OK] Camera released.")

    def _init_picamera(self):
        """Inisialisasi PiCamera2 (untuk Raspberry Pi Camera Module)."""
        try:
            from picamera2 import Picamera2
            picam = Picamera2()
            picam_config = picam.create_preview_configuration(
                main={"size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT),
                       "format": "RGB888"}
            )
            picam.configure(picam_config)
            picam.start()
            return picam
        except ImportError:
            print("[WARN] picamera2 tidak terinstall. Menggunakan USB camera.")
            return cv2.VideoCapture(config.CAMERA_INDEX)

    def _display_results(self, results: list):
        """Tampilkan hasil ke console."""
        if not results:
            print("  [--] Tidak ada plat terdeteksi")
            return

        for r in results:
            region = r.get("region", {}).get("code", "?")
            print(f"  [PLATE] {r['plate_text']:<15} "
                  f"| Confidence: {r['confidence']:.0%} "
                  f"| Region: {region}")

            # Tampilkan kandidat alternatif
            candidates = r.get("candidates", [])
            if len(candidates) > 1:
                alts = ", ".join([f"{c['plate']}({c['score']:.0%})" for c in candidates[1:3]])
                print(f"          Alternatives: {alts}")

    def _save_results(self, source_path: str, annotated: np.ndarray, results: list):
        """Simpan gambar anotasi dan log hasil."""
        basename = os.path.splitext(os.path.basename(source_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Simpan gambar anotasi
        out_path = os.path.join(config.OUTPUT_DIR, f"{basename}_{timestamp}.jpg")
        cv2.imwrite(out_path, annotated)

        # Log ke file CSV
        log_path = os.path.join(config.OUTPUT_DIR, "results.csv")
        file_exists = os.path.exists(log_path)

        with open(log_path, "a", encoding="utf-8") as f:
            if not file_exists:
                f.write("timestamp,source,plate_text,confidence,region\n")
            for r in results:
                region = r.get("region", {}).get("code", "")
                f.write(
                    f"{timestamp},{source_path},{r['plate_text']},"
                    f"{r['confidence']:.3f},{region}\n"
                )


def main():
    parser = argparse.ArgumentParser(description="ALPR System — Plate Recognizer API")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", type=str, help="Path ke gambar")
    group.add_argument("--camera", action="store_true", help="Mode kamera real-time")
    group.add_argument("--folder", type=str, help="Path ke folder gambar")
    
    # Tambahan opsi mode manual
    parser.add_argument("--manual", action="store_true", help="Mode Test: tekan SPASI untuk capture (hanya untuk --camera)")
    
    args = parser.parse_args()

    pipeline = ALPRPipeline()

    if args.image:
        pipeline.run_on_image(args.image)
    elif args.camera:
        pipeline.run_camera(is_manual=args.manual)
    elif args.folder:
        pipeline.run_on_folder(args.folder)


if __name__ == "__main__":
    main()
