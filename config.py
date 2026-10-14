"""
Konfigurasi ALPR untuk Raspberry Pi 4
Konsep: RPi hanya menangkap gambar, processing via Plate Recognizer API.
"""

# ── Plate Recognizer API ────────────────────────
API_TOKEN = "476ed9b4276c169486fc16e30891cc01f9f0e4f1"          # Ganti dengan token dari platerecognizer.com
API_URL = "https://api.platerecognizer.com/v1/plate-reader/"
API_REGIONS = ["id"]                       # Region Indonesia
API_TIMEOUT = 10                           # Timeout request (detik)

# ── Kamera ───────────────────────────────────────
CAMERA_INDEX = 1                            # Index kamera
CAMERA_WIDTH = 1280                         # Resolusi kamera (lebar)
CAMERA_HEIGHT = 720                         # Resolusi kamera (tinggi)
USE_PICAMERA = False                        # True jika pakai PiCamera

# ── Performa RPi4 ───────────────────────────────
SKIP_FRAMES = 5                             # Proses setiap N frame (hemat bandwidth API)
MIN_CAPTURE_INTERVAL = 2.0                  # Minimum detik antara API calls
JPEG_QUALITY = 85                           # Kualitas JPEG untuk upload (1-100)
MAX_IMAGE_SIZE = (1280, 720)                # Max resolusi gambar sebelum upload

# ── Output ───────────────────────────────────────
SAVE_RESULTS = True                         # Simpan hasil deteksi
OUTPUT_DIR = "output/"                      # Folder output
SHOW_PREVIEW = True                         # Tampilkan preview (False jika headless)

# ── Firebase ─────────────────────────────────────
FIREBASE_ENABLED = True                     # Ubah ke False jika ingin mematikan fitur DB
FIREBASE_CREDENTIALS = "serviceAccountKey.json"
FIREBASE_DB_URL = "https://alpr-fb61b-default-rtdb.asia-southeast1.firebasedatabase.app/"  # GANTI INI DENGAN URL DATABASE-MU
