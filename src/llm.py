"""Optional LLM structuring for sources whose content is free-form prose.

Deterministic parsing stays the default; the LLM is a *fallback* for pages
where the deadline/fee/location only exist inside a paragraph. Disabled
automatically when no API key is configured.
"""

from __future__ import annotations

import json
import logging
import re

from src.config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger("compScraper-v2")

PROMPT = """Kamu adalah parser Structured Data untuk halaman Memories Lomba di Indonesia.

Ambil informasi dari TEKS di bawah dan kembalikan satu objek JSON.

ATURAN:
1. `title`: judul lomba. null jika tidak ada.
2. `organizer`: penyelenggara/institusi (nama termasuk kata "Universitas", "HIMA", "BEM", dll). null jika tidak ada.
3. `deadline`: batas akhir pendaftaran format YYYY-MM-DD. Ambil TANGGAL TERAKHIR jika ada rentang.
   null jika tidak ada tanggal pendaftaran.
4. `fee`: teks biaya apa adanya, contoh "GRATIS", "Rp 50.000", "Gratis untuk mahasiswa". null jika tidak ada.
5. `location`: salah satu dari "Online", "Offline", "Hybrid". null jika tidak jelas.
6. `location_detail`: kota/tempat/negara. null jika tidak ada.
7. `target`: siapa yang boleh ikut, contoh "SMA / Sederajat, Mahasiswa". null jika tidak ada.
8. `registration_url`: URL pendaftaran/form. null jika tidak ada.
9. `description`: ringkasan singkat maksimal 300 karakter, tanpa markdown.

Balas HANYA JSON valid, tanpa penjelasan, tanpa markdown.

TEKS:
{text}
"""


class LLMExtractor:
    """Thin Gemini wrapper. `available` is False when unconfigured."""

    def __init__(self, model: str = GEMINI_MODEL, api_key: str = GEMINI_API_KEY):
        self.model = model
        self.api_key = api_key
        self._client = None
        self.available = bool(api_key)
        if not self.available:
            log.info("LLM fallback disabled (no GEMINI_API_KEY).")

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        except Exception as exc:
            log.warning("LLM client unavailable: %s", exc)
            self.available = False
        return self._client

    def extract(self, text: str, source_url: str = "") -> dict | None:
        """Return a dict of extracted fields, or None on failure."""
        if not self.available or not text:
            return None
        client = self._ensure_client()
        if client is None:
            return None

        payload = f"{PROMPT.format(text=text[:12000])}\nSOURCE_URL: {source_url}\n"
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=payload,
                config={"response_mime_type": "application/json", "temperature": 0.1},
            )
            raw = response.text or ""
        except Exception as exc:
            log.warning("LLM call failed for %s: %s", source_url, exc)
            return None

        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("LLM returned non-JSON for %s: %.120s", source_url, raw)
            return None
        return data if isinstance(data, dict) else None
