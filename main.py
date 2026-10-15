"""
Sistem Smart Parking Gate FT UNTIRTA (EXIT GATE — GERBANG KELUAR)
Platform: Raspberry Pi 3 Model B+

Sistem Verifikasi Ganda (Dual-Factor Authentication):
- KEDUA PARAMETER (PLAT NOMOR DAN KARTU RFID) HARUS COCOK dengan database!
- Jika plat cocok dan kartu RFID cocok milik kendaraan yang sama -> Palang KELUAR terbuka.
- Jika plat terdaftar tetapi kartu salah/berbeda -> Palang TETAP TERTUTUP (Alarm bunyi).
- Jika kendaraan belum terdaftar (Tamu) -> Petugas verifikasi manual lalu tekan Push Button.

Komponen Terintegrasi:
  1. Raspberry Pi 3 Model B+ (Pusat Kontrol)
  2. Webcam USB (Perekam Plat Keluar)
  3. RFID USB 13.56 MHz (Pembaca Kartu Civitas)
  4. Buzzer Flash AD16-22SM 12V (GPIO22 - Pin 15)
  5. Motor Servo Palang (GPIO18 - Pin 12)
  6. LCD I2C 20x4 (SDA: GPIO2 / Pin 3, SCL: GPIO3 / Pin 5)
  7. Push Button Manual (GPIO27 - Pin 13)
  8. Sensor Infrared E18-D80NK (GPIO17 - Pin 11)
"""

import os
import sys
import time
import argparse
import cv2
import numpy as np

import config
from hardware import HardwareManager
from plate_recognizer import PlateRecognizerAPI, draw_results
from supabase_logger import SupabaseLogger


