# Attendance API

Aplikasi API presensi sederhana berbasis FastAPI dengan PostgreSQL, autentikasi JWT, dan dukungan soft delete.

## Cara Menjalankan Aplikasi

### 1. Jalankan melalui Docker Compose
```bash
docker compose up --build
```

Aplikasi akan berjalan di:
- API: http://localhost:8080
- Dokumentasi Swagger: http://localhost:8080/docs

### 2. Login untuk mendapatkan token JWT
Endpoint login tersedia di:
```http
POST /login
```

Token yang diterima kemudian digunakan pada endpoint lain dengan header:
```http
Authorization: Bearer <token>
```

### 3. Menjalankan unit test
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql://myuser:mysecretpassword@localhost:5432/techtest_db'
export JWT_SECRET_KEY='inirahasia46'
python -m pytest -q tests/test_main.py
```

## Teknologi yang Digunakan

- FastAPI: framework API modern dan cepat
- SQLAlchemy: ORM untuk interaksi database
- PostgreSQL: database relasional untuk menyimpan data presensi
- JWT (PyJWT): autentikasi token untuk melindungi endpoint
- Docker Compose: menjalankan aplikasi dan database dalam container terpisah
- Pytest: pengujian unit untuk endpoint utama
- python-dotenv: memuat konfigurasi environment dari file .env

## Struktur Folder

```text
.
├── app/
│   ├── __init__.py
│   ├── database.py      # koneksi database dan inisialisasi schema
│   ├── init.sql         # skema tabel dan data awal
│   └── main.py          # routing API, auth, validasi, dan logika bisnis
├── tests/
│   ├── conftest.py      # konfigurasi test dan env
│   └── test_main.py     # unit test untuk API
├── docker-compose.yml   # konfigurasi service web dan database
├── Dockerfile           # image aplikasi Python
├── requirements.txt     # dependency Python
├── .env                 # konfigurasi environment
└── README.md            # dokumentasi proyek
```

## Penjelasan Desain Aplikasi

Aplikasi ini dirancang sebagai backend presensi dengan arsitektur sederhana namun terstruktur:

- Layer API: semua endpoint disimpan di app/main.py.
- Layer Database: koneksi dan inisialisasi database di app/database.py.
- Layer Schema: struktur tabel dan seed data didefinisikan di app/init.sql.

Fitur utama yang tersedia:
- Login untuk menghasilkan JWT
- Pencatatan presensi baru atau update presensi harian
- Melihat detail presensi berdasarkan ID
- Mengubah data presensi
- Menghapus presensi secara soft delete
- Mencari presensi berdasarkan status, tanggal, dan nama karyawan

Desain ini memisahkan logika routing, akses data, dan inisialisasi database sehingga lebih mudah dikembangkan dan diuji.

## Kendala yang Ditemui

Beberapa kendala yang muncul selama pengembangan antara lain:

1. Schema database berubah setelah aplikasi berjalan.
   - Awalnya kolom deleted_at belum ada, sehingga perlu ditambahkan melalui mekanisme alter table agar soft delete dapat bekerja.

2. Koneksi database berbeda antara container dan lokal.
   - Saat aplikasi dijalankan di Docker, host database yang dipakai adalah db.
   - Saat test dijalankan lokal, perlu menggunakan localhost agar dapat terhubung ke container PostgreSQL.

3. Autentikasi JWT perlu diterapkan secara konsisten.
   - Middleware dibuat agar endpoint tertentu tidak memerlukan token, sementara endpoint presensi tetap terlindungi.

4. Data presensi harus aman dari duplikasi.
   - Perlu adanya aturan unik pada kombinasi employee_id dan attendance_date untuk mencegah data ganda per karyawan per hari.

## Alasan Pemilihan Tipe Data

Pemilihan tipe data dibuat agar data presensi lebih konsisten dan sesuai dengan makna nilainya:

- date untuk attendance_date: karena nilai presensi merepresentasikan tanggal, bukan waktu.
- time untuk check_in dan check_out: karena jam masuk dan pulang adalah nilai waktu.
- VARCHAR untuk nama karyawan dan catatan: cukup untuk menyimpan teks singkat.
- TIMESTAMP WITH TIME ZONE untuk created_at, updated_at, dan deleted_at: agar pencatatan waktu lebih akurat dan tidak bergantung zona waktu lokal.
- ENUM attendance_status: membuat status presensi terbatas pada nilai yang sudah ditentukan, misalnya Present, Sick, Leave, dan Absent.

## Cara Mencegah Data Presensi Ganda

Untuk mencegah data presensi ganda, digunakan constraint unik pada kombinasi:

```sql
UNIQUE (employee_id, attendance_date)
```

Artinya, satu karyawan hanya boleh memiliki satu data presensi per tanggal. Saat endpoint create dipanggil untuk tanggal yang sama, sistem akan melakukan update data yang sudah ada, bukan menambahkan entri baru. Hal ini mencegah duplikasi dan menjaga integritas data.
