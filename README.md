# 🚗 Smart Parking Gate FT UNTIRTA — Capstone A7

Sistem pemantauan gerbang parkir pintar berbasis **Automatic License Plate Recognition (ALPR)** yang dirancang untuk Fakultas Teknik Universitas Sultan Ageng Tirtayasa (FT UNTIRTA). Proyek ini memadukan penangkapan citra plat nomor melalui kamera (Raspberry Pi 4 / PC), inferensi cloud AI (Plate Recognizer API), pencatatan realtime di Firebase, dan antarmuka pemantauan **Web Dashboard Interaktif (SPA)**.

---

## 📌 Fitur Utama

### 1. 🔍 ALPR Pipeline (`main.py`)
- **Cloud-Based Recognition:** Menggunakan Plate Recognizer API dengan optimasi khusus format plat nomor Indonesia (`id`).
- **Hemat Bandwidth & Asynchronous:** Pemrosesan API berjalan di latar belakang (threading) dengan frame-skipping dan interval capture yang dapat dikonfigurasi.
- **Dukungan Kamera Fleksibel:** Mendukung USB Webcam, PiCamera, dan input citra/folder batch.
- **Logging Real-Time ke Firebase:** Data kendaraan (plat, waktu, kategori, confidence, status masuk/keluar) otomatis tersinkronisasi ke Firebase Realtime Database.
- **Penyimpanan Anotasi:** Gambar hasil deteksi dengan bounding box dan label disimpan secara otomatis ke folder `output/`.

### 2. 📊 Web Dashboard Interaktif (`web_dashboard/`)
- **Single Page Application (SPA):** Menggabungkan seluruh halaman menjadi satu aplikasi tanpa reload dengan hash-based routing (`#/dashboard`, `#/trendline`, `#/vehicle-log`, `#/security`, `#/login`).
- **Real-Time Simulation:** Mode simulasi kendaraan live (interval 6 detik) untuk uji coba tanpa kamera fisik.
- **Kapasitas Parkir & Pengukur Gauge:** Visualisasi kapasitas terisi, slot kosong, dan persentase kapasitas parkir FT Untirta.
- **Trendline & Analisis Per Jam:** Grafik SVG interaktif dengan tooltip yang menampilkan volume kendaraan masuk vs keluar per jam.
- **Vehicle Log Terintegrasi:**
  - Pencarian nomor plat & nama pengendara secara live.
  - Filter kategori (Student, Lecturer, Academic Community) & arah (IN/OUT).
  - Multi-column sorting (Waktu, Plat, Kategori, Confidence).
  - Paginasi dinamis dan modal detail kendaraan.
  - **Ekspor CSV:** Unduh log kendaraan harian langsung dalam format CSV.
- **Security Notification & Real-Time Camera:**
  - Monitoring notifikasi otomatis jika kapasitas hampir penuh atau confidence pembacaan plat rendah (<80%).
  - Dukungan streaming webcam langsung di browser dengan tombol snapshot kamera.
- **Desain Modern Vision UI & Identitas Untirta:**
  - Tema gelap futuristik dengan Glassmorphism (Vision UI).
  - Logo resmi FT UNTIRTA dan maskot **Crodas Untirta** pada card selamat datang.
- **Zoom-Resilient & Responsif:**
  - Halaman login didesain fluid menggunakan `max(px, vw)` sehingga tetap tajam, proporsional, dan nyaman digunakan baik pada zoom out ekstrem (25%) maupun zoom in (200%+).

---

## 📂 Struktur Direktori

```text
ALPR/
├── config.py                  # Konfigurasi token API, kamera, interval, dan Firebase
├── firebase_logger.py         # Modul integrasi Firebase Realtime Database
├── plate_recognizer.py        # Client HTTP API Plate Recognizer & anotasi OpenCV
├── main.py                    # Script eksekusi utama ALPR pipeline
├── requirements-pc.txt        # Dependensi Python untuk PC/Laptop
├── requirements-rpi.txt       # Dependensi Python untuk Raspberry Pi 4
├── serviceAccountKey.json     # Kunci kredensial Firebase Admin SDK
├── test.jpg                   # Gambar contoh untuk pengujian
├── output/                    # Direktori penyimpanan hasil deteksi ALPR
└── web_dashboard/             # Antarmuka Web Dashboard
    ├── index.html             # Aplikasi utama (SPA Terpadu dengan Router & UI Lengkap)
    ├── Dashboard.html         # Halaman Dashboard individual
    ├── Trendline.html         # Halaman Trendline individual
    ├── VehicleLog.html        # Halaman Log Kendaraan individual
    ├── SecurityPage.html      # Halaman Notifikasi Keamanan & Kamera
    ├── LoginPage.html         # Halaman Login individual (Zoom-Resilient)
    └── img/                   # Aset gambar & ikon
        ├── LOGO-UNTIRTA-1.png # Logo resmi FT Untirta
        ├── Crodas-1.png       # Maskot Crodas Untirta
        ├── image-1.png        # Foto Gedung FT Untirta
        ├── Background.png     # Background UI
        ├── chart.svg          # Ikon navigasi Trendline
        ├── circle.svg         # Ikon status Vehicle Log
        └── ...
```

