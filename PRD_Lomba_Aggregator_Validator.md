# PRD: Lomba Aggregator & Validator System

**Organisasi:** Cakrawala University
**Versi:** 1.0 (Draft untuk review)
**Status:** Siap development setelah review tim Lomba dan Medsos
**Pemilik Produk:** Tim Lomba
**Pemilik Teknis:** Tim Engineering / Mahasiswa Teknik Informatika

---

## 1. Executive Summary & Project Background

Tim Lomba dan Tim Medsos saat ini mencari info lomba secara manual dari berbagai website, terutama InfoLomba. Proses ini memakan waktu, tidak konsisten, dan sulit memastikan setiap School/Fakultas mendapat konten lomba tiap bulan. Target kampus adalah minimal 1 lomba per School per bulan untuk konten media sosial.

Sistem ini mengotomatiskan lapisan pengumpulan data (*data gathering*). Scraper berjalan terjadwal setiap malam, mengambil info lomba, mengklasifikasikannya ke School yang relevan dengan aturan kata kunci, membuang duplikat, lalu menulis hasilnya ke tab **Draft** di Google Sheets. Tim Lomba tetap memegang keputusan akhir melalui kolom *Status Review*.

Prinsip utama sistem:

- **Gratis 100% (Rp0):** GitHub Actions untuk penjadwalan, Google Sheets sebagai database, library open source.
- **Tanpa AI komersial:** klasifikasi berbasis keyword matching, deterministik, dan bisa diaudit.
- **Human-in-the-loop:** sistem hanya menyiapkan draft. Tidak ada data yang langsung dipublikasikan.

---

## 2. Tujuan dan Non-Goals

### 2.1 Tujuan (Goals)

| ID | Tujuan | Indikator Keberhasilan |
|----|--------|------------------------|
| G1 | Mengotomatiskan pengumpulan info lomba dari sumber publik | Minimal 30 lomba baru masuk per bulan ke tab Draft |
| G2 | Menghilangkan pencarian manual rutin | Waktu kerja manual pencarian turun ≥ 80% (diukur lewat survei tim) |
| G3 | Memastikan coverage konten per School | Setiap School punya ≥ 1 lomba berstatus Approved per bulan |
| G4 | Menjaga kualitas data | Duplikasi di sheet < 1%; field kosong tertangani tanpa crash |
| G5 | Biaya operasional nol | Tagihan bulanan Rp0 |

### 2.2 Non-Goals (di luar scope v1.0)

- Publikasi otomatis ke media sosial.
- Penggunaan LLM, embedding, atau layanan AI berbayar untuk klasifikasi.
- Scraping situs yang membutuhkan login, CAPTCHA, atau API berbayar.
- Dashboard web khusus. Monitoring cukup lewat Google Sheets dan log GitHub Actions.
- Notifikasi real-time (Slack/WhatsApp). Ini masuk roadmap v1.1.
- Verifikasi keabsahan penyelenggara lomba. Tetap dilakukan manual oleh Tim Lomba.

---

## 3. Scope dan Pemetaan School

### 3.1 Pemetaan Kategori Lomba ke School

| Kode | School | Program Studi Cakupan |
|------|--------|-----------------------|
| SEN | School of Engineering and Computer Science | S1 AI, Ilmu Komputer, Sistem Informasi, Sains Data, Teknik Elektro, Teknik Industri, Teknik Lingkungan |
| SBE | School of Business and Economics | S1 Bisnis Digital, Keuangan & Investasi, Manajemen, Akuntansi |
| SCD | School of Communication and Design | S1 DKV, Ilmu Komunikasi |
| SPE | School of Psychology and Education | S1 Psikologi, PGSD |
| SLA | School of Law | S1 Ilmu Hukum |
| UMUM | Lintas kategori | Keagamaan, Olahraga, Esai Umum, E-sports, dan lomba yang tidak masuk kategori di atas |

### 3.2 Aturan Scope

- Sumber data v1.0: InfoLomba (halaman daftar dan halaman detail). Sumber lain ditambahkan lewat konfigurasi, tanpa mengubah logika inti.
- Cakupan geografis: lomba nasional dan internasional. Lomba lokal wilayah tertentu tetap masuk, dengan catatan di kolom Judul.
- Rentang waktu data: lomba dengan deadline di masa depan atau maksimal 7 hari yang lalu.

