# CV Screening AI

Layanan REST API untuk **screening & ranking kandidat berdasarkan CV** secara semi-otomatis,
dibuat sebagai Proof of Concept untuk technical test *AI Specialist* (otomatisasi seleksi CV).

Alur inti: CV (PDF) diekstrak teksnya → di-embed → disimpan di **Qdrant** (vector DB). Saat HR
bertanya lewat endpoint chat, sistem melakukan **retrieval** kandidat paling relevan, lalu
**LLM** menilai dan meranking mereka terhadap requirements posisi dan menghasilkan output
terstruktur (skor kecocokan + alasan).

---

## Fitur

| Kemampuan (sesuai soal) | Status di PoC |
|---|---|
| 2. Ekstraksi informasi dari CV | ✅ ekstraksi teks PDF (PyMuPDF) |
| 3. Pencocokan CV dengan kriteria posisi | ✅ vector retrieval + penilaian LLM |
| 4. Menyaring & meranking kandidat | ✅ ranking + `match_score` 0–100 dari LLM |
| 5. Shortlist siap interview, minim intervensi | ✅ output otomatis, ada threshold relevansi |
| 6. Output jelas & terstruktur | ✅ JSON: `summary` (markdown) + daftar kandidat terurut + `reasoning` + link file CV |

Fitur tambahan:
- **Intent guard** — pertanyaan di luar konteks screening kandidat langsung ditolak tanpa memanggil LLM scoring.
- **Relevance threshold** — kalau skor similarity tertinggi di bawah ambang, sistem menjawab "tidak ada yang cocok" tanpa memaksakan kecocokan (mitigasi bias positif).
- **Presigned URL** — setiap kandidat hasil ranking disertai link download CV dari MinIO (berlaku 60 menit).
- **Requirements fleksibel** — bisa dikirim sebagai teks atau lampiran PDF job description.

---

## Arsitektur

Upload file CV ke MinIO dilakukan **di luar aplikasi ini** (lewat MinIO console, `mc`, atau
sistem lain). Aplikasi tidak menerima file binary — request `/ingest` hanya membawa
`bucket_name` + `object_name`, lalu endpoint **membaca file itu dari MinIO** untuk diproses.

```
  ┌─────────────────────────────┐
  │ Upload PDF CV ke MinIO      │   di luar aplikasi (MinIO console / mc / sistem lain)
  │ (mis. via MinIO console)    │
  └──────────────┬──────────────┘
                 │ taruh di: cv-files/<nama>.pdf
                 ▼
        ┌──────────────┐
        │    MinIO     │  (penyimpanan file CV)
        └──────┬───────┘
   (1) baca    │  ▲                            ┌──────────────┐
   file  ◀─────┘  │ (3) presigned URL per      │    Qdrant    │  (vektor + metadata)
                  │     kandidat (chat)        └──────┬───────┘
                  │                            (2) upsert     ▲
 request /ingest  │                             vektor  │     │ retrieval
 { bucket_name,   │        ┌────────────┐               │     │
   object_name }──┼───────▶│  /ingest   │───────────────┘     │
                  │        │            │  extract teks (PyMuPDF) → embed (fastembed)
                  │        └────────────┘                     │
                  │                                           │
   HR question ───┼───────▶┌────────────┐  embed query ───────┘
  (+requirements) │        │   /chat    │
                  └────────│            │   ┌─────────────────────┐
                           │            │──▶│  LLM (OpenRouter)   │  scoring + ranking + summary
                           └─────┬──────┘   └─────────────────────┘
                                 │
                                 ▼
             JSON: summary + ranked candidates (+ score, reasoning, file_url)
```

**Alur ingest:** client upload PDF ke MinIO sendiri → panggil `POST /ingest` dengan lokasi
file → endpoint fetch bytes dari MinIO → ekstrak teks → embed → upsert vektor + metadata
(`minio_file`, dll) ke Qdrant.

**Alur chat:** `POST /chat` dengan pertanyaan HR (+ requirements opsional) → embed query →
retrieval kandidat dari Qdrant → LLM menilai & meranking → tiap kandidat dilengkapi presigned
URL download CV dari MinIO → response JSON.

**Stack**

