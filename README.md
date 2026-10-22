# Lomba Aggregator & Validator System (Cakrawala University)

Sistem otomatis pengumpulan info lomba dari beberapa portal publik, dikurasi di
Google Sheets, lalu dipakai Tim Medsos untuk membuat konten.

```
GitHub Actions (harian 23:59 WIB)
  -> scrape semua sumber
  -> normalisasi + validasi (pydantic)
  -> klasifikasi School (keyword) + filter noise
  -> dedup terhadap SELURUH tab sheet (anti-leak)
  -> append ke tab "Tab Audit"
  -> manusia approve/reject lewat menu Apps Script (scripts/Code.gs)
```

## Sheet

Spreadsheet ID ada di `.env` (`SHEET_ID`). Tab yang dipakai:

| Tab | Isi | Who |
|-----|-----|-----|
| `Tab Audit` | inbox hasil scrape (15 kolom) | ditulis scraper, dibaca Tim Lomba |
| `Master Data Lomba` | baris yang sudah disetujui | Tim Medsos (draft konten IG) |
| `Arsip Reject` | baris yang ditolak | disimpan, tidak pernah dihapus |

Anti-leak: **semua tab** dibaca sebelum menulis (URL Sumber + Judul + Deadline),
apa pun statusnya. Baris reject tidak boleh dihapus manual.

### Skema 15 kolom (`Tab Audit`)

`ID`, `Judul Lomba`, `Penyelenggara`, `Lokasi`, `Sasaran`, `Biaya`, `Deadline`,
`Rekomendasi School`, `Confidence`, `Status Review`, `Link Pendaftaran`,
`Link Panduan`, `URL Sumber`, `Deskripsi Singkat`, `Tanggal Scrape`

Kolom wajib dari brief: `Penyelenggara`, `Judul Lomba`, `Biaya`,
`Link Pendaftaran`, `Deadline`. `Confidence` = blacklist (semakin kecil, semakin
perlu ditinjau manual).

`Status Review`: `AUTO_APPROVE` / `PERLU_REVIEW` / `MANUAL_CHECK`.

## Sumber

| id | sumber | cara ambil data |
|----|--------|-----------------|
| `infolomba` | infolomba.id | list SSR + POST `/load-event-2` (size 5) + `/load-details` |
| `luarkampus` | luarkampus.id | kartu event di list `?page=N` (detail butuh login) |
| `puspresnas` | pusatprestasinasional.kemendikdasmen.go.id | JSON di atribut `data-page` |
| `infolombait` | infolombait.com | Blogger, artikel bebas |
| `informasilomba` | informasilomba.com | sitemap + artikel bebas |
| `logikaui` | logikaui.id | portal `/competitions/` |

Artikel bebas (3 sumber terakhir) diisi lewat heuristik; **Gemini** dipakai
sebagai fallback opsional bila `GEMINI_API_KEY` diset (tidak wajib).

Sumber yang sengaja dilewati: UNPAD / UGM DRA / ITB (Cloudflare / wp-json 401).

## Instalasi

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # isi SHEET_ID + GOOGLE_SERVICE_ACCOUNT_FILE
```

`service_account.json` (service account Google Cloud) harus ada dan spreadsheet
harus di-share ke akun service account tersebut.

## Menjalankan

```bash
python main.py                          # production: tulis ke Tab Audit
python main.py --dry-run                # scrape tanpa menulis, print JSON
python main.py --source infolomba --limit 5 --dry-run
python main.py --limit 10               # batasi jumlah item per sumber
```

Argumen: `--limit` (item per sumber, default `MAX_ITEMS_PER_RUN`), `--source`
(filter satu sumber), `--dry-run`, `--pages` (kompatibilitas CLI, diabaikan).

## Self-check

Tidak butuh jaringan:

```bash
python test_pipeline.py
```

## Variabel lingkungan

`SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE` (atau `GOOGLE_SERVICE_ACCOUNT_JSON`),
`SHEET_AUDIT_TAB`, `MAX_ITEMS_PER_RUN`, `MIN/MAX_DELAY_SECONDS`, `TIMEOUT`,
`MAX_RETRIES`, `DEADLINE_GRACE_DAYS`, `GEMINI_API_KEY` (opsional).

## Kurasi (Apps Script)

Pasang `scripts/Code.gs` di Extensions → Apps Script. Menu **🏆 Lomba
Aggregator**: approve baris terpilih, approve semua `AUTO_APPROVE`, reject
baris terpilih (pindah ke `Arsip Reject`).

## Struktur kode

```
main.py                 orkestrasi pipeline
src/config.py           konfigurasi dari .env
src/models.py           schema 15 kolom + model pydantic
src/normalizer.py       tanggal Indonesia, URL, heuristik field
src/classifier.py       filter noise + School + Confidence
src/dedupe.py           fingerprint + Jaccard + toleransi deadline
src/sheets.py           gspread: snapshot anti-leak + append
src/llm.py              fallback Gemini (opsional)
src/sources/*.py        adapter per sumber
data/keywords.json      bobot keyword School + pola noise
scripts/Code.gs         menu approve/reject
```
