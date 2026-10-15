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
  8. Dual Sensor Infrared E18-D80NK:
     - Sensor IR 1 (Sebelum Palang): GPIO 17 - Pin 11 (Deteksi Kedatangan / ALPR)
     - Sensor IR 2 (Setelah Palang): GPIO 23 - Pin 16 (Pemicu Penutup Palang)
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

        # 5. Keamanan & Penutup Palang Otomatis (Sensor IR 2 + Safety Timer)
        self.wait_and_close_gate()

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

        # Keamanan & Penutup Palang Otomatis (Sensor IR 2 + Safety Timer)
        self.wait_and_close_gate()

    def wait_and_close_gate(self):
        """
        Logika Penutup Palang Otomatis Berbasis 2 Sensor Infrared (Bebas Bug):
        - Sensor IR 1 (Sebelum Palang): Memastikan kendaraan mulai maju.
        - Sensor IR 2 (Setelah Palang): Mendeteksi kendaraan melintas melewati palang.

        Alur Eksekusi Tanpa Bug:
        1. Tunggu kendaraan bergerak maju & memicu Sensor IR 2 (PIN_IR_AFTER == LOW).
           Jika kendaraan mogok/batal melintas hingga GATE_MAX_WAIT detik, palang ditutup fail-safe.
        2. Tunggu kendaraan SELESAI melintasi Sensor IR 2 (PIN_IR_AFTER == HIGH).
           Mencegah palang turun saat bodi kendaraan masih berada di bawah palang/sensor.
        3. Mulai timer jeda GATE_CLOSE_DELAY (misal 2.0 detik) sebelum palang menutup.
           PROTEKSI RE-TRIGGER: Jika Sensor IR 2 terhalang kembali selama countdown
           (misal kendaraan panjang / ada mobil lain menempel), timer otomatis DIRESET
           dan kembali menunggu sensor bebas agar palang tidak pernah menimpa kendaraan!
        4. Setelah timer selesai dan aman, buzzer berbunyi singkat & palang ditutup ke 0 derajat.
        """
        if not self.hw.is_rpi:
            # Mode Simulasi di PC / Windows
            print("  [SIMULASI] Menunggu kendaraan melaju menuju Sensor IR 2 (Setelah Palang)...")
            time.sleep(1.2)
            print("  [SIMULASI] Sensor IR 2 TERDETEKSI (Kendaraan sedang melintas di bawah palang).")
            time.sleep(1.2)
            print("  [SIMULASI] Sensor IR 2 BEBAS (Kendaraan telah melewati palang).")
            print(f"  [SIMULASI] Menjalankan safety timer {config.GATE_CLOSE_DELAY} detik sebelum menutup palang...")
            time.sleep(config.GATE_CLOSE_DELAY)
            self.hw.buzzer_beep(0.1, 1)
            self.hw.close_gate()
            print("  [GERBANG] Palang berhasil ditutup kembali (0 derajat).")
            time.sleep(1.0)
            self.hw.lcd.display_standby()
            return

        start_time = time.time()
        max_wait = getattr(config, 'GATE_MAX_WAIT', 25.0)
        close_delay = getattr(config, 'GATE_CLOSE_DELAY', 2.0)

        print("\n  [SAFETY GATE] Palang terbuka. Menunggu kendaraan menuju Sensor IR 2 (Setelah Palang)...")
        self.hw.lcd.display(
            "  SILAKAN MELINTAS  ",
            "   HATI-HATI JALAN  ",
            "MENUJU SENSOR 2...  ",
            "PALANG TERBUKA (90*)"
        )

        # -----------------------------------------------------------------
        # TAHAP 1: Tunggu kendaraan menyentuh/memicu Sensor IR 2
        # -----------------------------------------------------------------
        sensor2_triggered = False
        while time.time() - start_time < max_wait:
            if self.hw.is_vehicle_at_sensor2():
                sensor2_triggered = True
                print("  [IR 2 AKTIF \u2705] Kendaraan terdeteksi melintasi Sensor IR 2!")
                break
            time.sleep(0.05)

        # Kasus Fail-safe: Kendaraan tidak pernah mencapai Sensor 2 dalam GATE_MAX_WAIT detik
        if not sensor2_triggered:
            if not self.hw.is_vehicle_at_sensor1():
                print(f"  [FAIL-SAFE] Timeout {max_wait}s: Kendaraan batal melintas / sudah pergi. Menutup palang.")
            else:
                print(f"  [FAIL-SAFE] Timeout {max_wait}s: Menutup palang demi keamanan.")
            self.hw.close_gate()
            time.sleep(1.0)
            self.hw.lcd.display_standby()
            return

        # -----------------------------------------------------------------
        # TAHAP 2: Tunggu kendaraan SELESAI melintasi Sensor IR 2
        # (Sensor 2 harus kembali HIGH / tidak terhalang)
        # -----------------------------------------------------------------
        print("  [IR 2 PROSES] Kendaraan sedang melintas. Menunggu seluruh bodi melewati Sensor 2...")
        self.hw.lcd.display(
            " KENDARAAN MELINTAS ",
            "   JANGAN BERHENTI  ",
            "MELEWATI SENSOR 2...",
            "PALANG TERBUKA (90*)"
        )

        stuck_timeout = 25.0
        stuck_start = time.time()
        while self.hw.is_vehicle_at_sensor2():
            if time.time() - stuck_start > stuck_timeout:
                print("  [WARN] Kendaraan terdiam di atas Sensor IR 2 lebih dari 25s!")
                break
            time.sleep(0.1)

        print("  [IR 2 CLEAR \u2705] Kendaraan telah selesai melewati Sensor IR 2.")

        # -----------------------------------------------------------------
        # TAHAP 3: Safety Countdown Timer sebelum palang menutup
        # Dengan re-trigger protection: jika Sensor 2 terhalang lagi, reset timer!
        # -----------------------------------------------------------------
        print(f"  [SAFETY TIMER] Memulai timer penutup {close_delay} detik...")
        
        timer_remaining = close_delay
        interval = 0.1
        while timer_remaining > 0:
            # Re-trigger protection: Jika ada kendaraan susulan / objek terdeteksi lagi di IR 2
            if self.hw.is_vehicle_at_sensor2():
                print("  [RE-TRIGGER \u26a0\ufe0f] Sensor IR 2 kembali terhalang! Mereset safety timer...")
                self.hw.lcd.display(
                    "OBJEK TERDETEKSI IR2",
                    "MENUNGGU BEBAS...   ",
                    "TIMER DIRESET       ",
                    "PALANG TETAP TERBUKA"
                )
                while self.hw.is_vehicle_at_sensor2():
                    time.sleep(0.1)
                timer_remaining = close_delay # Reset timer penuh
                continue

            self.hw.lcd.display(
                "  KENDARAAN LEWAT   ",
                " SENSOR 2 CLEAR OK  ",
                "PALANG AKAN MENUTUP ",
                f"WAKTU: {timer_remaining:.1f} DETIK"
            )
            time.sleep(interval)
            timer_remaining -= interval

        # -----------------------------------------------------------------
        # TAHAP 4: Tutup Palang
        # -----------------------------------------------------------------
        self.hw.buzzer_beep(0.1, 1)
        self.hw.close_gate()
        print("  [GERBANG] Palang berhasil ditutup kembali (0 derajat).")

        self.hw.lcd.display(
            " GERBANG KELUAR FT  ",
            "  UNTIRTA CILEGON   ",
            "  PALANG TERTUTUP   ",
            "    TERIMA KASIH    "
        )
        time.sleep(1.5)

        # Tunggu sampai Sensor 1 benar-benar bebas sebelum siap menerima kendaraan baru
        debounce_start = time.time()
        while self.hw.is_vehicle_at_sensor1() and (time.time() - debounce_start < 4.0):
            time.sleep(0.2)

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
        print("  Sensor IR 1 (Sebelum Palang): Pemicu deteksi kedatangan & kamera ALPR")
        print("  Sensor IR 2 (Setelah Palang): Pemicu penutup palang otomatis + timer")
        print("  Syarat Buka Otomatis: PLAT NOMOR + KARTU RFID KEDUANYA HARUS COCOK!")
        print("  Bypass Tamu: Tekan Push Button Manual (GPIO 27)")
        print("  Tekan 'Ctrl + C' untuk keluar.")
        print("=" * 65 + "\n")

        try:
            while True:
                # 1. Pemicu Utama: Sensor IR 1 (Sebelum Palang) mendeteksi kendaraan mendekat
                # Kamera HANYA memotret saat ada kendaraan (tidak capture terus menerus)
                if self.hw.is_vehicle_at_sensor1():
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
