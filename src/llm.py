"""Optional LLM structuring for sources whose content is free-form prose.

Deterministic parsing stays the default; the LLM is a *fallback* for pages
where the deadline/fee/location only exist inside a paragraph. Disabled
automatically when no API key is configured.
"""

from __future__ import annotations

import json
import logging
import re

from src.config import GEMINI_API_KEY, GEMINI_MODEL, OPENROUTER_API_KEY, OPENROUTER_MODEL

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
    """Thin wrapper for Gemini or OpenRouter LLM. `available` is False when unconfigured."""

    def __init__(self, model: str = GEMINI_MODEL, api_key: str = GEMINI_API_KEY,
                 openrouter_key: str = OPENROUTER_API_KEY,
                 openrouter_model: str = OPENROUTER_MODEL):
        self.model = model
        self.api_key = api_key
        self.openrouter_key = openrouter_key
        self.openrouter_model = openrouter_model
        self._client = None
        self._or_client = None
        self.available = bool(api_key)
        if not self.available:
            log.info("LLM fallback disabled (no GEMINI_API_KEY).")

    def _ensure_client(self):
        if self._client is not None and self._or_client is not None:
            return self._client, self._or_client
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        except Exception as exc:
            log.warning("Gemini client unavailable: %s", exc)
            self._client = None

        try:
            import openai
            self._or_client = openai.AsyncClient(
                api_key=self.openrouter_key,
                base_url="https://openrouter.ai/api/v1",
            )
        except Exception as exc:
            log.warning("OpenRouter client unavailable: %s", exc)
            self._or_client = None

        return self._client, self._or_client

    def extract(self, text: str, source_url: str = "") -> dict | None:
        """Return a dict of extracted fields, or None on failure."""
        if not self.available or not text:
            return None
        client, or_client = self._ensure_client()
        if client is None and or_client is None:
            return None

        use_or = (self.model == self.openrouter_model) or (self.model.startswith("openrouter/"))

        payload_text = f"{PROMPT.format(text=text[:12000])}\nSOURCE_URL: {source_url}\n"

        if use_or and or_client is not None:
            # OpenRouter: pakai model dari self.openrouter_model
            try:
                response = or_client.chat.completions.create(
                    model=self.openrouter_model,
                    messages=[{"role": "user", "content": payload_text}],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content or ""
            except Exception as exc:
                log.warning("OpenRouter call failed for %s: %s", source_url, exc)
                return None
        else:
            # Gemini: pakai client lama
            if client is None:
                return None
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=payload_text,
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