---

## 4. User Personas

### 4.1 Persona A: Tim Lomba (Penanggung Jawab Kurasi)

- **Profil:** Mahasiswa yang bertugas mencari dan memvalidasi lomba.
- **Kebutuhan:** Daftar lomba yang sudah tersaring per School, lengkap dengan deadline, biaya, dan link. Tidak perlu lagi membuka puluhan situs.
- **Pain point:** Banyak duplikasi, lomba sudah tutup saat ditemukan, dan data tidak konsisten.
- **Interaksi dengan sistem:** Membuka tab Draft setiap pagi, mengubah *Status Review* menjadi Approved atau Rejected, dan mengisi ulang field yang bertanda "Hubungi Penyelenggara" bila perlu.

### 4.2 Persona B: Tim Medsos (Konsumen Konten)

- **Profil:** Mahasiswa yang membuat konten Instagram, TikTok, dan poster kampus.
- **Kebutuhan:** Daftar lomba Approved yang siap diangkat jadi konten, dengan deadline dan link pendaftaran yang valid.
- **Pain point:** Kekurangan ide konten per School, dan deadline yang tidak jelas membuat konten terlambat.
- **Interaksi dengan sistem:** Hanya membaca tab Approved (atau memfilter Status = Approved). Tidak mengedit data mentah.

### 4.3 Persona C: Engineer / Maintainer (Sekunder)

- **Kebutuhan:** Scraper yang mudah dipelihara, log yang jelas saat gagal, dan konfigurasi keyword yang bisa diubah tanpa refactor.

---

## 5. Functional Requirements

Prioritas: **P0** = wajib untuk rilis v1.0, **P1** = penting, **P2** = nice to have.

| ID | Requirement | Prioritas |
|----|-------------|-----------|
| FR-01 | Sistem mengambil daftar lomba dari halaman listing sumber (paginasi ditangani sampai halaman terakhir atau batas maksimal halaman yang dikonfigurasi). | P0 |
| FR-02 | Sistem mengambil halaman detail tiap lomba untuk mengisi penyelenggara, biaya, deadline, link pendaftaran, dan guidebook. | P0 |
| FR-03 | Sistem mengklasifikasikan setiap lomba ke tepat satu School (SEN/SBE/SCD/SPE/SLA/UMUM) menggunakan keyword matching. | P0 |
| FR-04 | Sistem memeriksa duplikasi terhadap data yang sudah ada di sheet sebelum menulis (lihat Bagian 6.3). Duplikat dilewati. | P0 |
| FR-05 | Sistem menulis baris baru ke tab Draft dengan 10 kolom sesuai skema (Bagian 8). | P0 |
| FR-06 | Field kosong diisi nilai fallback (`-` atau `Hubungi Penyelenggara`) tanpa menghentikan eksekusi. | P0 |
| FR-07 | Kolom Status Review default `Pending` untuk setiap baris baru. | P0 |
| FR-08 | Dropdown untuk kolom Rekomendasi School dan Status Review dipasang lewat data validation di Sheets. | P0 |
| FR-09 | Eksekusi terjadwal setiap hari pukul 23:59 WIB via GitHub Actions. | P0 |
| FR-10 | Setiap eksekusi menghasilkan ringkasan log: jumlah data ditemukan, ditulis, duplikat, dan gagal. | P0 |
| FR-11 | Sistem menjalankan validasi tanggal deadline. Lomba dengan deadline yang sudah lewat lebih dari 7 hari tidak ditulis. | P1 |
| FR-12 | Keyword dan konfigurasi sumber disimpan di file terpisah (`config/keywords.yaml` atau `.json`), tidak hardcode di kode. | P1 |
| FR-13 | Mode dry-run (argumen CLI `--dry-run`) untuk menguji scraping dan klasifikasi tanpa menulis ke Sheets. | P1 |
| FR-14 | Sistem menandai lomba yang kemungkinan multi-School dengan catatan di log (bukan di sheet) agar Tim Lomba bisa meninjau. | P2 |
| FR-15 | Sistem mengirim notifikasi kegagalan (misal lewat email GitHub Actions bawaan). | P2 |

