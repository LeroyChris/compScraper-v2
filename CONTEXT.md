# Domain Glossary: Lomba Aggregator & Validator

Organisasi: Cakrawala University

## School
Fakultas atau unit akademik target publikasi lomba.
- **SEN**: School of Engineering and Computer Science (AI, CS, SI, Data Science, Elektro, Industri, Lingkungan).
- **SBE**: School of Business and Economics (Bisnis Digital, Keuangan, Manajemen, Akuntansi).
- **SCD**: School of Communication and Design (DKV, Ilmu Komunikasi).
- **SPE**: School of Psychology and Education (Psikologi, PGSD).
- **SLA**: School of Law (Ilmu Hukum).
- **UMUM**: Lintas kategori (Keagamaan, Olahraga, Esai Umum, E-sports, non-spesifik).

Bobot keyword per School ada di `data/keywords.json`. Tepat 1 School utama
per baris (skor tertinggi); School sekunder hanya dicatat di log.

## Confidence
Skor 0.00–1.00 di kolom `Confidence` = **blacklist**: makin kecil, makin perlu
ditinjau manual oleh Tim Lomba. Ambang: ≥ 0.85 `AUTO_APPROVE`, ≥ 0.50
`PERLU_REVIEW`, di bawahnya `MANUAL_CHECK`.

## Status Review
Status yang ditulis scraper di kolom `Status Review`:
- **AUTO_APPROVE**: keyword kuat, aman langsung dipindahkan Tim Medsos.
- **PERLU_REVIEW**: kemungkinan besar relevan, perludicek cepat.
- **MANUAL_CHECK**: tidak ada keyword yang cocok, wajib diperiksa manusia.

Status kurasi manusia (diisi lewat `scripts/Code.gs`):
- **Approved**: baris dipindahkan ke tab `Master Data Lomba`.
- **Rejected**: baris dipindahkan ke tab `Arsip Reject`.

## Sheet Tabs
- **Tab Audit**: inbox hasil scrape, 15 kolom. Satu-satunya tab yang ditulis scraper.
- **Master Data Lomba**: baris Approved, sumber draft konten medsos.
- **Arsip Reject**: baris Rejected, tetap dibaca deduplicator.

## Primary School Rule
Aturan penugasan tepat 1 School utama pada kolom `Rekomendasi School` per lomba
berdasarkan skor bobot kata kunci tertinggi. Kemunculan School sekunder dicatat
pada log eksekusi, tanpa menduplikasi baris.

## Anti-Leak Deduplication
Mekanisme pemeriksaan seluruh URL sumber (`URL Sumber`) dari **seluruh tab**
(`Tab Audit`, `Master Data Lomba`, `Arsip Reject`, dan tab lain) tanpa
memekauli status review, sebelum data baru ditulis ke sheet. Kunci sekunder:
`Judul Lomba` ternormalisasi + `Deadline` (toleransi ±4 jam).

## Deadline
Tanggal **batas akhir pendaftaran** (bukan tanggal acara). Format `YYYY-MM-DD`.
Lomba yang deadline-nya sudah lewat tidak ditulis (`DEADLINE_GRACE_DAYS` untuk
toleransi). Deadline `-` berarti sumber tidak menyebut batas pendaftaran —
kolom itu wajib diisi manual sebelum konten dibuat.
