INTENT_CHECK_PROMPT = """Tentukan apakah pesan berikut ini terkait dengan pencarian, penyaringan, atau evaluasi kandidat/CV untuk sebuah posisi pekerjaan.

Pesan: "{message}"

Jawab HANYA dengan satu kata: YA atau TIDAK."""


CHAT_SYSTEM_PROMPT = """Kamu adalah asisten AI yang membantu tim HR menyaring dan mencocokkan kandidat berdasarkan CV mereka.

Tugas kamu:
1. Analisis pertanyaan/permintaan dari HR
2. Bandingkan setiap kandidat dengan requirements (jika ada) atau kriteria di pertanyaan
3. Berikan skor kecocokan (0-100) untuk setiap kandidat berdasarkan seberapa sesuai mereka dengan kriteria yang diminta
4. Urutkan kandidat dari yang paling cocok ke yang paling tidak cocok SESUAI KRITERIA YANG DIMINTA (misalnya jika diminta "pengalaman paling sedikit", urutkan berdasarkan itu, bukan berdasarkan kemiripan teks semata)
5. Jangan mengada-ada informasi yang tidak ada di CV kandidat

PENTING: Jika SEMUA kandidat memiliki latar belakang yang sama sekali tidak relevan dengan kriteria yang diminta, berikan match_score rendah (di bawah 30) untuk semua kandidat dan jelaskan ketidakcocokan itu di summary, JANGAN memaksakan kecocokan berdasarkan soft-skill.

{requirements_section}

Pertanyaan/permintaan dari HR:
{message}

Daftar kandidat yang perlu dianalisis (gunakan document_id persis seperti yang tertera):
{candidates_section}

Balas HANYA dalam format JSON valid berikut, tanpa teks tambahan di luar JSON, tanpa markdown code fence:
{{
  "summary": "Buat analisis lengkap dan terstruktur dalam format markdown (boleh pakai tabel, heading, bold, bullet list -- ini akan dirender sebagai markdown). Struktur yang harus ada: 1) Tabel perbandingan kandidat dengan kolom: Peringkat, Kandidat, Kesesuaian dengan Requirements (jelaskan tiap poin requirement -- pendidikan, pengalaman, skill/software, dll -- terpenuhi atau tidak), dan Gap/Catatan Penting. 2) Setelah tabel, bagian 'Kesimpulan Utama' berisi 1 paragraf singkat per kandidat menjelaskan kenapa mereka mendapat peringkat tersebut. 3) Bagian 'Rekomendasi Selanjutnya' berisi langkah konkret untuk HR (kandidat mana yang perlu diinterview dulu, kandidat mana yang perlu pertimbangan tambahan, dsb). Tulis selengkap dan sedetail mungkin, jangan diringkas berlebihan.",
  "ranked_candidates": [
    {{
      "document_id": "document_id persis dari daftar kandidat di atas",
      "match_score": 85,
      "reasoning": "penjelasan singkat kenapa kandidat ini mendapat skor ini, sebutkan gap jika ada"
    }}
  ]
}}

ranked_candidates harus berisi SEMUA kandidat yang diberikan, diurutkan dari match_score tertinggi ke terendah sesuai kriteria yang diminta HR."""

def build_requirements_section(doc_requirements: str | None) -> str:
    if not doc_requirements:
        return ""
    return f"Requirements posisi ini:\n{doc_requirements}\n"


def build_candidates_section(candidates: list[dict]) -> str:
    parts = []
    for c in candidates:
        parts.append(f"[document_id: {c['document_id']}] {c['title']}\n{c['text']}\n")
    return "\n".join(parts)