---

## 6. System Architecture

### 6.1 Diagram Alur

```
┌────────────────────────┐
│  GitHub Actions        │  cron: 59 16 * * *  (UTC; = 23:59 WIB)
│  .github/workflows/    │
│  main.yml              │
└───────────┬────────────┘
            │ trigger
            ▼
┌────────────────────────┐
│  Python Scraper        │
│  requests + BS4        │
│  ├─ fetch listing      │
│  ├─ fetch detail       │
│  └─ parse fields       │
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│  Normalizer            │  trim, collapse spaces, format tanggal
│  + Fallback Layer      │  isi nilai kosong
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│  Rule-Based Classifier │  keyword matching → School
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│  Deduplicator          │  cek Link Sumber & Judul ternormalisasi
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│  Sheets Writer (gspread)│  batch append ke tab Draft
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│  Google Sheets         │  tab Draft → dibaca Tim Lomba & Tim Medsos
└────────────────────────┘
```

### 6.2 Komponen dan Tanggung Jawab

| Modul | Tanggung Jawab | Input | Output |
|-------|----------------|-------|--------|
| `scraper/` | HTTP request, parsing HTML, ekstraksi raw field | URL sumber | Dict raw per lomba |
| `normalizer/` | Pembersihan teks, parsing tanggal, fallback | Dict raw | Dict bersih |
| `classifier/` | Mapping ke School berdasarkan keyword | Dict bersih + `keywords.yaml` | Dict + field `school` |
| `dedup/` | Membandingkan dengan data eksisting | Dict + snapshot sheet | Dict atau skip |
| `sheets/` | Autentikasi gspread dan batch write | List baris | Konfirmasi tulis |
| `main.py` | Orkestrasi, logging, exit code | Argumen CLI, env | Log ringkasan |

### 6.3 Strategi Deduplikasi & Aturan Anti-Bocor (Anti-Leak)

1. **Aturan Anti-Bocor (Single Source of Truth):**
   - Baris berstatus `Rejected` **TIDAK BOLEH DIHAPUS** oleh Tim Lomba dari spreadsheet agar database deduplikasi tidak bocor/ter-scrape ulang.
   - Sistem wajib membaca seluruh URL yang ada pada tab `DRAFT` (apapun statusnya: `Pending`, `Approved`, `Rejected`).
   - Jika tab `ARCHIVE` ada/digunakan (tempat pemindahan data lama `Approved`/`Rejected`), sistem juga wajib membaca seluruh URL dari tab `ARCHIVE` sebagai basis deduplikasi.
2. **Kunci utama:** `Link Sumber` (dinormalisasi: lowercase host, strip trailing slash, strip query params seperti `utm_*`).
3. **Kunci sekunder:** `Judul Lomba` ternormalisasi (lowercase, hapus tanda baca dan spasi ganda). Dipakai jika link sumber kosong.
4. **Snapshot Memory:** Snapshot URL dan judul dibaca sekali di awal run (`batch_get`) dari tab `DRAFT` (dan `ARCHIVE` bila ada), disimpan di memory set.
5. **Multi-School Policy:** Tepat satu baris per lomba dengan satu School utama di Kolom D (berdasarkan keyword skor tertinggi). Kemunculan School sekunder dicatat pada log runtime terminal/GitHub Actions tanpa membuat baris ganda di sheet.

### 6.4 Logika Klasifikasi (Rule-Based)

**Prinsip:** Case-insensitive substring/word-boundary matching terhadap gabungan `Judul Lomba + Deskripsi + Kategori sumber`.

**Algoritma:**

1. Untuk setiap School, hitung skor = jumlah keyword yang cocok (bobot 2 jika cocok di Judul, 1 jika hanya di Deskripsi).
2. Pilih School dengan skor tertinggi.
3. Jika skor tertinggi = 0, set `UMUM`.
4. Jika ada seri (dua School skor sama), pilih School yang urutan prioritasnya lebih tinggi dalam `keywords.yaml`. Catat di log.
5. Keyword kata umum seperti "design" atau "data" harus dibatasi dengan word-boundary (`\bdesign\b`) agar tidak salah cocok.

