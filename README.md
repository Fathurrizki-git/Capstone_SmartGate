# 🚗 Smart Parking Gate FT UNTIRTA (RFID + ALPR) — Capstone A7

Sistem pemantauan dan pengendalian gerbang parkir pintar berbasis **Automatic License Plate Recognition (ALPR)** dan **RFID 13.56 MHz** yang dirancang untuk Fakultas Teknik Universitas Sultan Ageng Tirtayasa (FT UNTIRTA). 

Sistem ini ditenagai oleh **Raspberry Pi 3 Model B+** dengan sistem catu daya mandiri bertenaga surya (**PLTS + Baterai 12V**) dan terintegrasi secara *real-time* ke cloud database **Supabase** (PostgreSQL) serta **Web Dashboard Monitoring**.

---

## 📌 Daftar 8 Komponen Sistem

| No | Komponen | Fungsi & Spesifikasi |
|---|---|---|
| 1 | **Raspberry Pi 3 Model B+** | Pusat pemrosesan, pembacaan sensor, inferensi API, dan kendali aktuator |
| 2 | **Webcam USB** | Kamera penangkap foto plat nomor kendaraan saat memasuki gerbang |
| 3 | **RFID USB 13.56 MHz** | Pembaca kartu KTM / kartu civitas akademika berbasis USB HID |
| 4 | **Buzzer Flash AD16-22SM 12V** | Indikator suara & lampu strobo saat akses disetujui atau ditolak |
| 5 | **Motor Servo (25kg/standard)** | Aktuator penggerak palang gerbang parkir (0° tertutup, 90° terbuka) |
| 6 | **LCD I2C 20x4** | Layar antarmuka instruksi gerbang dan status akses pengendara |
| 7 | **Push Button** | Tombol manual override petugas untuk membuka gerbang darurat/tamu |
| 8 | **Sensor Infrared E18-D80NK** | Sensor deteksi kedatangan dan lewatnya kendaraan di depan gerbang |

---

## 🔌 Diagram Pinout & Wiring (Raspberry Pi 3 Model B+)

Sesuai dengan skema wiring kelistrikan sistem:

```text
Raspberry Pi 3 Model B+ (Header GPIO 40-Pin):
   Pin 2  (5V)          ------> VCC LCD I2C 20x4
   Pin 4  (5V)          ------> VCC Sensor Infrared E18-D80NK
   Pin 6  (GND)         ------> GND LCD I2C 20x4
   Pin 9  (GND)         ------> GND Sensor Infrared
   Pin 14 (GND)         ------> GND Push Button Manual
   Pin 3  (GPIO 2 / SDA) ------> SDA LCD I2C 20x4
   Pin 5  (GPIO 3 / SCL) ------> SCL LCD I2C 20x4
   Pin 11 (GPIO 17)     ------> OUT Sensor Infrared E18-D80NK (Active LOW)
   Pin 12 (GPIO 18)     ------> Signal Motor Servo Palang (Hardware PWM0)
   Pin 13 (GPIO 27)     ------> Signal Push Button Manual (Active LOW, Pull-Up)
   Pin 15 (GPIO 22)     ------> Base Transistor NPN (Driver Buzzer Flash 12V)
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

## 🔄 Alur Logika Gerbang Otomatis

```mermaid
flowchart TD
    A["🚗 Kendaraan Mendekat"] --> B{"Pemicu Akses"}
    B -->|Sensor IR Terhalang (GPIO17)| C["📸 Ambil Foto via Webcam USB"]
    B -->|Kartu Di-tap| D["💳 Baca RFID USB 13.56 MHz"]
    B -->|Tombol Ditekan (GPIO27)| E["🔘 Buka Manual oleh Petugas"]

    C --> F["🧠 Plate Recognizer Cloud API"]
    F --> G["🔍 Cek Database Supabase (registered_vehicles)"]
    D --> G

    G -->|Terdaftar / Civitas Valid| H["✅ AKSES DITERIMA"]
    H --> H1["LCD: Tampilkan Nama & Plat"]
    H1 --> H2["Buzzer: Beep 2x Pendek"]
    H2 --> H3["Servo: Buka Palang (90°)"]
    H3 --> H4["Kirim Full Data ke Supabase (vehicle_logs)"]
    H4 --> H5["Tunggu Kendaraan Melintas (Sensor IR Clear)"]
    H5 --> H6["Servo: Tutup Palang (0°)"]

    G -->|Tidak Terdaftar / Asing| I["❌ AKSES DITOLAK"]
    I --> I1["LCD: 'TIDAK TERDAFTAR - HUBUNGI PETUGAS'"]
    I1 --> I2["Buzzer: Alarm Flash Panjang"]
    I2 --> I3["Palang Tetap Tertutup"]
    I3 --> I4["Kirim Log Status Tidak Terdaftar ke Supabase"]

    E --> H3
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
