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

## Status Review
Status kurasi manual oleh Tim Lomba pada kolom `Status Review`:
- **Pending**: Status bawaan data baru hasil scraping.
- **Approved**: Lomba disetujui untuk dijadikan konten medsos.
- **Rejected**: Lomba ditolak (tidak layak / expired / duplikat manual). Baris rejected TIDAK BOLEH dihapus demi integritas deduplikasi.

## Sheet Tabs
- **DRAFT**: Tab utama penulisan hasil scrape dan kurasi aktif.
- **ARCHIVE**: Tab opsional untuk menampung baris Approved/Rejected lama; tetap dibaca oleh deduplicator agar URL tidak ter-scrape ulang.

## Primary School Rule
Aturan penugasan tepat 1 School utama pada kolom D (Rekomendasi School) per lomba berdasarkan skor bobot kata kunci tertinggi. Kemunculan School sekunder dicatat pada log eksekusi, tanpa menduplikasi baris.

## Anti-Leak Deduplication
Mekanisme pemeriksaan seluruh URL sumber (`Link Sumber`) dari seluruh tab (`DRAFT` dan `ARCHIVE`) tanpa memandang status review (Pending, Approved, maupun Rejected) sebelum data baru ditulis ke sheet.