**Contoh isi `keywords.yaml` (sebagian):**

```yaml
priority: [SLA, SPE, SCD, SBE, SEN, UMUM]   # urutan tie-break
SEN:
  - "programming"
  - "coding"
  - "machine learning"
  - "artificial intelligence"
  - "robotik"
  - "IoT"
  - "hackathon"
  - "data science"
  - "elektronika"
SBE:
  - "business plan"
  - "bisnis"
  - "entrepreneur"
  - "investasi"
  - "akuntansi"
  - "manajemen"
  - "case competition"
SCD:
  - "desain grafis"
  - "poster"
  - "film"
  - "fotografi"
  - "jurnalistik"
  - "komunikasi"
  - "UI/UX"
SPE:
  - "psikologi"
  - "pendidikan"
  - "guru"
  - "kesehatan mental"
SLA:
  - "moot court"
  - "hukum"
  - "debat hukum"
  - "esai hukum"
UMUM:
  - "keagamaan"
  - "MTQ"
  - "olahraga"
  - "e-sports"
  - "esai"
```

> **Catatan:** Daftar ini adalah titik awal. Keyword perlu dikalibrasi dengan 2–3 minggu data nyata. Lomba yang salah klasifikasi dikoreksi manual oleh Tim Lomba, lalu keyword diperbarui.

---

## 7. Technical Requirements

### 7.1 Stack

| Komponen | Pilihan | Alasan |
|----------|---------|--------|
| Bahasa | Python 3.12 (dikunci) | Kompatibilitas GitHub Actions runner & gspread terbaru |
| HTTP | `requests` | Ringan, cukup untuk HTML statis |
| Parsing | `BeautifulSoup4` (parser `lxml`) | Cepat dan toleran terhadap HTML rusak |
| Sheets | `gspread` + service account | Akses programatik tanpa login interaktif |
| Config | `PyYAML` | Keyword dan sumber mudah diubah |
| Scheduler | GitHub Actions (`schedule` + `workflow_dispatch`) | Gratis untuk repo publik; kuota cukup untuk repo privat |
| Secrets | GitHub Secrets (`GSPREAD_SERVICE_ACCOUNT_JSON`, `SHEET_ID`) | Kredensial tidak masuk repo |

### 7.2 Konfigurasi GitHub Actions

- File: `.github/workflows/main.yml`
- Jadwal: `cron: '59 16 * * *'`. GitHub Actions memakai UTC, sehingga 23:59 WIB (UTC+7) sama dengan 16:59 UTC.
- Tambahkan `workflow_dispatch` agar bisa dijalankan manual saat debugging.
- Set `timeout-minutes: 15` untuk mencegah job menggantung.
- Set `concurrency` group agar dua eksekusi tidak menulis bersamaan.

### 7.3 Etika dan Kepatuhan Scraping

- Cek `robots.txt` sumber sebelum development. Jika path tertentu di-disallow, path tersebut tidak di-scrape.
- Cek Terms of Service sumber. Jika scraping dilarang, Tim Lomba harus memutuskan apakah tetap lanjut atau mencari sumber alternatif. Keputusan ini harus didokumentasikan sebelum rilis.
- Gunakan `User-Agent` yang jelas, misalnya `CakrawalaLombaBot/1.0 (contact: tim-lomba@domain)`.
- Rate limit: jeda minimal 2 detik antar request. Maksimal sekitar 100 request per eksekusi.
- Tidak menyimpan salinan konten penuh (guidebook atau deskripsi panjang). Hanya field yang ada di skema yang ditulis.
- Setiap sumber punya `enabled: true/false` di konfigurasi agar bisa dimatikan cepat jika ada masalah.

### 7.4 Anti-Crash Layer dan Error Handling

