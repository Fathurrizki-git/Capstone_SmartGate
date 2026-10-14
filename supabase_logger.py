"""
Modul untuk mengintegrasikan sistem ALPR dengan Supabase (PostgreSQL Cloud).
Koneksi langsung dari Raspberry Pi / PC via REST API HTTPS — 100% tanpa MQTT.
"""

import requests
from datetime import datetime
import config


class SupabaseLogger:
    def __init__(self):
        self.url = getattr(config, 'SUPABASE_URL', '').rstrip('/')
        self.key = getattr(config, 'SUPABASE_KEY', '')
        self.enabled = bool(
            self.url 
            and self.key 
            and not 'YOUR_PROJECT_ID' in self.url
            and not 'YOUR_SUPABASE' in self.key
        )

        if not self.enabled:
            print("[INFO] Supabase belum diaktifkan (masih menggunakan konfigurasi default di config.py).")
            return

        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        # Tes koneksi ringan ke endpoint Supabase
        try:
            r = requests.get(f"{self.url}/rest/v1/users?select=id&limit=1", headers=self.headers, timeout=5)
            if r.status_code in (200, 206):
                print("[OK] Supabase Cloud Database terhubung!")
            else:
                print(f"[WARN] Respon Supabase status {r.status_code}: {r.text[:80]}")
        except Exception as e:
            print(f"[WARN] Belum dapat terhubung ke Supabase: {e}")

    def lookup_vehicle(self, plate_text: str):
        """
        Cari apakah plat nomor terdaftar di tabel registered_vehicles.
        Mengembalikan dictionary data pemilik dan kategori (STUDENT/LECTURER/ACADEMIC COMMUNITY).
        """
        if not self.enabled:
            return None
        try:
            clean_plate = plate_text.strip().upper()
            url = f"{self.url}/rest/v1/registered_vehicles?plate=eq.{clean_plate}&select=*"
            res = requests.get(url, headers=self.headers, timeout=4)
            if res.status_code == 200:
                rows = res.json()
                if rows and len(rows) > 0:
                    return rows[0]
        except Exception as e:
            print(f"  [WARN] Lookup plat gagal: {e}")
        return None

    def log_vehicle(self, plate_text: str, confidence: float, region: str = "id", direction: str = "IN"):
        """
        Kirim data plat nomor yang terdeteksi ke tabel vehicle_logs di Supabase.
        Berjalan langsung via HTTPS REST API tanpa perlu MQTT broker.
        """
        clean_plate = plate_text.strip().upper()
        conf_val = round(confidence * 100 if confidence <= 1.0 else confidence, 2)

        if not self.enabled:
            print(f"  [SIMULASI LOCAL] Plat: {clean_plate} (conf: {conf_val}%) dicatat lokal.")
            return None

        try:
            # Cari informasi kendaraan terdaftar
            vehicle_info = self.lookup_vehicle(clean_plate)
            if vehicle_info:
                owner_name = vehicle_info.get('owner_name', 'Civitas Untirta')
                category = vehicle_info.get('category', 'STUDENT')
            else:
                owner_name = 'Pengendara Terdeteksi'
                category = 'STUDENT'

            payload = {
                "plate": clean_plate,
                "name": owner_name,
                "category": category,
                "direction": direction,
                "confidence": conf_val,
                "region": region or "id"
            }

            url = f"{self.url}/rest/v1/vehicle_logs"
            res = requests.post(url, headers=self.headers, json=payload, timeout=6)

            if res.status_code in (200, 201):
                print(f"  [SUPABASE ⚡] Plat {clean_plate} ({category} - {owner_name}) tersimpan ke Cloud!")
                return res.json()
            else:
                print(f"  [SUPABASE ERROR] Status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"  [SUPABASE ERROR] Gagal mengirim data ke Supabase: {e}")

        return None

