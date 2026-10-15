# 🚗 Smart Parking Exit Gate FT UNTIRTA (RFID + ALPR) — Capstone A7

Sistem pemantauan dan pengendalian **gerbang KELUAR parkir pintar** berbasis verifikasi **Automatic License Plate Recognition (ALPR)** dan **RFID 13.56 MHz** yang dirancang untuk Fakultas Teknik Universitas Sultan Ageng Tirtayasa (FT UNTIRTA). 

Sistem ini difokuskan khusus pada **pintu keluar parkir (Exit Gate Only)** untuk memastikan keamanan kendaraan:
- **Verifikasi Keluar Otomatis:** Kendaraan keluar diverifikasi melalui **ALPR (Kamera Plat)** dan/atau **Kartu RFID Civitas**. Jika data terdaftar dan valid, palang gerbang keluar otomatis terbuka.
- **Verifikasi Keluar Manual:** Untuk kendaraan tamu atau yang belum terdaftar di sistem, petugas keamanan melakukan pengecekan manual dan membuka gerbang keluar via **Push Button**.

Sistem ditenagai oleh **Raspberry Pi 3 Model B+** dengan catu daya mandiri bertenaga surya (**PLTS + Baterai 12V**) dan terintegrasi secara *real-time* ke cloud database **Supabase** (PostgreSQL) dengan status arah `OUT` (Keluar).

---

## 📌 Daftar Komponen Sistem

| No | Komponen | Fungsi & Spesifikasi |
|---|---|---|
| 1 | **Raspberry Pi 3 Model B+** | Pusat pemrosesan, inferensi API, dan kendali logika gerbang keluar |
| 2 | **Webcam USB** | Kamera penangkap plat nomor saat kendaraan mendekati palang keluar |
| 3 | **RFID USB 13.56 MHz** | Pembaca kartu KTM / kartu civitas akademika berbasis USB HID |
| 4 | **Buzzer Flash AD16-22SM 12V** | Indikator suara & lampu strobo saat verifikasi keluar disetujui / ditolak |
| 5 | **Motor Servo (25kg/standard)** | Aktuator penggerak palang gerbang keluar (0° tertutup, 90° terbuka) |
| 6 | **LCD I2C 20x4** | Layar panduan instruksi pengendara dan status verifikasi keluar |
| 7 | **Push Button** | Tombol manual override petugas untuk membuka gerbang bagi tamu / belum terdaftar |
| 8 | **Sensor Infrared 1 (Sebelum Palang)** | E18-D80NK (GPIO 17 - Pin 11): Deteksi kedatangan kendaraan agar kamera tidak memotret terus-menerus |
| 9 | **Sensor Infrared 2 (Setelah Palang)** | E18-D80NK (GPIO 23 - Pin 16): Deteksi kendaraan melintas sebagai pemicu penutupan palang otomatis via safety timer |

---

## 🔌 Diagram Pinout & Wiring (Raspberry Pi 3 Model B+)

Sesuai dengan skema wiring kelistrikan sistem:

```text
Raspberry Pi 3 Model B+ (Header GPIO 40-Pin):
   Pin 2  (5V)          ------> VCC LCD I2C 20x4
   Pin 4  (5V)          ------> VCC Sensor IR 1 & Sensor IR 2 (E18-D80NK)
   Pin 6  (GND)         ------> GND LCD I2C 20x4
   Pin 9  (GND)         ------> GND Sensor IR 1 (Sebelum Palang)
   Pin 14 (GND)         ------> GND Push Button Manual
   Pin 20 (GND)         ------> GND Sensor IR 2 (Setelah Palang)
   Pin 3  (GPIO 2 / SDA) ------> SDA LCD I2C 20x4
   Pin 5  (GPIO 3 / SCL) ------> SCL LCD I2C 20x4
   Pin 11 (GPIO 17)     ------> OUT Sensor IR 1 Sebelum Palang (Active LOW)
   Pin 12 (GPIO 18)     ------> Signal Motor Servo Palang (Hardware PWM0)
   Pin 13 (GPIO 27)     ------> Signal Push Button Manual (Active LOW, Pull-Up)
   Pin 15 (GPIO 22)     ------> Base Transistor NPN (Driver Buzzer Flash 12V)
   Pin 16 (GPIO 23)     ------> OUT Sensor IR 2 Setelah Palang (Active LOW)
   Port USB 1           ------> Webcam USB
   Port USB 2           ------> RFID USB 13.56 MHz Reader
```

