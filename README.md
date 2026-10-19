# Lomba Aggregator & Validator System (Cakrawala University)

Sistem otomatis pengumpulan dan kurasi lomba untuk kebutuhan publikasi konten media sosial fakultas/school di Cakrawala University.

## Persyaratan Lingkungan
- **Python**: `3.12` (dikunci)

## Struktur Sheet
- **Tab Utama**: `DRAFT` (10 kolom: Scraped At, Judul Lomba, Penyelenggara, Rekomendasi School, Biaya Pendaftaran, Deadline, Link Sumber, Link Pendaftaran, Link Guidebook, Status Review).
- **Tab Sekunder (Opsional)**: `ARCHIVE` (untuk menampung baris lama yang telah Approved/Rejected).
- **Aturan Anti-Bocor**: Baris berstatus `Rejected` tidak boleh dihapus. Seluruh baris pada `DRAFT` dan `ARCHIVE` dibaca oleh sistem untuk deduplikasi.
- **Aturan Multi-School**: Tepat 1 School utama di Kolom D, School sekunder dicatat di log eksekusi.

## Instalasi
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Pengujian Lokal
Uji unit internal:
```bash
python -m unittest test_pipeline.py
```

Uji scraping & klasifikasi tanpa menulis ke Google Sheets (Dry-run):
```bash
python main.py --dry-run --pages 1
```

## Eksekusi Produksi
Pastikan variabel lingkungan telah disetel:
- `SHEET_ID`: ID Google Sheets target.
- `GSPREAD_SERVICE_ACCOUNT_JSON`: Path file JSON atau isi string JSON Service Account Google Cloud.

```bash
python main.py --pages 2
```
