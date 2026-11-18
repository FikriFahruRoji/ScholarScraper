# Google Scholar Scraper

Aplikasi Streamlit dengan dua mode pengambilan data Google Scholar:

1. **Profil Scholar** — masukkan URL/ID satu profil publik, dapatkan identitas,
   metrik sitasi, riwayat sitasi tahunan, dan daftar artikel.
2. **Cari Kata Kunci** — masukkan topik atau frasa, dapatkan hasil pencarian
   artikel beserta penulis, venue, tahun, sitasi, ringkasan, dan tautan PDF.

Dibangun dengan [Scrapling](https://github.com/D4Vinci/Scrapling) untuk pengambilan
halaman dan [Streamlit](https://streamlit.io) untuk antarmuka.

## Fitur

### Profil Scholar

- Input berupa URL profil Scholar atau ID dari parameter `user=`.
- Validasi ketat: hanya host `scholar.google.*` dan path `/citations` yang diterima.
- Mode **HTTP** cepat dengan impersonasi browser, plus fallback **browser stealth**.
- Deteksi blokir: HTTP 403/429/503, CAPTCHA, halaman `/sorry/`, dan redirect login.
- Parsing tahan-locale: nama, afiliasi, email terverifikasi, homepage, minat riset,
  sitasi, h-index, i10-index, dan metrik 5 tahun terakhir.
- Daftar artikel: judul, penulis, venue, tahun, sitasi, tautan artikel, tautan sitasi,
  dan ID publikasi.
- Filter judul/penulis/venue, sitasi minimal, rentang tahun, serta pengurutan.
- Grafik artikel per tahun dan sitasi baru per tahun.
- Ekspor **CSV**, **Excel** (3 sheet), dan **JSON**.

### Cari Kata Kunci

- Pencarian `/scholar` dengan dukungan frasa persis (`"machine learning"`),
  `author:`, `source:`, dan operator Scholar lain.
- Pilihan 10–100 hasil, **semua halaman** (batas pengaman 1.000 hasil), atau
  **tidak dibatasi** (terus mengambil sampai hasil habis), urutan
  relevansi/tanggal, serta batas rentang tahun.
- **Jeda aman acak per halaman**: 5–12 detik, 12–25 detik, atau jeda manual.
  Tersedia juga batas waktu memuat setiap halaman.
- **Browser stealth** sebagai mode default karena permintaan HTTP biasa dialihkan
  ke halaman verifikasi Google (`sgsync`).
- Deteksi blokir khusus pencarian, termasuk redirect `sgsync` dan halaman
  `Verifying...`.
- Hasil berisi judul, penulis, venue, penerbit, tahun, sitasi, ringkasan, tautan
  artikel, PDF, daftar sitasi, dan semua versi.
- Filter teks, sitasi minimal, rentang tahun, hanya PDF, serta pengurutan.
- Grafik hasil per tahun, venue terbanyak, dan 10 hasil paling banyak disitasi.
- Ekspor **CSV**, **Excel** (2 sheet), dan **JSON**.

## Instalasi

Butuh Python 3.10+ (diuji dengan Python 3.11 dan Scrapling 0.5.1).

```bash
cd scholar-scraper
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> macOS Command Line Tools kadang masih menyediakan `python3` versi 3.9, yang
> tidak didukung Scrapling. Gunakan `python3.11`/`python3.12`, atau jalankan
> `./run.command` yang otomatis mencari interpreter 3.10+.

Browser stealth dibutuhkan untuk pencarian kata kunci dan berguna sebagai fallback
profil. Pasang dengan:

```bash
scrapling install
```

## Menjalankan

```bash
streamlit run app.py
```

Atau di macOS, klik dua kali `run.command` (membuat `.venv` dan memasang dependensi
secara otomatis).

Navigasi halaman tersedia di sidebar: **Profil Scholar** dan **Cari Kata Kunci**.

## Cara pakai

### Profil Scholar

1. Tempel URL profil, misalnya
   `https://scholar.google.com/citations?user=kukA0LcAAAAJ&hl=en`,
   atau ID `kukA0LcAAAAJ`.
2. Pilih bahasa halaman, urutan daftar, jumlah artikel, dan metode pengambilan.
3. Klik **Ambil data artikel**.
4. Filter/urutkan di tab **Artikel**, lihat grafik di **Analitik**, lalu unduh hasilnya.

### Cari Kata Kunci

1. Tulis kata kunci, misalnya `"machine learning" education`.
2. Pilih bahasa, urutan, jumlah hasil (10–100, **Semua halaman**, atau
   **Tidak dibatasi**), rentang tahun, jeda aman, dan batas waktu per halaman.
3. Centang persetujuan, lalu klik **Cari artikel**.
4. Filter hasil, buka detail untuk membaca ringkasan, lalu unduh CSV/Excel/JSON.

## Batas dan kepatuhan

- **Profil: default satu halaman.** Google Scholar mengizinkan `/citations?user=`
  pada `robots.txt`, dan `pagesize=100` memuat hingga 100 artikel dalam satu request.
- **Profil: pagination opt-in.** Halaman berikutnya memakai parameter `cstart`, yang
  saat ini dilarang `robots.txt` (`Disallow: /citations?*cstart=`). Aplikasi hanya
  memakainya jika pengguna mencentang persetujuan secara eksplisit.
- **Pencarian: `/scholar` dilarang `robots.txt`.** Fitur kata kunci memerlukan
  persetujuan eksplisit sebelum berjalan. Gunakan hanya untuk keperluan wajar,
  dalam jumlah terbatas, dan beri jeda antar halaman.
- **Semua halaman tetap dibatasi pengaman.** Opsi “Semua halaman” berhenti setelah
  1.000 hasil. Pilih **“Tidak dibatasi”** untuk terus mengambil halaman sampai
  tombol Next tidak ada atau tidak ada hasil baru; Google Scholar sendiri biasanya
  berhenti memberikan hasil setelah sekitar 1.000 hasil.
- **Jeda aman bukan jaminan bebas blokir.** Jeda acak 5–12/12–25 detik dan batas
  waktu per halaman mengurangi risiko pembatasan, tetapi Google tetap dapat
  meminta CAPTCHA kapan saja.
- **Browser stealth lebih tahan blokir, bukan izin.** Mode ini membantu melewati
  halaman verifikasi otomatis, tetapi tidak mengubah ketentuan layanan Google.
- **Bukan API resmi.** Google Scholar dapat memblokir akses kapan saja. Jika muncul
  CAPTCHA/429, tunggu beberapa menit, coba mode browser, atau ganti jaringan.
- **Angka sitasi** mengikuti Scholar dan tidak setara dengan Scopus/Web of Science.
- Gunakan data secara wajar, hormati ketentuan layanan Google, hak penulis, dan
  ketentuan perlindungan data yang berlaku. Tautan PDF mengarah ke berkas pihak
  ketiga; periksa izin sebelum mengunduh atau menyebarkannya.

## Struktur proyek

```
scholar-scraper/
├── app.py                     # router Streamlit + st.navigation
├── views/
│   ├── profil.py              # halaman profil Scholar
│   └── kata_kunci.py          # halaman pencarian kata kunci
├── scholar_scraper/
│   ├── errors.py              # tipe kesalahan untuk UI
│   ├── models.py              # dataclass profil, artikel, dan hasil pencarian
│   ├── parser.py              # validasi URL + parsing halaman profil
│   ├── search.py              # URL, parsing, dan pengambilan hasil pencarian
│   ├── browser.py             # sesi browser stealth bersama
│   ├── fetcher.py             # Scrapling HTTP/browser, retry, progres
│   ├── export.py              # DataFrame, CSV, Excel, JSON
│   └── ui.py                  # CSS dan helper UI bersama
├── tests/
│   ├── fixtures/profile_page.html
│   ├── fixtures/search_page.html
│   ├── test_parser.py
│   ├── test_fetcher.py
│   ├── test_search.py
│   └── test_export.py
├── requirements.txt
└── run.command
```

## Pengujian

```bash
pip install -r requirements-dev.txt
pytest
```

Tes tidak mengakses jaringan; parsing diuji memakai fixture HTML profil dan hasil
pencarian. Uji manual ke Google Scholar tetap disarankan sebelum pemakaian nyata.

## Catatan teknis

- URL request selalu dibangun ulang dari input yang tervalidasi, sehingga pengguna
  tidak bisa mengarahkan request ke host lain.
- `FetcherSession` dipakai agar cookie/headers konsisten antar halaman.
- Timeout browser Scrapling memakai milidetik; timeout HTTP memakai detik.
- Pencarian memakai offset `start=0,10,20,...` dan berhenti saat tombol **Next**
  tidak aktif atau jumlah hasil yang diminta terpenuhi.
- Mode jeda aman memilih durasi acak untuk setiap perpindahan halaman
  (`random.uniform`), sedangkan mode manual memakai nilai slider.
- Judul hasil membersihkan label `[PDF]`, `[HTML]`, `[BOOK]`, dan sejenisnya.
- Baris `Penulis - Venue, Tahun - Penerbit` dipecah secara toleran karena Google
  Scholar tidak selalu menampilkan semua bagian.