- **FastAPI** — REST API
- **PyMuPDF** — ekstraksi teks PDF
- **fastembed** — embedding model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (multibahasa, ID/EN)
- **Qdrant** — vector search + filter metadata
- **MinIO** — object storage untuk file CV (S3-compatible)
- **OpenRouter** (via `langchain-openai` `ChatOpenAI`, OpenAI-compatible) — LLM untuk penilaian & ranking. Model default: `openai/gpt-oss-120b`

---

## Prasyarat

- Python 3.10+
- Docker (untuk menjalankan MinIO & Qdrant)

---

## 1. Jalankan MinIO & Qdrant via Docker

**Wajib dijalankan lebih dulu sebelum aplikasi** — saat startup, aplikasi otomatis membuat
Qdrant collection (`candidates`) dan MinIO bucket (`cv-files`). Kalau salah satu belum siap,
aplikasi gagal start.

### Opsi A — perintah `docker run` terpisah

```bash
# Qdrant — REST di 6333, gRPC di 6334
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v qdrant_data:/qdrant/storage \
  qdrant/qdrant

# MinIO — API di 9000, console web di 9001
docker run -d --name minio \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=admin \
  -e MINIO_ROOT_PASSWORD=admin12345 \
  -v minio_data:/data \
  minio/minio server /data --console-address ":9001"
```

> Windows PowerShell: ganti `\` di akhir baris dengan backtick `` ` `` atau tulis satu baris.

### Opsi B — `docker-compose.yml`

```yaml
services:
  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: admin12345
    volumes:
      - minio_data:/data

volumes:
  qdrant_data:
  minio_data:
```

```bash
docker compose up -d
```

### Verifikasi

- Qdrant   : http://localhost:6333/dashboard
- MinIO API : http://localhost:9000
- MinIO console : http://localhost:9001  (login `admin` / `admin12345`)

---

## 2. Konfigurasi environment

Konfigurasi dibaca dari `config/properties.env`. Buat file tersebut (atau salin dari contoh
di bawah) dan sesuaikan nilainya:

```ini
# App
APP_NAME=CV Screening AI
APP_VERSION=0.1.0
APP_PORT=8000
DEBUG=true
API_PREFIX=/api/v1

# Embedding
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# LLM (OpenRouter, OpenAI-compatible)
open_router.api_key=<ISI_API_KEY_OPENROUTER_ANDA>
open_router.url=https://openrouter.ai/api/v1
open_router.model=openai/gpt-oss-120b

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=candidates

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin12345
MINIO_BUCKET=cv-files
MINIO_SECURE=false
```

> `config/properties.env` sudah masuk `.gitignore` dan tidak ikut ter-commit. Jangan pernah
> membagikan API key asli di slide/repo — rotasi key jika sudah pernah terekspos.

---

## 3. Install dependency & jalankan aplikasi

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt

# jalankan (pastikan langkah 1 & 2 sudah beres)
python -m app.main
```

Aplikasi jalan di `http://localhost:8000`.

- Swagger UI : http://localhost:8000/docs
- Health     : http://localhost:8000/health

---

## 4. Cara pakai API

Base path semua endpoint: `/api/v1`.

### a. Upload file CV ke MinIO