| Skenario | Penanganan |
|----------|------------|
| Field kosong (penyelenggara, biaya, link guidebook) | Isi `-` atau `Hubungi Penyelenggara` sesuai aturan kolom |
| Deadline tidak bisa diparse | Isi `-`, tandai di log, lomba tetap ditulis dengan status Pending |
| Halaman detail 404 atau timeout | Retry 2 kali dengan backoff (2s, 5s). Jika tetap gagal, catat di log dan lanjut ke lomba berikutnya |
| HTML berubah struktur (selector tidak ketemu) | Fallback selector; jika tetap gagal, eksekusi sumber tersebut dihentikan dan log menandai "parser error" |
| Rate limit atau HTTP 429 | Hormati header `Retry-After`; jika tidak ada, tunggu 30 detik lalu retry satu kali |
| Google Sheets API quota (429) | Batch write (maksimal 100 baris per call), backoff eksponensial |
| Kredensial tidak valid | Gagal cepat dengan pesan jelas. Exit code non-zero agar GitHub Actions menandai run gagal |
| Encoding karakter (emoji, huruf non-latin) | Paksa UTF-8 pada response dan write |
| Pemisah tanggal bermacam format (`10 Oktober 2026`, `10-10-2026`, `2026/10/10`) | Parser dengan daftar format yang dikenal; nama bulan Indonesia dipetakan manual |
| Duplikat di dalam satu batch | Dedup internal sebelum write, bukan hanya terhadap sheet |
| Sumber mengembalikan 0 lomba | Dianggap warning, bukan error. Log menandai kemungkinan perubahan struktur |

**Prinsip:** Satu lomba yang gagal tidak boleh menggagalkan seluruh batch. Error per item dicatat, lalu proses dilanjutkan.

### 7.5 Konfigurasi dan Secrets

- Semua nilai yang bisa berubah (URL sumber, jumlah halaman maksimal, nama tab, keyword) ada di `config/`.
- Kredensial hanya lewat environment variable.
- File `.env` untuk pengembangan lokal masuk ke `.gitignore`.

### 7.6 Logging

- Format log: `[timestamp WIB] [level] [modul] pesan`.
- Ringkasan akhir wajib memuat: total ditemukan, total ditulis, total duplikat, total skip, total error, dan durasi.
- Log disimpan sebagai artifact GitHub Actions selama 14 hari.

---

## 8. Data Schema dan Struktur Sheet

### 8.1 Tab DRAFT: 10 Kolom

Sistem menggunakan 1 tab utama bernama `DRAFT`. Tab sekunder opsional: `ARCHIVE` (hanya jika tim memindahkan row lama, tetap dibaca deduplicator).

| No | Nama Kolom | Tipe | Format / Aturan | Contoh | Nilai Fallback |
|----|------------|------|-----------------|--------|----------------|
| A | Scraped At | Datetime (teks) | `DD/MM/YYYY HH:mm`, zona WIB | `19/10/2026 23:59` | Tidak pernah kosong |
| B | Judul Lomba | Teks | Dibersihkan (trim, spasi ganda dihapus) | `National Data Hackathon 2026` | `-` |
| C | Penyelenggara | Teks | Nama organisasi | `Kemenkominfo` | `Hubungi Penyelenggara` |
| D | Rekomendasi School | Dropdown | `SEN`, `SBE`, `SCD`, `SPE`, `SLA`, `UMUM` (School utama skor tertinggi) | `SEN` | `UMUM` |
| E | Biaya Pendaftaran | Teks | Tulis apa adanya, misal `Gratis` atau `Rp150.000` | `Rp150.000` | `Hubungi Penyelenggara` |
| F | Deadline | Tanggal (teks) | `YYYY-MM-DD` | `2026-11-15` | `-` |
| G | Link Sumber | URL | URL halaman detail di sumber, sudah dinormalisasi | `https://...` | `-` |
| H | Link Pendaftaran | URL | URL form atau halaman daftar | `https://...` | `Hubungi Penyelenggara` |
| I | Link Guidebook | URL | URL file atau halaman panduan | `https://...` | `-` |
| J | Status Review | Dropdown | `Pending` (default), `Approved`, `Rejected` (Anti-Bocor: Rejected dilarang dihapus) | `Pending` | `Pending` |

### 8.2 Catatan Teknis Skema