### ⚡ Arsitektur Catu Daya (Solar PLTS & Buck Converter)
* **Panel Surya (PLTS)** terhubung ke **Solar Charge Controller (SCC MPPT 12V 10A)**.
* **Baterai 12V (20.000 mAh)** terhubung ke port baterai SCC MPPT.
* **Jalur Output LOAD SCC (12V):**
  - **Buck Converter A (Step-down 12V ke 5V):** Menyuplai daya ke Raspberry Pi 3 Model B+ melalui port Micro-USB.
  - **Buck Converter B (Step-down 12V ke 5V):** Menyuplai daya arus tinggi ke Motor Servo (GND terhubung ke common GND).
  - **Jalur Langsung 12V:** Menyuplai daya ke Buzzer Flash AD16-22SM 12V melalui *switching* transistor NPN yang dipicu oleh GPIO 22.

---

## 🔄 Alur Logika Verifikasi Ganda & Penutup Palang Otomatis (Dual IR Sensor)

Sistem menggunakan **Dual-Factor Authentication (2FA)** dan **2 Sensor Infrared Bebas Bug**:
1. **Sensor IR 1 (Sebelum Palang):** Memicu webcam mengambil foto plat nomor dan meminta pengendara men-tap RFID. Kamera **tidak mengambil gambar terus-menerus** jika tidak ada kendaraan.
2. **Dual Verification:** Plat nomor **DAN** Kartu RFID **KEDUANYA HARUS COCOK** pada data pemilik yang sama di database `registered_vehicles`.
3. **Buka Manual (Bypass Tamu):** Jika belum terdaftar atau terjadi ketidakcocokan, petugas keamanan dapat membuka gerbang secara fisik via **Push Button (GPIO 27)** ATAU secara jarak jauh melalui **Web Dashboard (Menu Security Notification)** dengan pop-up konfirmasi keamanan.
4. **Sensor IR 2 (Setelah Palang) + Safety Timer:** Setelah palang terbuka, sistem mendeteksi mobil melintas ke Sensor 2. Ketika mobil telah sepenuhnya melewati Sensor 2, sistem mengaktifkan **Safety Timer (2.0s)** sebelum palang turun ke 0°. Jika ada kendaraan susulan memicu Sensor 2 selama timer, timer langsung **direset** agar palang tidak pernah menimpa kendaraan!

```mermaid
flowchart TD
    A["🚗 Kendaraan Mendekati Gerbang Keluar"] --> B["🔴 Sensor IR 1 Terhalang (GPIO 17)"]
    B --> C["📸 1. Webcam USB: Capture Plat Nomor (ALPR)"]
    C --> D["💳 2. Pengendara Tap Kartu RFID 13.56 MHz"]

    C & D --> E["🔍 Verifikasi Ganda ke Supabase (registered_vehicles)"]

    E -->|KEDUA DATA COCOK (Plat + RFID Sama)| F["✅ AKSES KELUAR DITERIMA"]
    F --> F1["LCD: 'HATI-HATI DI JALAN :)' & Nama Pemilik"]
    F1 --> F2["Buzzer: Beep 2x Pendek"]
    F2 --> F3["Servo: Buka Palang Keluar (90°)"]
    F3 --> F4["Kirim Log Lengkap ke Supabase (Arah: OUT)"]

    E -->|Plat & RFID BEDA / Kartu Orang Lain| G["❌ DATA TIDAK COCOK (DITOLAK)"]
    E -->|Belum Terdaftar / Tamu| H["❌ BELUM TERDAFTAR"]
    
    G & H --> I["Palang Keluar TETAP TERTUTUP + Alarm Strobo"]
    I --> J["🔘 Petugas Cek Manual: Tekan Push Button / Web Dashboard"]
    J --> F3

    F4 --> K["🚗 Kendaraan Bergerak Maju Melewati Palang"]
    K --> L["🟡 Sensor IR 2 Terdeteksi (GPIO 23 - Sedang Melintas)"]
    L --> M["🟢 Sensor IR 2 Bebas (Bodi Mobil Selesai Melintas)"]
    M --> N["⏱️ Mulai Safety Countdown Timer (2.0 Detik)"]
    N -->|Ada objek memicu IR 2 lagi| L
    N -->|Timer Selesai & Area Bebas| O["🔒 Servo: Tutup Palang Keluar (0°)"]
    O --> P["Standby Menunggu Kendaraan Berikutnya"]
```