Endpoint `/ingest` mengharapkan file **sudah ada di MinIO**. Upload dulu PDF-nya ke bucket
`cv-files` lewat MinIO console (http://localhost:9001) atau `mc`, misalnya:

```
cv-files/Bayu_Pratama.pdf
```

### b. `POST /api/v1/ingest` — indeks satu CV

Request body (JSON):

```json
{
  "document_id": "cand-001",
  "file": {
    "bucket_name": "cv-files",
    "object_name": "Bayu_Pratama.pdf"
  }
}
```

Response:

```json
{
  "document_id": "cand-001",
  "title": "Bayu_Pratama.pdf",
  "status": "success",
  "minio_file": "cv-files/Bayu_Pratama.pdf"
}
```

Ulangi untuk setiap kandidat.

### c. `POST /api/v1/chat` — cari, nilai, & ranking kandidat

Request berupa **multipart/form-data**:

| Field | Wajib | Keterangan |
|---|---|---|
| `message` | ✅ | pertanyaan/permintaan HR, mis. `"Carikan kandidat untuk posisi Interior Designer, utamakan yang paham AutoCAD"` |
| `top_k` | – | jumlah kandidat yang diambil dari retrieval (default `5`) |
| `requirements_text` | – | requirements posisi dalam bentuk teks |
| `requirements_file` | – | requirements posisi berupa file PDF (job description) |

Contoh `curl`:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -F "message=Carikan kandidat paling cocok untuk Interior Designer" \
  -F "top_k=5" \
  -F "requirements_file=@job_description.pdf"
```

Response:

```json
{
  "answer": "## Perbandingan Kandidat\n| Peringkat | Kandidat | ... |",
  "candidates": [
    {
      "document_id": "cand-001",
      "title": "Bayu_Pratama.pdf",
      "score": 87.0,
      "minio_file": "cv-files/Bayu_Pratama.pdf",
      "file_url": "http://localhost:9000/cv-files/...&X-Amz-Signature=...",
      "reasoning": "Memenuhi syarat pendidikan D3 Desain Interior, 4 tahun pengalaman, menguasai AutoCAD & SketchUp. Gap: belum ada pengalaman proyek komersial."
    }
  ]
}
```

Catatan perilaku:
- `score` di response chat = `match_score` dari LLM (0–100), **bukan** cosine similarity.
- Kalau pertanyaan tidak berkaitan dengan screening kandidat → balasan fallback, `candidates` kosong.
- Kalau tidak ada kandidat sama sekali, atau skor similarity tertinggi di bawah ambang (`0.5`) → balasan "tidak ada yang cocok" tanpa memanggil LLM scoring.
- Kalau output LLM gagal di-parse jadi JSON → fallback ke urutan vector similarity + teks mentah LLM.

---

## 5. Frontend — UI untuk test chat

`frontend/cv-screening-app.html` adalah halaman statis sederhana untuk mencoba endpoint
`/chat` (kirim pertanyaan + requirements, lihat hasil ranking dirender sebagai markdown)
tanpa perlu `curl` / Postman.

Jalankan sebagai static server dari folder `frontend/`:

```bash
cd frontend
python -m http.server 5500
```

Lalu buka http://localhost:5500/cv-screening-app.html di browser.

- Pastikan backend (langkah 3) sudah jalan di `http://localhost:8000`. CORS di backend sudah
  di-set `allow_origins=["*"]`, jadi origin `localhost:5500` bebas mengakses.
- Field **Base URL** di halaman default-nya `http://localhost:8000/api/v1` — ubah kalau
  `APP_PORT` / `API_PREFIX` kamu beda.
- Data kandidat harus sudah di-ingest dulu (langkah 4a–4b) sebelum dicoba lewat halaman ini.
- Halaman ini hanya memakai `/chat`; ingest tetap lewat `curl` / Swagger UI.

> Port `5500` cuma konvensi (sama seperti Live Server VS Code) — bebas pakai port lain,
> asal bukan `8000` yang sudah dipakai backend.

---

## Struktur proyek

```
app/
├── main.py                 # entrypoint FastAPI + lifespan (ensure collection & bucket)
├── config/settings.py      # loader config dari config/properties.env
├── routers/                # definisi endpoint (/ingest, /chat)
├── controllers/            # orkestrasi alur ingest & chat
├── index/qdrant_index.py   # ingest_document + search_documents (embed → upsert/search)
├── infra/
│   ├── qdrant_infra.py     # client Qdrant, embedder, upsert, search
│   └── minio_infra.py      # client MinIO, presigned URL, get/stat object
├── prompts/chat_prompt.py  # prompt intent-check & scoring/ranking
├── schemas/                # model Pydantic (request/response)
└── utils/                  # pdf_extractor, logger
frontend/
└── cv-screening-app.html   # UI sederhana untuk mencoba endpoint chat
config/properties.env       # konfigurasi (tidak di-commit)
```

---

## Batasan PoC & rencana pengembangan

- **Auto-collect CV** dari job portal belum diimplementasi (fokus pada pipeline pemrosesan & ranking).
- **Ekstraksi** masih berupa teks mentah PDF (belum ada schema terstruktur pengalaman/pendidikan/skill, belum ada OCR untuk CV hasil scan).
- **Chunking** belum ada — satu CV = satu vektor (memadai untuk dokumen sependek CV, perlu ditinjau untuk dokumen panjang).
- **Mitigasi bias** yang sudah ada: threshold relevansi + instruksi prompt agar tidak memaksakan kecocokan. Rencana lanjut: anonimisasi PII (nama, umur, gender, foto) sebelum scoring, audit log keputusan, dan human-in-the-loop di tahap akhir.
