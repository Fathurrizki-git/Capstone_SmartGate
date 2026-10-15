"""
Sistem Smart Parking Gate FT UNTIRTA (RFID + ALPR)
Platform: Raspberry Pi 3 Model B+

Komponen Terintegrasi:
  1. Raspberry Pi 3 Model B+ (Pusat Kontrol)
  2. Webcam USB (Perekam Plat Kendaraan)
  3. RFID USB 13.56 MHz (Pembaca Kartu Civitas)
  4. Buzzer Flash AD16-22SM 12V (GPIO22 - Pin 15)
  5. Motor Servo Palang (GPIO18 - Pin 12)
  6. LCD I2C 20x4 (SDA: GPIO2 / Pin 3, SCL: GPIO3 / Pin 5)
  7. Push Button Manual (GPIO27 - Pin 13)
  8. Sensor Infrared E18-D80NK (GPIO17 - Pin 11)

Penggunaan:
  python main.py             # Menjalankan sistem gerbang otomatis
  python main.py --test-cam  # Uji coba preview webcam USB
  python main.py --image test.jpg # Uji coba deteksi dari file gambar
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


class SmartParkingGate:
    def __init__(self):
        print("=" * 60)
        print("  SMART PARKING GATE FT UNTIRTA (RFID + ALPR)")
        print("  Hardware: Raspberry Pi 3 Model B+")
        print("  Cloud Database: SUPABASE (PostgreSQL Cloud)")
        print("=" * 60)

        # 1. Inisialisasi Hardware (LCD, Buzzer, Servo, Sensor IR, Button, RFID)
        self.hw = HardwareManager()

        # 2. Inisialisasi Cloud Logger & Plate Recognizer API
        self.db = SupabaseLogger()
        self.api = PlateRecognizerAPI()

        # 3. Inisialisasi Kamera USB
        self.cap = None
        self._init_camera()

        # Pastikan folder output ada jika opsi simpan aktif
        if config.SAVE_RESULTS:
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        # Tampilkan ucapan selamat datang di LCD
        self.hw.lcd.display(
            " SMART PARKING GATE ",
            "    FT UNTIRTA     ",
            "SISTEM SIAP AKTIF...",
            "PALANG TERTUTUP (0*)"
        )
        self.hw.close_gate()
        self.hw.buzzer_beep(0.15, 1)
        time.sleep(1.5)
        self.hw.lcd.display_standby()

        print("[OK] Seluruh sistem siap beroperasi!\n")

    def _init_camera(self):
        """Buka koneksi Webcam USB."""
        print(f"[INFO] Membuka Webcam USB index {config.CAMERA_INDEX}...")
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        if not self.cap.isOpened():
            print("[WARN] Webcam USB belum terdeteksi. Silakan periksa port USB.")
        else:
            print("[OK] Webcam USB terhubung dan siap.")

    def capture_frame(self):
        """Ambil 1 frame citra jernih dari webcam USB."""
        if not self.cap or not self.cap.isOpened():
            self._init_camera()
            if not self.cap or not self.cap.isOpened():
                return None

        # Buang 2 frame awal untuk auto-exposure / white-balance kamera USB
        for _ in range(2):
            self.cap.read()

        ret, frame = self.cap.read()
        if ret and frame is not None:
            return frame
        return None

    def handle_access_granted(self, info: dict, method: str = "ALPR"):
        """Aksi saat akses diterima (Civitas Terdaftar)."""
        plate = info.get("plate", "-")
        owner = info.get("owner_name", "Civitas")
        cat = info.get("category", "STUDENT")
        nim = info.get("nim_nip", "-")

        print(f"\n>>> [AKSES DITERIMA \u2705] {owner} ({cat}) - Plat: {plate} [{method}]")

        # 1. Update LCD 20x4
        self.hw.lcd.display(
            "*** AKSES DITERIMA ***",
            f"{plate} ({cat[:7]})",
            f"{owner[:20]}",
            "SILAKAN MASUK :)"
        )

        # 2. Bunyikan Buzzer 2x pendek (Akses Disetujui)
        self.hw.buzzer_beep(0.12, 2)

        # 3. Buka Palang Gerbang (Servo 90 Derajat)
        self.hw.open_gate()

        # 4. Kirim Data Lengkap ke Supabase (vehicle_logs)
        self.db.log_vehicle(
            plate_text=plate,
            confidence=info.get("confidence", 95.0),
            direction="IN",
            method=method,
            custom_info=info
        )

        # 5. Keamanan: Tunggu kendaraan melintas melewati sensor IR
        print(f"  [HOLD] Palang terbuka selama {config.GATE_OPEN_DURATION} detik...")
        time.sleep(config.GATE_OPEN_DURATION)
        self.hw.wait_for_vehicle_clear(timeout=6.0)

        # 6. Tutup Palang Kembali (Servo 0 Derajat)
        self.hw.close_gate()
        time.sleep(1.0)
        self.hw.lcd.display_standby()

    def handle_access_denied(self, info: dict, method: str = "ALPR"):
        """Aksi saat akses ditolak (Kendaraan Asing / Belum Terdaftar)."""
        plate = info.get("plate", "TIDAK DIKENAL")
        print(f"\n>>> [AKSES DITOLAK \u26a0\ufe0f] Plat: {plate} - Belum Terdaftar [{method}]")

        # 1. Update LCD 20x4
        self.hw.lcd.display(
            "*** AKSES DITOLAK ***",
            f"{plate[:20]}",
            "TIDAK TERDAFTAR",
            "MOHON LAPOR PETUGAS"
        )

        # 2. Bunyikan Alarm Buzzer Flash Panjang
        self.hw.buzzer_alert()

        # 3. Palang TETAP TERTUTUP (Servo 0 Derajat)
        self.hw.close_gate()

        # 4. Catat ke Supabase (Status: TIDAK TERDAFTAR)
        self.db.log_vehicle(
            plate_text=plate,
            confidence=info.get("confidence", 80.0),
            direction="IN",
            method=method,
            custom_info=info
        )

        time.sleep(3.0)
        self.hw.lcd.display_standby()

    def handle_manual_override(self):
        """Buka gerbang secara manual via Push Button oleh petugas."""
        print("\n>>> [MANUAL] Push Button ditekan! Membuka gerbang...")
        self.hw.lcd.display(
            "** MANUAL OVERRIDE **",
            "TOMBOL PETUGAS AKTIF",
            "PALANG GERBANG BUKA ",
            "SILAKAN MELINTAS..."
        )
        self.hw.buzzer_beep(0.2, 1)
        self.hw.open_gate()

        # Catat log manual ke Supabase
        manual_info = {
            "matched": True,
            "plate": "MANUAL-GATE",
            "owner_name": "Petugas Gerbang",
            "category": "ACADEMIC COMMUNITY",
            "nim_nip": "-",
            "status": "TERDAFTAR",
            "confidence": 100.0
        }
        self.db.log_vehicle(
            plate_text="MANUAL-GATE",
            confidence=100.0,
            direction="IN",
            method="MANUAL",
            custom_info=manual_info
        )

        time.sleep(config.GATE_OPEN_DURATION)
        self.hw.wait_for_vehicle_clear(timeout=6.0)
        self.hw.close_gate()
        time.sleep(1.0)
        self.hw.lcd.display_standby()

    def process_alpr_trigger(self):
        """Proses pembacaan plat saat Sensor IR mendeteksi kendaraan."""
        print("\n[SENSOR IR] Kendaraan terdeteksi di depan gerbang!")
        self.hw.lcd.display(
            "KENDARAAN TERDETEKSI",
            "MENGAMBIL FOTO...",
            "MEMPROSES PLAT...",
            "MOHON TUNGGU..."
        )
        self.hw.buzzer_beep(0.08, 1)

        # Tangkap citra dari webcam USB
        frame = self.capture_frame()
        if frame is None:
            print("[ERROR] Gagal mengambil gambar dari webcam!")
            self.hw.lcd.display(
                "  GAGAL AMBIL FOTO  ",
                "PERIKSA WEBCAM USB",
                "ATAU TAP KARTU RFID",
                "HUBUNGI PETUGAS"
            )
            time.sleep(2.0)
            self.hw.lcd.display_standby()
            return

        # Kirim ke Plate Recognizer API
        api_res = self.api.recognize(frame)
        if not api_res.get("success") or not api_res.get("results"):
            print("  [--] Tidak ada plat nomor terdeteksi pada citra.")
            self.hw.lcd.display(
                "PLAT TIDAK TERBACA ",
                "DEKATKAN KENDARAAN ",
                "ATAU TAP KARTU RFID",
                "TEKAN TOMBOL MANUAL"
            )
            time.sleep(2.5)
            self.hw.lcd.display_standby()
            return

        # Ambil hasil pembacaan plat pertama
        best = api_res["results"][0]
        plate_text = best.get("plate_text", "")
        conf = best.get("confidence", 0.0)

        # Simpan hasil foto jika diatur
        if config.SAVE_RESULTS:
            annotated = draw_results(frame, [best])
            fname = os.path.join(config.OUTPUT_DIR, f"gate_{int(time.time())}.jpg")
            cv2.imwrite(fname, annotated)

        # Cocokkan ke tabel registered_vehicles di Supabase
        vehicle_info = self.db.lookup_vehicle(plate_text)
        vehicle_info["confidence"] = conf

        if vehicle_info["matched"]:
            self.handle_access_granted(vehicle_info, method="ALPR")
        else:
            self.handle_access_denied(vehicle_info, method="ALPR")

    def process_rfid_trigger(self, rfid_uid: str):
        """Proses pembacaan kartu saat RFID di-tap."""
        print(f"\n[RFID] Kartu terdeteksi: UID {rfid_uid}")
        self.hw.lcd.display(
            "  KARTU TERDETEKSI  ",
            f"UID: {rfid_uid[:14]}",
            "MEMERIKSA DATA...",
            "MOHON TUNGGU..."
        )
        self.hw.buzzer_beep(0.08, 1)

        # Cocokkan UID ke database
        card_info = self.db.lookup_rfid(rfid_uid)
        if card_info["matched"]:
            self.handle_access_granted(card_info, method="RFID")
        else:
            self.handle_access_denied(card_info, method="RFID")

    def run(self):
        """Loop utama pemantauan gerbang secara real-time."""
        print("\n" + "=" * 60)
        print("  MEMULAI PEMANTAUAN GERBANG (Loop Standby)")
        print("  Tekan 'Ctrl + C' untuk menghentikan sistem.")
        print("=" * 60 + "\n")

        try:
            while True:
                # 1. Cek Sensor Infrared (Kendaraan Tiba)
                if self.hw.is_vehicle_detected():
                    self.process_alpr_trigger()

                # 2. Cek Kartu RFID USB (Civitas Mengetap Kartu)
                scanned_rfid = self.hw.get_scanned_rfid()
                if scanned_rfid:
                    self.process_rfid_trigger(scanned_rfid)

                # 3. Cek Tombol Push Button (Buka Manual oleh Petugas)
                if self.hw.is_button_pressed():
                    self.handle_manual_override()

                time.sleep(0.05) # Meringankan beban CPU Raspberry Pi 3B+

        except KeyboardInterrupt:
            print("\n[STOP] Menghentikan sistem Smart Parking Gate...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Lepaskan seluruh resource hardware dan kamera."""
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.hw.cleanup()
        print("[OK] Sistem berhasil dinonaktifkan dengan aman.")


def main():
    parser = argparse.ArgumentParser(description="Smart Parking Gate FT UNTIRTA (RPi 3B+)")
    parser.add_argument("--test-cam", action="store_true", help="Uji coba preview webcam USB")
    parser.add_argument("--image", type=str, help="Uji coba deteksi satu file gambar")
    args = parser.parse_args()

    gate = SmartParkingGate()

    if args.test_cam:
        print("[TEST] Membuka window preview webcam. Tekan 'q' untuk keluar.")
        while True:
            frame = gate.capture_frame()
            if frame is not None:
                cv2.imshow("Webcam USB Test (RPi 3B+)", frame)
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
                info = gate.db.lookup_vehicle(plate)
                print(f"Hasil: Plat={plate}, Status={info['status']}")
            else:
                print("Tidak ada plat terdeteksi.")
        gate.cleanup()
    else:
        gate.run()


if __name__ == "__main__":
    main()