---

## 🚀 Panduan Menjalankan Sistem

### A. Menjalankan Python ALPR Pipeline

#### 1. Instalasi Dependensi
Untuk PC / Laptop (Windows/Linux/macOS):
```bash
pip install -r requirements-pc.txt
```
Untuk Raspberry Pi 4 (Raspberry Pi OS):
```bash
pip install -r requirements-rpi.txt
```

#### 2. Konfigurasi Kredensial
Buka file `config.py` dan sesuaikan parameter Supabase Anda:
```python
API_TOKEN = "token_platerecognizer_anda"

# Database: Supabase (PostgreSQL Cloud)
DATABASE_PROVIDER = "supabase"
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_OR_SERVICE_KEY"

CAMERA_INDEX = 0  # 0 untuk webcam bawaan, 1 untuk USB webcam eksternal
```

#### 3. Setup Tabel Database di Supabase
1. Masuk ke Dashboard Supabase Anda, lalu buka **SQL Editor**.
2. Buka file [schema.sql](file:///c:/Users/MUHAMMAD%20FATHURRIZKI/OneDrive/Documents/1%20-%20MUHAMMAD%20FATHURRIZKI/1%20-%20UNTIRTA/0%20-%20Bismillah%20Capstone/ALPR/alpr/schema.sql) di proyek ini, salin seluruh kodenya, lalu klik **Run**.
3. Tabel `users`, `registered_vehicles`, dan `vehicle_logs` akan langsung terbuat lengkap dengan data awal.

#### 4. Mengelola User (Tambah / Hapus / Lihat)
Gunakan script CLI [manage_users.py](file:///c:/Users/MUHAMMAD%20FATHURRIZKI/OneDrive/Documents/1%20-%20MUHAMMAD%20FATHURRIZKI/1%20-%20UNTIRTA/0%20-%20Bismillah%20Capstone/ALPR/alpr/manage_users.py):
```bash
# Melihat daftar user di Supabase:
python manage_users.py --list

# Menambah user baru:
python manage_users.py --add

# Menghapus user:
python manage_users.py --delete email@untirta.ac.id
```

#### 5. Menjalankan Deteksi
* **Mode Kamera Otomatis (Live Deploy):**
  ```bash
  python main.py --camera
  ```
* **Mode Kamera Manual (Tekan [Spasi] untuk menangkap gambar):**
  ```bash
  python main.py --camera --manual
  ```
* **Mode Gambar Tunggal:**
  ```bash
  python main.py --image test.jpg
  ```
* **Mode Folder (Batch):**
  ```bash
  python main.py --folder path/ke/folder/
  ```

---

### B. Menjalankan Web Dashboard

1. Buka folder `web_dashboard/`.
2. Buka file `index.html` langsung menggunakan browser modern (Google Chrome, Microsoft Edge, Firefox, atau Safari).
3. Anda juga dapat menjalankannya melalui server lokal sederhana:
   ```bash
   cd web_dashboard
   python -m http.server 8080
   ```
   Lalu buka browser di `http://localhost:8080`.

#### 🔑 Akun Demo Login:
* **Email:** `admin@untirta.ac.id`
* **Password:** `admin123`

---

## 🛠️ Teknologi yang Digunakan

* **Backend / Edge Device:** Python 3.9+, OpenCV, NumPy, Requests, Threading.
* **Computer Vision / AI:** [Plate Recognizer Snapshot API](https://platerecognizer.com/) (OCR Plat Nomor Kendaraan Indonesia).
* **Cloud Database:** Firebase Realtime Database.
* **Frontend Web:** HTML5, CSS3 Modern (CSS Grid, Flexbox, Fluid Clamping, Glassmorphism, CSS Custom Properties), Vanilla JavaScript ES6+ (No heavy framework dependencies, ringan dan cepat).
* **Font:** Plus Jakarta Sans (Google Fonts).

---

## 👥 Tim Pengembang

* **Tim Capstone A7** — Fakultas Teknik, Universitas Sultan Ageng Tirtayasa (UNTIRTA).
* **Tahun:** 2026