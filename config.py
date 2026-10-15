"""
Konfigurasi Sistem Smart Parking Gate FT UNTIRTA
Perangkat: Raspberry Pi 3 Model B+
Komponen:
  1. Raspberry Pi 3 Model B+
  2. Webcam USB
  3. RFID USB 13.56 MHz
  4. Buzzer Flash AD16-22SM 12V (GPIO22 - Pin 15)
  5. Motor Servo Palang (GPIO18 - Pin 12)
  6. LCD I2C 20x4 (SDA: GPIO2 / Pin 3, SCL: GPIO3 / Pin 5)
  7. Push Button Manual (GPIO27 - Pin 13)
  8. Sensor Infrared E18-D80NK (GPIO17 - Pin 11)
"""

# ── Plate Recognizer API ────────────────────────
API_TOKEN = "476ed9b4276c169486fc16e30891cc01f9f0e4f1"          # Token dari platerecognizer.com
API_URL = "https://api.platerecognizer.com/v1/plate-reader/"
API_REGIONS = ["id"]                       # Region Indonesia
API_TIMEOUT = 8                            # Timeout request (detik)

# ── Webcam USB ───────────────────────────────────
CAMERA_INDEX = 0                            # 0 untuk Webcam USB utama
CAMERA_WIDTH = 640                          # Resolusi optimal untuk RPi 3B+ (hemat RAM & cepat)
CAMERA_HEIGHT = 480
JPEG_QUALITY = 85                           # Kualitas kompresi upload citra

# ── GPIO Pin Mapping (BCM numbering pada RPi 3B+) ─
# Sesuai diagram wiring:
PIN_IR_SENSOR = 17       # Pin 11 (Sensor Infrared E18-D80NK - Active LOW)
PIN_PUSH_BUTTON = 27     # Pin 13 (Push Button Manual Buka Gerbang - Active LOW)
PIN_SERVO = 18           # Pin 12 (Motor Servo Palang - Hardware PWM0)
PIN_BUZZER = 22          # Pin 15 (Buzzer Flash 12V via Transistor NPN - Active HIGH)

# ── LCD I2C 20x4 ─────────────────────────────────
LCD_I2C_ADDR = 0x27      # Alamat I2C umum: 0x27 atau 0x3F
LCD_I2C_BUS = 1          # I2C Bus 1 (SDA: GPIO2 / Pin 3, SCL: GPIO3 / Pin 5)
LCD_COLS = 20
LCD_ROWS = 4

# ── Parameter Palang Gerbang & Timing ────────────
SERVO_OPEN_ANGLE = 90    # Sudut palang terbuka (derajat)
SERVO_CLOSE_ANGLE = 0    # Sudut palang tertutup (derajat)
GATE_OPEN_DURATION = 4.0 # Waktu jeda palang terbuka sebelum ditutup kembali (detik)

# ── Database (Supabase Cloud PostgreSQL) ───────────
# Dapatkan dari: Supabase Dashboard -> Project Settings -> API
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_OR_SERVICE_KEY"

# ── Penyimpanan & Debug ──────────────────────────
SAVE_RESULTS = True                         # Simpan foto hasil deteksi ke folder output/
OUTPUT_DIR = "output/"                      # Folder penyimpanan citra
SHOW_PREVIEW = False                        # Set True jika menggunakan monitor/GUI desktop