class SmartParkingExitGate:
    def __init__(self):
        print("=" * 65)
        print("  SMART PARKING GATE FT UNTIRTA — GERBANG KELUAR (EXIT ONLY)")
        print("  Sistem Verifikasi: DUAL AUTH (PLAT DAN RFID HARUS MATCH!)")
        print("  Bypass Tamu: Push Button Manual Petugas")
        print("  Database: SUPABASE (Arah: OUT / Keluar)")
        print("=" * 65)

        # 1. Inisialisasi Perangkat Keras
        self.hw = HardwareManager()

        # 2. Inisialisasi Database Logger & AI API
        self.db = SupabaseLogger()
        self.api = PlateRecognizerAPI()

        # 3. Inisialisasi Kamera USB
        self.cap = None
        self._init_camera()

        if config.SAVE_RESULTS:
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        # Standby gerbang keluar
        self.hw.lcd.display(
            " GERBANG KELUAR FT  ",
            "  UNTIRTA CILEGON   ",
            "SISTEM DUAL-AUTH OK ",
            "PALANG TERTUTUP (0*)"
        )
        self.hw.close_gate()
        self.hw.buzzer_beep(0.15, 1)
        time.sleep(1.5)
        self.hw.lcd.display_standby()

        print("[OK] Gerbang keluar siap beroperasi dengan verifikasi PLAT + RFID!\n")

    def _init_camera(self):
        """Buka koneksi Webcam USB."""
        print(f"[INFO] Membuka Webcam USB index {config.CAMERA_INDEX}...")
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        if not self.cap.isOpened():
            print("[WARN] Webcam USB belum terdeteksi. Silakan periksa kabel USB.")
        else:
            print("[OK] Webcam USB terhubung dan siap.")

    def capture_frame(self):
        """Ambil 1 frame citra jernih dari webcam USB."""
        if not self.cap or not self.cap.isOpened():
            self._init_camera()
            if not self.cap or not self.cap.isOpened():
                return None

        for _ in range(2):
            self.cap.read()

        ret, frame = self.cap.read()
        if ret and frame is not None:
            return frame
        return None

    def handle_exit_success(self, info: dict):
        """Aksi saat KEDUA PARAMETER (Plat + RFID) COCOK."""
        plate = info.get("plate", "-")
        owner = info.get("owner_name", "Civitas")
        cat = info.get("category", "STUDENT")

        print(f"\n>>> [AKSES KELUAR DITERIMA \u2705] PLAT & RFID COCOK: {owner} ({plate})")

        # 1. Update LCD 20x4
        self.hw.lcd.display(
            "*** AKSES KELUAR ***",
            f"{plate} ({cat[:7]})",
            f"{owner[:20]}",
            "HATI-HATI DI JALAN:)"
        )

        # 2. Bunyikan Buzzer 2x
        self.hw.buzzer_beep(0.12, 2)

        # 3. Buka Palang Gerbang Keluar (90 Derajat)
        self.hw.open_gate()

        # 4. Kirim Data Lengkap ke Supabase (vehicle_logs)
        self.db.log_vehicle(
            plate_text=plate,
            confidence=info.get("confidence", 95.0),
            direction="OUT",
            method="ALPR+RFID",
            custom_info=info
        )

        # 5. Keamanan: Tunggu kendaraan melintas melewati sensor IR
        print(f"  [HOLD] Palang terbuka selama {config.GATE_OPEN_DURATION} detik...")
        time.sleep(config.GATE_OPEN_DURATION)
        self.hw.wait_for_vehicle_clear(timeout=6.0)

        # 6. Tutup Palang Kembali (0 Derajat)
        self.hw.close_gate()
        time.sleep(1.0)
        self.hw.lcd.display_standby()

    def handle_exit_failed(self, info: dict, reason: str = "TIDAK COCOK"):
        """Aksi saat verifikasi keluar gagal (Salah Kartu / Belum Terdaftar)."""
        plate = info.get("plate", "TIDAK DIKENAL")
        rfid = info.get("rfid_uid", "-")
        status = info.get("status", "TIDAK TERDAFTAR")

        if reason == "RFID_MISMATCH":
            print(f"\n>>> [AKSES DITOLAK \u26a0\ufe0f] KARTU TIDAK SESUAI DENGAN PLAT: {plate} vs RFID {rfid}")
            self.hw.lcd.display(
                "! DATA TIDAK COCOK !",
                f"PLAT: {plate[:14]}",
                "KARTU BUKAN MILIKNYA",
                "MOHON LAPOR SATPAM  "
            )
        else:
            print(f"\n>>> [AKSES DITOLAK \u26a0\ufe0f] BELUM TERDAFTAR: {plate}")
            self.hw.lcd.display(
                "** BELUM TERDAFTAR *",
                f"{plate[:20]}",
                "VERIFIKASI GAGAL    ",
                "MOHON LAPOR PETUGAS "
            )

        # Alarm Buzzer Strobo Panjang
        self.hw.buzzer_alert()

        # Palang TETAP TERTUTUP demi keamanan
        self.hw.close_gate()

        # Catat kegagalan ke Supabase
        self.db.log_vehicle(
            plate_text=plate,
            confidence=info.get("confidence", 80.0),
            direction="OUT",
            method="ALPR+RFID",
            custom_info=info
        )

        time.sleep(3.0)
        self.hw.lcd.display_standby()

    def handle_manual_override(self):
        """Buka gerbang keluar manual via Push Button oleh Petugas (Tamu/Belum Terdaftar)."""
        print("\n>>> [MANUAL KELUAR] Tombol ditekan oleh petugas! Membuka gerbang keluar...")
        self.hw.lcd.display(
            "** MANUAL KELUAR ** ",
            "PETUGAS BUKA GERBANG",
            "PALANG DIBUKA       ",
            "SILAKAN MELINTAS... "
        )
        self.hw.buzzer_beep(0.2, 1)
        self.hw.open_gate()

        # Catat log keluar manual ke Supabase
        manual_info = {
            "matched": True,
            "plate": "MANUAL-EXIT",
            "owner_name": "Tamu (Buka Manual)",
            "category": "ACADEMIC COMMUNITY",
            "nim_nip": "-",
            "status": "TERDAFTAR",
            "confidence": 100.0
        }
        self.db.log_vehicle(
            plate_text="MANUAL-EXIT",
            confidence=100.0,
            direction="OUT",
            method="MANUAL",
            custom_info=manual_info
        )

        time.sleep(config.GATE_OPEN_DURATION)
        self.hw.wait_for_vehicle_clear(timeout=6.0)
        self.hw.close_gate()
        time.sleep(1.0)
        self.hw.lcd.display_standby()

    def process_dual_verification(self, initial_rfid: str = None):
        """
        Alur Verifikasi Ganda:
        1. Baca Plat Nomor dari Kamera USB.
        2. Minta Pengendara Tap Kartu RFID (atau gunakan initial_rfid jika tap duluan).
        3. Cocokkan: KEDUA parameter (Plat & RFID) HARUS sesuai dengan data yang sama di database.
        """
        print("\n[PROSES VERIFIKASI GANDA] Kendaraan terdeteksi di gerbang keluar...")
        self.hw.lcd.display(
            "KENDARAAN KELUAR... ",
            "MENGAMBIL FOTO PLAT ",
            "MEMPROSES OCR API...",
            "MOHON TUNGGU...     "
        )
        self.hw.buzzer_beep(0.08, 1)

        # 1. Ambil foto dan deteksi plat via Webcam USB
        frame = self.capture_frame()
        if frame is None:
            print("[ERROR] Gagal membaca webcam!")
            self.hw.lcd.display(
                "  GAGAL AMBIL FOTO  ",
                "PERIKSA WEBCAM USB  ",
                "TEKAN TOMBOL MANUAL ",
                "HUBUNGI PETUGAS     "
            )
            time.sleep(2.0)
            self.hw.lcd.display_standby()
            return

        api_res = self.api.recognize(frame)
        if not api_res.get("success") or not api_res.get("results"):
            print("  [--] Tidak ada plat nomor terdeteksi pada citra.")
            self.hw.lcd.display(
                "PLAT TIDAK TERBACA  ",
                "DEKATKAN KENDARAAN  ",
                "ATAU TEKAN TOMBOL   ",
                "MANUAL OLEH PETUGAS "
            )
            time.sleep(2.5)
            self.hw.lcd.display_standby()
            return

        best = api_res["results"][0]
        plate_text = best.get("plate_text", "")
        conf = best.get("confidence", 0.0)

        if config.SAVE_RESULTS:
            annotated = draw_results(frame, [best])
            fname = os.path.join(config.OUTPUT_DIR, f"exit_{int(time.time())}.jpg")
            cv2.imwrite(fname, annotated)

        print(f"  [ALPR OK] Plat terdeteksi: {plate_text} (conf: {conf:.0%})")

        # 2. Ambil Kartu RFID
        rfid_uid = initial_rfid
        if not rfid_uid:
            # Pengendara belum tap kartu, minta tap sekarang
            timeout = getattr(config, 'RFID_WAIT_TIMEOUT', 12.0)
            start_wait = time.time()
            self.hw.buzzer_beep(0.1, 1)

            print(f"  [MENUNGGU RFID] Menunggu pengendara tap kartu (maks {timeout} detik)...")
            while time.time() - start_wait < timeout:
                remaining = int(timeout - (time.time() - start_wait))
                self.hw.lcd.display(
                    f"PLAT: {plate_text[:14]}",
                    "SILAKAN TAP KARTU...",
                    "RFID CIVITAS ANDA   ",
                    f"WAKTU: {remaining} DETIK"
                )

                # Cek jika tombol manual ditekan petugas selama menunggu
                if self.hw.is_button_pressed():
                    self.handle_manual_override()
                    return

                # Cek jika kartu RFID di-tap
                rfid_uid = self.hw.get_scanned_rfid()
                if rfid_uid:
                    print(f"  [RFID OK] Kartu di-tap: UID {rfid_uid}")
                    self.hw.buzzer_beep(0.08, 1)
                    break

                time.sleep(0.3)

        if not rfid_uid:
            print("  [TIMEOUT] Batas waktu tap RFID habis.")
            self.hw.lcd.display(
                "WAKTU TAP HABIS!    ",
                "KARTU BELUM DI-TAP  ",
                "VERIFIKASI GAGAL    ",
                "TEKAN TOMBOL MANUAL "
            )
            self.hw.buzzer_alert()
            time.sleep(2.5)
            self.hw.lcd.display_standby()
            return

        # 3. VERIFIKASI GANDA (PLAT & RFID HARUS MATCH)
        self.hw.lcd.display(
            "MEMVERIFIKASI DATA..",
            f"PLAT: {plate_text[:14]}",
            f"RFID: {rfid_uid[:14]}",
            "MOHON TUNGGU..."
        )
        time.sleep(0.5)

        auth_result = self.db.verify_dual_auth(plate_text, rfid_uid)
        auth_result["confidence"] = conf

        if auth_result["verified"]:
            # SUKSES: Plat dan RFID cocok pada kendaraan yang sama
            self.handle_exit_success(auth_result)
        else:
            # GAGAL: Mismatch atau belum terdaftar
            self.handle_exit_failed(auth_result, reason=auth_result.get("reason", "UNREGISTERED"))

    def run(self):
        """Loop pemantauan gerbang keluar secara real-time."""
        print("\n" + "=" * 65)
        print("  MEMULAI PEMANTAUAN GERBANG KELUAR (STANDBY DUAL-AUTH)")
        print("  Syarat Buka Otomatis: PLAT NOMOR + KARTU RFID KEDUANYA HARUS COCOK!")
        print("  Bypass Tamu: Tekan Push Button Manual (GPIO 27)")
        print("  Tekan 'Ctrl + C' untuk keluar.")
        print("=" * 65 + "\n")

        try:
            while True:
                # 1. Pemicu Utama: Sensor IR mendeteksi mobil di depan palang keluar
                if self.hw.is_vehicle_detected():
                    self.process_dual_verification()

                # 2. Pemicu Kartu: Jika pengendara men-tap RFID duluan sebelum IR
                scanned_rfid = self.hw.get_scanned_rfid()
                if scanned_rfid:
                    self.process_dual_verification(initial_rfid=scanned_rfid)

                # 3. Pemicu Manual: Petugas menekan Push Button (tamu/belum terdaftar)
                if self.hw.is_button_pressed():
                    self.handle_manual_override()

                time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n[STOP] Menghentikan sistem Gerbang Keluar...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Lepaskan seluruh resource hardware dan kamera."""
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.hw.cleanup()
        print("[OK] Sistem gerbang keluar dinonaktifkan dengan aman.")


def main():
    parser = argparse.ArgumentParser(description="Smart Parking Exit Gate FT UNTIRTA (Dual-Auth)")
    parser.add_argument("--test-cam", action="store_true", help="Uji coba preview webcam USB")
    parser.add_argument("--image", type=str, help="Uji coba deteksi satu file gambar")
    args = parser.parse_args()

    gate = SmartParkingExitGate()

    if args.test_cam:
        print("[TEST] Membuka window preview webcam. Tekan 'q' untuk keluar.")
        while True:
            frame = gate.capture_frame()
            if frame is not None:
                cv2.imshow("Webcam USB Test (Exit Gate RPi 3B+)", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        cv2.destroyAllWindows()
        gate.cleanup()
    elif args.image:
        print(f"[TEST] Menguji gambar: {args.image}")
        img = cv2.imread(args.image)
        if img is not None:
            res = gate.api.recognize(img)
            if res.get("results"):
                plate = res["results"][0]["plate_text"]
                print(f"Hasil: Plat={plate}")
                auth = gate.db.verify_dual_auth(plate, "0001234567")
                print(f"Dual Auth Test (dengan RFID 0001234567): Verified={auth['verified']}, Status={auth['status']}")
            else:
                print("Tidak ada plat terdeteksi.")
        gate.cleanup()
    else:
        gate.run()


if __name__ == "__main__":
    main()