- **Kolom A dan F disimpan sebagai teks**, bukan tanggal native Sheets. Alasannya: format yang diminta spesifik, dan Sheets bisa mengubah format otomatis. Pada `gspread`, gunakan `value_input_option='RAW'` agar string tidak diinterpretasi ulang.
- **Dropdown (D dan J)** dipasang sekali lewat data validation, bukan ditulis ulang setiap eksekusi.
- **Kolom J** hanya boleh diubah oleh Tim Lomba. Sistem tidak pernah menimpa nilai J pada baris yang sudah ada. Proteksi kolom J dengan *protected range* di Sheets.
- **Urutan kolom tidak boleh diubah.** Writer memakai indeks kolom, bukan nama header. Tambahkan validasi saat startup: header baris 1 harus cocok dengan skema. Jika tidak cocok, eksekusi berhenti.

### 8.3 Tab Pendukung (Opsional, P1)

| Tab | Isi | Fungsi |
|-----|-----|--------|
| `Log` | Ringkasan tiap eksekusi | Audit dan monitoring |
| `Coverage` | Hitungan lomba Approved per School per bulan | Mengawasi target minimal 1 lomba per School |
| `Config` | Daftar keyword (read-only, sinkronisasi dari YAML) | Referensi Tim Lomba |

**Rumus Coverage (contoh, di tab `Coverage`):**

```
=COUNTIFS(Draft!$D:$D, "SEN", Draft!$J:$J, "Approved", Draft!$F:$F, ">="&DATE(2026,10,1), Draft!$F:$F, "<="&DATE(2026,10,31))
```

Catatan: kolom F bertipe teks `YYYY-MM-DD`, jadi perbandingan tanggal di atas perlu `DATEVALUE` atau kolom bantu. Pastikan rumus diuji dengan data nyata sebelum dipakai.

---

## 9. Non-Functional Requirements

| Kategori | Requirement |
|----------|-------------|
| Biaya | Rp0 per bulan. Tidak ada layanan berbayar. |
| Keandalan | Target tingkat keberhasilan eksekusi harian ≥ 90% (dihitung dari run GitHub Actions). |
| Durasi | Satu eksekusi penuh selesai dalam ≤ 10 menit. |
| Keamanan | Kredensial hanya di GitHub Secrets. Service account hanya diberi akses edit ke satu spreadsheet. |
| Pemeliharaan | Penambahan sumber atau keyword tidak memerlukan perubahan kode. |
| Auditabilitas | Setiap keputusan klasifikasi bisa ditelusuri dari log (keyword apa yang cocok, skor berapa). |
| Portabilitas | Kode bisa dijalankan lokal dengan `python main.py --dry-run` tanpa akses ke Sheets. |

---

## 10. Testing

| Jenis | Cakupan | Metode |
|-------|---------|--------|
| Unit test | Normalizer, parser tanggal, deduplicator, classifier | `pytest` dengan fixture HTML sampel |
| Snapshot test | Parser terhadap HTML sumber yang disimpan | Simpan 5–10 halaman sampel di `tests/fixtures/` |
| Integrasi | Alur end-to-end dengan sheet uji | Spreadsheet terpisah sebagai staging |
| Dry-run | Scraping nyata tanpa tulis | `--dry-run`, cek hasil klasifikasi manual |
| Akurasi klasifikasi | Rasio klasifikasi benar | Tim Lomba menilai 50 sampel acak; target ≥ 80% benar pada rilis pertama |

---

## 11. Risks dan Mitigasi

| Risiko | Dampak | Mitigasi |
|--------|--------|----------|
| Struktur HTML sumber berubah | Scraper berhenti mengambil data | Fallback selector, alert log, snapshot test untuk deteksi dini |
| Sumber memblokir IP GitHub Actions | Tidak ada data masuk | Rate limit yang sopan; siapkan sumber alternatif; jika perlu, jalankan dari mesin lokal sebagai cadangan |
| Scraping melanggar ToS | Risiko reputasi dan hukum | Cek ToS sebelum rilis; keputusan didokumentasikan |
| Keyword salah klasifikasi | Tim Medsos mengambil lomba yang tidak relevan | Human review di kolom Status; kalibrasi keyword rutin |
| Kuota Google Sheets API terlampaui | Penulisan gagal | Batch write; snapshot dedup di memori |
| Kolom Sheet diubah manual | Writer salah menulis | Validasi header saat startup; protected range |
| Lomba sudah tutup saat masuk Draft | Konten tidak bisa dipakai | Validasi deadline (FR-11); Tim Lomba cek ulang sebelum Approve |
| Kredensial bocor | Akses sheet tidak sah | Secrets, service account terbatas, rotasi berkala |

