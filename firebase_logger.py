"""
Modul untuk mengintegrasikan ALPR dengan Firebase Realtime Database.
Mengirim log kendaraan masuk secara real-time ke dashboard web.
"""

import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import config

class FirebaseLogger:
    def __init__(self):
        self.enabled = config.FIREBASE_ENABLED
        if not self.enabled:
            return
            
        try:
            # Cegah inisialisasi ganda jika aplikasi direload
            if not firebase_admin._apps:
                cred = credentials.Certificate(config.FIREBASE_CREDENTIALS)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': config.FIREBASE_DB_URL
                })
            
            # Referensi ke tabel "logs" di database
            self.ref = db.reference('logs')
            print("[OK] Firebase Realtime Database terhubung!")
            
        except FileNotFoundError:
            print("[ERROR] File serviceAccountKey.json tidak ditemukan!")
            self.enabled = False
        except ValueError:
            print("[ERROR] FIREBASE_DB_URL di config.py sepertinya belum diganti!")
            self.enabled = False
        except Exception as e:
            print(f"[ERROR] Gagal menghubungkan ke Firebase: {e}")
            self.enabled = False

    def log_vehicle(self, plate_text, confidence, region=""):
        """
        Push data plat nomor yang terdeteksi ke Firebase.
        """
        if not self.enabled:
            return
        
        try:
            # Waktu saat ini
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # push() otomatis membuat ID unik untuk setiap data masuk
            new_log_ref = self.ref.push()
            
            # Set data JSON yang akan dikirim
            new_log_ref.set({
                'plate': plate_text,
                'confidence': round(confidence, 3),
                'region': region,
                'timestamp': timestamp
            })
            
            print(f"  [FIREBASE] ☁️ Berhasil mencatat plat {plate_text} ke database.")
        except Exception as e:
            print(f"  [FIREBASE ERROR] Gagal mencatat data: {e}")
