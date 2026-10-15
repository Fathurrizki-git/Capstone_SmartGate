-- ============================================================
-- SKEMA DATABASE SMART PARKING GATE FT UNTIRTA (SUPABASE SQL)
-- Salin dan jalankan script ini di SQL Editor pada Dashboard Supabase Anda
-- ============================================================

-- 1. TABEL USERS (Daftar Akun Pengguna / Admin / Petugas)
CREATE TABLE IF NOT EXISTS public.users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'Petugas Gerbang',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. TABEL REGISTERED VEHICLES (Daftar Kendaraan Civitas Akademika Terdaftar)
CREATE TABLE IF NOT EXISTS public.registered_vehicles (
    id BIGSERIAL PRIMARY KEY,
    plate VARCHAR(20) UNIQUE NOT NULL,
    owner_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('STUDENT', 'LECTURER', 'ACADEMIC COMMUNITY')),
    nim_nip VARCHAR(50),
    rfid_uid VARCHAR(50) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. TABEL VEHICLE LOGS (Riwayat Deteksi Masuk/Keluar Gerbang oleh Raspberry Pi 3B+)
CREATE TABLE IF NOT EXISTS public.vehicle_logs (
    id BIGSERIAL PRIMARY KEY,
    plate VARCHAR(20) NOT NULL,
    name VARCHAR(100) DEFAULT 'Civitas Untirta',
    category VARCHAR(50) DEFAULT 'STUDENT',
    nim_nip VARCHAR(50) DEFAULT '-',
    status VARCHAR(50) DEFAULT 'TERDAFTAR',
    method VARCHAR(20) DEFAULT 'ALPR', -- 'ALPR', 'RFID', 'MANUAL'
    direction VARCHAR(10) DEFAULT 'IN',
    confidence NUMERIC(5, 2) DEFAULT 90.00,
    region VARCHAR(20) DEFAULT 'id',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. TABEL GATE COMMANDS (Perintah Buka Gerbang Jarak Jauh via Web Dashboard)
CREATE TABLE IF NOT EXISTS public.gate_commands (
    id BIGSERIAL PRIMARY KEY,
    command VARCHAR(50) NOT NULL DEFAULT 'OPEN_GATE',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'EXECUTED', 'CANCELLED'
    operator_name VARCHAR(100) DEFAULT 'Petugas',
    reason VARCHAR(255) DEFAULT 'Buka Gerbang Manual via Web Dashboard',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ
);

-- ============================================================
-- KEBIJAKAN AKSES (ROW LEVEL SECURITY / RLS)
-- Izinkan akses baca dan tulis untuk REST API bawaan Supabase
-- ============================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.registered_vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicle_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gate_commands ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read users" ON public.users FOR SELECT USING (true);
CREATE POLICY "Allow public insert users" ON public.users FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public delete users" ON public.users FOR DELETE USING (true);

CREATE POLICY "Allow public read registered_vehicles" ON public.registered_vehicles FOR SELECT USING (true);
CREATE POLICY "Allow public insert registered_vehicles" ON public.registered_vehicles FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update registered_vehicles" ON public.registered_vehicles FOR UPDATE USING (true);
CREATE POLICY "Allow public delete registered_vehicles" ON public.registered_vehicles FOR DELETE USING (true);

CREATE POLICY "Allow public read vehicle_logs" ON public.vehicle_logs FOR SELECT USING (true);
CREATE POLICY "Allow public insert vehicle_logs" ON public.vehicle_logs FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public delete vehicle_logs" ON public.vehicle_logs FOR DELETE USING (true);

CREATE POLICY "Allow public read gate_commands" ON public.gate_commands FOR SELECT USING (true);
CREATE POLICY "Allow public insert gate_commands" ON public.gate_commands FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update gate_commands" ON public.gate_commands FOR UPDATE USING (true);
CREATE POLICY "Allow public delete gate_commands" ON public.gate_commands FOR DELETE USING (true);

-- Aktifkan Realtime Replication untuk tabel vehicle_logs dan gate_commands
ALTER PUBLICATION supabase_realtime ADD TABLE public.vehicle_logs;
ALTER PUBLICATION supabase_realtime ADD TABLE public.gate_commands;

-- ============================================================
-- DATA CONTOH AWAL (SEED DATA)
-- ============================================================

-- Akun Login Awal
INSERT INTO public.users (name, email, password, role) VALUES
('Fathurrizki', 'admin@untirta.ac.id', 'admin123', 'Admin'),
('Budi Santoso', 'petugas@untirta.ac.id', 'petugas123', 'Petugas Gerbang'),
('Siti Rahma', 'operator@untirta.ac.id', 'operator123', 'Operator')
ON CONFLICT (email) DO NOTHING;

-- Contoh Kendaraan Civitas Terdaftar (Plat & RFID UID)
INSERT INTO public.registered_vehicles (plate, owner_name, category, nim_nip, rfid_uid) VALUES
('B 3782 NHF', 'Elkan Baggot', 'STUDENT', '3332200001', '0001234567'),
('B 1234 VZN', 'Shabrina Zahra', 'STUDENT', '3332200002', '0002345678'),
('B 3501 NZN', 'Rocky Alfanz', 'LECTURER', '198501012010121001', '0003456789'),
('A 9816 XY', 'Bundo', 'ACADEMIC COMMUNITY', '199002022015042001', '0004567890'),
('A 2145 JZ', 'Sohari', 'ACADEMIC COMMUNITY', '199103032016051002', '0005678901')
ON CONFLICT (plate) DO NOTHING;
