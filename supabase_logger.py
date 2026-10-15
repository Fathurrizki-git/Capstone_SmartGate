"""
Modul untuk mengintegrasikan sistem ALPR dengan Supabase (PostgreSQL Cloud).
Koneksi langsung dari Raspberry Pi / PC via REST API HTTPS — 100% tanpa MQTT.

Alur Kerja Otomatis:
1. Kamera menangkap gambar & Plate Recognizer membaca plat.
2. lookup_vehicle() mencocokkan plat dengan database registered_vehicles di Supabase.
3. log_vehicle() mengirimkan data lengkap (Full Data: Plat, Pemilik, Kategori, NIM/NIP, Status, Confidence, Direction) ke vehicle_logs.
"""

import time
import requests
from datetime import datetime
import config


def normalize_plate(plate: str) -> str:
    """Normalisasi plat nomor: hilangkan spasi/simbol dan jadikan huruf kapital."""
    if not plate:
        return ""
    return "".join(c for c in plate if c.isalnum()).upper()


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

        self.registered_cache = []
        self.last_cache_refresh = 0
        self.cache_ttl = 60  # Cache kendaraan terdaftar selama 60 detik

        # Fallback offline data jika Supabase belum dikonfigurasi
        self.fallback_vehicles = [
            {"plate": "B 3782 NHF", "owner_name": "Elkan Baggot", "category": "STUDENT", "nim_nip": "3332200001", "rfid_uid": "0001234567"},
            {"plate": "B 1234 VZN", "owner_name": "Shabrina Zahra", "category": "STUDENT", "nim_nip": "3332200002", "rfid_uid": "0002345678"},
            {"plate": "B 3501 NZN", "owner_name": "Rocky Alfanz", "category": "LECTURER", "nim_nip": "198501012010121001", "rfid_uid": "0003456789"},
            {"plate": "A 9816 XY", "owner_name": "Bundo", "category": "ACADEMIC COMMUNITY", "nim_nip": "199002022015042001", "rfid_uid": "0004567890"},
            {"plate": "A 2145 JZ", "owner_name": "Sohari", "category": "ACADEMIC COMMUNITY", "nim_nip": "199103032016051002", "rfid_uid": "0005678901"}
        ]

        if not self.enabled:
            print("[INFO] Supabase belum aktif (masih URL default). Menggunakan offline fallback matching.")
            return

        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        # Tes koneksi awal dan muat cache kendaraan terdaftar
        try:
            r = requests.get(f"{self.url}/rest/v1/registered_vehicles?select=*&limit=5", headers=self.headers, timeout=5)
            if r.status_code in (200, 206):
                print("[OK] Supabase Cloud Database terhubung!")
                self.refresh_registered_cache()
            else:
                print(f"[WARN] Respon Supabase status {r.status_code}: {r.text[:80]}")
        except Exception as e:
            print(f"[WARN] Belum dapat terhubung ke Supabase: {e}")

    def refresh_registered_cache(self, force: bool = False):
        """
        Sinkronkan daftar registered_vehicles dari Supabase ke memory lokal.
        Membuat pencocokan plat di Raspberry Pi berjalan instan (~0ms).
        """
        if not self.enabled:
            return

        now = time.time()
        if not force and (now - self.last_cache_refresh < self.cache_ttl):
            return

        try:
            url = f"{self.url}/rest/v1/registered_vehicles?select=*"
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                self.registered_cache = res.json()
                self.last_cache_refresh = now
                # print(f"  [CACHE] {len(self.registered_cache)} data kendaraan terdaftar termuat.")
        except Exception as e:
            print(f"  [WARN] Gagal memperbarui cache kendaraan: {e}")

    def lookup_vehicle(self, plate_text: str) -> dict:
        """
        Mencocokkan plat yang terdeteksi OCR dengan data di registered_vehicles.
        Menggunakan normalisasi karakter (mengabaikan spasi dan perbedaan huruf kapital/kecil).
        
        Mengembalikan dictionary lengkap:
        - status: 'TERDAFTAR' atau 'TIDAK TERDAFTAR'
        - owner_name: Nama pemilik terdaftar atau 'Tamu / Belum Terdaftar'
        - category: 'STUDENT', 'LECTURER', atau 'ACADEMIC COMMUNITY'
        - nim_nip: NIM / NIP pemilik atau '-'
        """
        target_norm = normalize_plate(plate_text)
        if not target_norm:
            return {
                "matched": False,
                "plate": plate_text,
                "owner_name": "Tamu / Belum Terdaftar",
                "category": "ACADEMIC COMMUNITY",
                "nim_nip": "-",
                "status": "TIDAK TERDAFTAR"
            }

        # 1. Mode Supabase Aktif
        if self.enabled:
            self.refresh_registered_cache()
            
            # Cari di cache
            for item in self.registered_cache:
                db_norm = normalize_plate(item.get("plate", ""))
                if db_norm == target_norm:
                    return {
                        "matched": True,
                        "plate": item.get("plate", plate_text),
                        "owner_name": item.get("owner_name") or item.get("owner") or "Civitas Untirta",
                        "category": item.get("category", "STUDENT"),
                        "nim_nip": item.get("nim_nip", "-") or "-",
                        "status": "TERDAFTAR"
                    }

            # Jika tidak ada di cache, coba refresh paksa (mungkin baru ditambahkan)
            self.refresh_registered_cache(force=True)
            for item in self.registered_cache:
                db_norm = normalize_plate(item.get("plate", ""))
                if db_norm == target_norm:
                    return {
                        "matched": True,
                        "plate": item.get("plate", plate_text),
                        "owner_name": item.get("owner_name") or item.get("owner") or "Civitas Untirta",
                        "category": item.get("category", "STUDENT"),
                        "nim_nip": item.get("nim_nip", "-") or "-",
                        "status": "TERDAFTAR"
                    }

        # 2. Mode Demo / Fallback Offline
        for item in self.fallback_vehicles:
            fb_norm = normalize_plate(item.get("plate", ""))
            if fb_norm == target_norm:
                return {
                    "matched": True,
                    "plate": item.get("plate", plate_text),
                    "owner_name": item.get("owner_name", "Civitas Untirta"),
                    "category": item.get("category", "STUDENT"),
                    "nim_nip": item.get("nim_nip", "-") or "-",
                    "status": "TERDAFTAR"
                }

        # Plat tidak ditemukan dalam registered_vehicles
        return {
            "matched": False,
            "plate": plate_text.strip().upper(),
            "owner_name": "Tamu / Belum Terdaftar",
            "category": "ACADEMIC COMMUNITY",
            "nim_nip": "-",
            "status": "TIDAK TERDAFTAR"
        }

    def lookup_rfid(self, rfid_uid: str) -> dict:
        """
        Mencocokkan UID kartu RFID dengan tabel registered_vehicles di Supabase.
        """
        clean_uid = str(rfid_uid).strip().upper()
        if not clean_uid:
            return {
                "matched": False,
                "plate": "NO_RFID",
                "owner_name": "Kartu Tidak Valid",
                "category": "ACADEMIC COMMUNITY",
                "nim_nip": "-",
                "status": "TIDAK TERDAFTAR",
                "method": "RFID"
            }

        # 1. Mode Supabase Aktif
        if self.enabled:
            self.refresh_registered_cache()
            for item in self.registered_cache:
                if str(item.get("rfid_uid", "")).strip().upper() == clean_uid:
                    return {
                        "matched": True,
                        "plate": item.get("plate", "RFID_CARD"),
                        "owner_name": item.get("owner_name") or item.get("owner") or "Civitas Untirta",
                        "category": item.get("category", "STUDENT"),
                        "nim_nip": item.get("nim_nip", "-") or "-",
                        "status": "TERDAFTAR",
                        "method": "RFID"
                    }

        # 2. Mode Demo / Fallback Offline
        for item in self.fallback_vehicles:
            if str(item.get("rfid_uid", "")).strip().upper() == clean_uid:
                return {
                    "matched": True,
                    "plate": item.get("plate", "RFID_CARD"),
                    "owner_name": item.get("owner_name", "Civitas Untirta"),
                    "category": item.get("category", "STUDENT"),
                    "nim_nip": item.get("nim_nip", "-") or "-",
                    "status": "TERDAFTAR",
                    "method": "RFID"
                }

        return {
            "matched": False,
            "plate": f"RFID-{clean_uid[:8]}",
            "owner_name": "Kartu Belum Terdaftar",
            "category": "ACADEMIC COMMUNITY",
            "nim_nip": "-",
            "status": "TIDAK TERDAFTAR",
            "method": "RFID"
        }

    def verify_dual_auth(self, plate_text: str, rfid_uid: str) -> dict:
        """
        Verifikasi GANDA: Plat Nomor DAN Kartu RFID KEDUANYA HARUS COCOK
        pada baris kendaraan yang sama di registered_vehicles.
        
        Kondisi:
        1. Plat dan RFID cocok pada kendaraan terdaftar yang sama -> verified = True
        2. Plat terdaftar tetapi RFID tidak cocok -> verified = False, status = 'TIDAK COCOK'
        3. Plat belum terdaftar di sistem -> verified = False, status = 'TIDAK TERDAFTAR'
        """
        target_plate = normalize_plate(plate_text)
        target_rfid = str(rfid_uid or "").strip().upper()

        if not target_plate or not target_rfid:
            return {
                "verified": False,
                "matched": False,
                "plate": plate_text or "UNKNOWN",
                "owner_name": "Tamu / Belum Terdaftar",
                "category": "ACADEMIC COMMUNITY",
                "nim_nip": "-",
                "rfid_uid": target_rfid or "-",
                "status": "TIDAK TERDAFTAR",
                "reason": "PARAM_EMPTY"
            }

        # 1. Cek di Supabase jika aktif
        if self.enabled:
            self.refresh_registered_cache()
            
            matched_row = None
            for item in self.registered_cache:
                if normalize_plate(item.get("plate", "")) == target_plate:
                    matched_row = item
                    break

            if not matched_row:
                self.refresh_registered_cache(force=True)
                for item in self.registered_cache:
                    if normalize_plate(item.get("plate", "")) == target_plate:
                        matched_row = item
                        break

            if matched_row:
                db_rfid = str(matched_row.get("rfid_uid", "")).strip().upper()
                owner = matched_row.get("owner_name") or matched_row.get("owner") or "Civitas Untirta"
                if db_rfid and db_rfid == target_rfid:
                    return {
                        "verified": True,
                        "matched": True,
                        "plate": matched_row.get("plate", plate_text),
                        "owner_name": owner,
                        "category": matched_row.get("category", "STUDENT"),
                        "nim_nip": matched_row.get("nim_nip", "-") or "-",
                        "rfid_uid": db_rfid,
                        "status": "TERDAFTAR",
                        "reason": "MATCH"
                    }
                else:
                    return {
                        "verified": False,
                        "matched": False,
                        "plate": matched_row.get("plate", plate_text),
                        "owner_name": owner,
                        "category": matched_row.get("category", "STUDENT"),
                        "nim_nip": matched_row.get("nim_nip", "-") or "-",
                        "rfid_uid": target_rfid,
                        "status": "TIDAK COCOK",
                        "reason": "RFID_MISMATCH"
                    }

        # 2. Cek di Fallback Data (Mode Demo / Offline)
        for item in self.fallback_vehicles:
            if normalize_plate(item.get("plate", "")) == target_plate:
                db_rfid = str(item.get("rfid_uid", "")).strip().upper()
                if db_rfid and db_rfid == target_rfid:
                    return {
                        "verified": True,
                        "matched": True,
                        "plate": item.get("plate", plate_text),
                        "owner_name": item.get("owner_name", "Civitas Untirta"),
                        "category": item.get("category", "STUDENT"),
                        "nim_nip": item.get("nim_nip", "-") or "-",
                        "rfid_uid": db_rfid,
                        "status": "TERDAFTAR",
                        "reason": "MATCH"
                    }
                else:
                    return {
                        "verified": False,
                        "matched": False,
                        "plate": item.get("plate", plate_text),
                        "owner_name": item.get("owner_name", "Civitas Untirta"),
                        "category": item.get("category", "STUDENT"),
                        "nim_nip": item.get("nim_nip", "-") or "-",
                        "rfid_uid": target_rfid,
                        "status": "TIDAK COCOK",
                        "reason": "RFID_MISMATCH"
                    }

        # Tidak ditemukan
        return {
            "verified": False,
            "matched": False,
            "plate": plate_text.strip().upper(),
            "owner_name": "Tamu / Belum Terdaftar",
            "category": "ACADEMIC COMMUNITY",
            "nim_nip": "-",
            "rfid_uid": target_rfid,
            "status": "TIDAK TERDAFTAR",
            "reason": "UNREGISTERED"
        }

    def log_vehicle(self, plate_text: str, confidence: float = 100.0, region: str = "id", direction: str = None, method: str = "ALPR", custom_info: dict = None) -> dict:
        """
        Mencocokkan plat/RFID ke registered_vehicles dan mengirimkan data LENGKAP ke vehicle_logs.
        Data yang dikirimkan:
        - plate       : Plat terdeteksi / UID kartu
        - name        : Nama pemilik terdaftar (atau Tamu)
        - category    : STUDENT / LECTURER / ACADEMIC COMMUNITY
        - nim_nip     : NIM / NIP civitas
        - status      : TERDAFTAR / TIDAK TERDAFTAR
        - method      : ALPR / RFID / MANUAL
        - direction   : IN / OUT
        - confidence  : Akurasi OCR (%)
        - region      : Kode wilayah
        """
        if direction is None:
            direction = getattr(config, 'GATE_DIRECTION', 'OUT')
        conf_val = round(confidence * 100 if confidence <= 1.0 else confidence, 2)
        
        # 1. COCOKKAN KE REGISTERED VEHICLES (Jika tidak diberikan custom_info)
        info = custom_info or self.lookup_vehicle(plate_text)

        payload = {
            "plate": info["plate"],
            "name": info["owner_name"],
            "category": info["category"],
            "nim_nip": info["nim_nip"],
            "status": info["status"],
            "method": method,
            "direction": direction,
            "confidence": conf_val
        }

        # Tampilkan hasil pencocokan di console RPi
        if info["matched"]:
            print(f"  [MATCHED OK] Terdaftar: {info['plate']} | {info['owner_name']} ({info['category']} - NIM/NIP: {info['nim_nip']}) [{method}]")
        else:
            print(f"  [UNREGISTERED] Tidak Terdaftar: {info['plate']} | Status: {info['status']} [{method}]")

        # 2. KIRIM FULL DATA KE SUPABASE
        if not self.enabled:
            print(f"  [SIMULASI LOCAL] Plat {info['plate']} dicatat secara lokal (Supabase belum diisi di config.py).")
            return payload

        try:
            url = f"{self.url}/rest/v1/vehicle_logs"
            res = requests.post(url, headers=self.headers, json=payload, timeout=6)

            if res.status_code in (200, 201):
                print(f"  [SUPABASE OK] Data terkirim penuh ke vehicle_logs! (Status: {info['status']})")
                return res.json()
            else:
                print(f"  [SUPABASE ERROR] Status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"  [SUPABASE ERROR] Gagal mengirim data ke Supabase: {e}")

        return payload

    def get_pending_gate_command(self) -> dict:
        """
        Cek apakah ada perintah buka gerbang manual dari Web Dashboard via Supabase.
        Mengambil 1 perintah berstatus 'PENDING', lalu mengubah statusnya menjadi 'EXECUTED'.
        """
        if not self.enabled:
            return None

        try:
            url = f"{self.url}/rest/v1/gate_commands?status=eq.PENDING&order=created_at.asc&limit=1"
            res = requests.get(url, headers=self.headers, timeout=3)
            if res.status_code == 200:
                rows = res.json()
                if rows and len(rows) > 0:
                    cmd = rows[0]
                    cmd_id = cmd.get("id")
                    # Update status menjadi EXECUTED
                    patch_url = f"{self.url}/rest/v1/gate_commands?id=eq.{cmd_id}"
                    patch_payload = {
                        "status": "EXECUTED",
                        "executed_at": datetime.now().isoformat()
                    }
                    requests.patch(patch_url, headers=self.headers, json=patch_payload, timeout=3)
                    return cmd
        except Exception:
            pass
        return None