---

## 📂 Struktur Direktori

```text
ALPR/
├── config.py             # Konfigurasi Pin GPIO RPi 3B+, kamera USB, dan Supabase
├── hardware.py           # Driver kontrol LCD 20x4, Servo, Buzzer, IR Sensor, Button, RFID
├── main.py               # Program utama otomasi palang parkir RPi 3B+
├── plate_recognizer.py   # Client REST API Plate Recognizer & anotasi citra OpenCV
├── supabase_logger.py    # Modul sinkronisasi database Supabase & pencocokan plat/RFID
├── manage_vehicles.py    # CLI pengelolaan kendaraan & kartu RFID terdaftar di Supabase
├── manage_users.py       # CLI pengelolaan akun petugas gerbang & admin di Supabase
├── schema.sql            # Skema tabel database Supabase (SQL Editor)
├── requirements-rpi.txt  # Dependensi Python untuk Raspberry Pi 3 Model B+
├── requirements-pc.txt   # Dependensi Python untuk simulasi di PC/Laptop
├── output/               # Folder penyimpanan citra deteksi gerbang
└── web_dashboard/        # Web Dashboard Monitoring Petugas
    ├── index.html        # Dashboard interaktif SPA (Vehicle Log, Trendline, Security)
    ├── supabase_config.js# Konfigurasi koneksi Supabase Web
    └── img/              # Aset logo Untirta & Crodas
```

---

## 🚀 Panduan Instalasi & Menjalankan pada Raspberry Pi 3 Model B+

### 1. Aktifkan Antarmuka I2C di Raspberry Pi OS
Pastikan fitur I2C aktif agar LCD 20x4 dapat terbaca:
```bash
sudo raspi-config
# Pilih: Interface Options -> I2C -> Enable -> Finish
```

Periksa alamat I2C LCD (umumnya `0x27`):
```bash
sudo apt-get install -y i2c-tools
sudo i2cdetect -y 1
```

### 2. Instalasi Dependensi Python
```bash
cd ALPR
pip install -r requirements-rpi.txt
```

### 3. Konfigurasi Kredensial Supabase & Token API
Buka file `config.py` dan sesuaikan token Plate Recognizer serta kredensial Supabase Anda:
```python
API_TOKEN = "token_platerecognizer_anda"
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_OR_SERVICE_KEY"
```

### 4. Setup Database di Supabase
1. Buka Dashboard Supabase Anda, masuk ke **SQL Editor**.
2. Salin isi file [schema.sql](file:///c:/Users/MUHAMMAD%20FATHURRIZKI/OneDrive/Documents/1%20-%20MUHAMMAD%20FATHURRIZKI/1%20-%20UNTIRTA/0%20-%20Bismillah%20Capstone/ALPR/alpr/schema.sql) dan klik **Run**.

### 5. Mengelola Data Civitas (Plat & RFID)
Gunakan CLI [manage_vehicles.py](file:///c:/Users/MUHAMMAD%20FATHURRIZKI/OneDrive/Documents/1%20-%20MUHAMMAD%20FATHURRIZKI/1%20-%20UNTIRTA/0%20-%20Bismillah%20Capstone/ALPR/alpr/manage_vehicles.py):
```bash
# Melihat daftar kendaraan & RFID terdaftar:
python manage_vehicles.py --list

# Mendaftarkan civitas baru (Plat + RFID):
python manage_vehicles.py --add --plate "A 1234 BC" --name "Ahmad Zaki" --category "STUDENT" --nim "3332210001" --rfid "0001234567"

# Melihat log deteksi gerbang terbaru:
python manage_vehicles.py --logs
```

### 6. Menjalankan Sistem Gerbang
Jalankan program utama:
```bash
python main.py
```

*Untuk uji coba preview Webcam USB:*
```bash
python main.py --test-cam
```

---

## 💻 Menjalankan Web Dashboard Petugas

1. Buka folder `web_dashboard/`.
2. Buka `index.html` langsung di browser, atau jalankan web server:
   ```bash
   cd web_dashboard
   python -m http.server 8080
   ```
3. Akses via browser: `http://<IP-Raspberry-Pi>:8080`
   - **Login Demo:** `admin@untirta.ac.id` | Password: `admin123`

---

## 👥 Pengembang
* **Tim Capstone A7** — Fakultas Teknik, Universitas Sultan Ageng Tirtayasa (UNTIRTA).