---

## 12. Timeline dan Next Steps

Estimasi untuk satu engineer paruh waktu. Durasi dapat disesuaikan.

| Fase | Durasi | Deliverable | Exit Criteria |
|------|--------|-------------|---------------|
| **Sprint 0: Setup dan Validasi** | 1 minggu | Repo, service account, spreadsheet staging, pengecekan robots.txt dan ToS, keputusan sumber | Keputusan sumber disetujui Tim Lomba |
| **Sprint 1: Scraper MVP** | 1–2 minggu | Fetch listing dan detail, parsing 10 field, dry-run | Dry-run menghasilkan data untuk ≥ 90% lomba di halaman uji |
| **Sprint 2: Normalizer, Classifier, Dedup** | 1–2 minggu | Fallback layer, `keywords.yaml`, dedup dua kunci, unit test | Akurasi klasifikasi ≥ 80% pada sampel 50 lomba |
| **Sprint 3: Sheets Writer dan Validasi Skema** | 1 minggu | gspread writer, batch write, data validation, protected range, tab Coverage | Penulisan ke staging tanpa duplikat dan tanpa merusak kolom J |
| **Sprint 4: Otomasi dan Monitoring** | 1 minggu | GitHub Actions, secrets, log artifact, notifikasi kegagalan | 5 hari berturut-turut berjalan tanpa intervensi manual |
| **Sprint 5: UAT dan Rilis** | 1 minggu | Pelatihan singkat Tim Lomba dan Tim Medsos, dokumentasi README | Tim Lomba menyetujui draft pertama; go-live |

### 12.1 Langkah Konkret Minggu Pertama

1. Tim Lomba memberikan daftar 3–5 sumber prioritas dan contoh 20 lomba yang sudah pernah dikurasi manual (untuk kalibrasi keyword).
2. Engineer memeriksa `robots.txt` dan ToS InfoLomba. Hasilnya dicatat di dokumen keputusan.
3. Buat repo dan spreadsheet staging. Pasang header 10 kolom sesuai Bagian 8.
4. Buat service account Google Cloud (gratis) dan bagikan akses edit ke spreadsheet staging.
5. Tulis scraper untuk satu halaman listing dan satu halaman detail sebagai proof of concept.

### 12.2 Pertanyaan Terbuka (Perlu Keputusan Sebelum Sprint 1)

1. **Multi-School:** Jika satu lomba relevan untuk dua School (misal lomba desain UI untuk SEN dan SCD), apakah cukup satu School utama, atau perlu baris duplikat per School? Usulan: satu baris dengan School utama, dan School lain dicatat di log.
2. **Sumber kedua:** Apakah ada sumber lain selain InfoLomba yang wajib masuk v1.0?
3. **Retensi:** Berapa lama lomba Rejected disimpan di sheet? Usulan: dipindah ke tab `Arsip` setiap akhir bulan.
4. **Lomba berbayar:** Apakah lomba dengan biaya di atas nominal tertentu perlu ditandai khusus untuk Tim Medsos?
5. **Repo:** Publik atau privat? Ini memengaruhi kuota GitHub Actions dan kebijakan secrets.

---

## 13. Definition of Done (v1.0)

- [ ] Scraper berjalan di GitHub Actions setiap hari pukul 23:59 WIB tanpa intervensi selama 2 minggu.
- [ ] Semua 10 kolom terisi atau berisi fallback. Tidak ada sel kosong.
- [ ] Dedup terbukti: tidak ada Link Sumber yang muncul dua kali di tab Draft.
- [ ] Dropdown D dan J berfungsi. Kolom J terlindungi dari overwrite sistem.
- [ ] Dokumentasi README mencakup cara setup, cara menambah sumber, dan cara mengubah keyword.
- [ ] Keputusan etika scraping sudah didokumentasikan.
- [ ] Tim Lomba dan Tim Medsos sudah dilatih dan menyetujui alur kerja.
