#!/usr/bin/env python3
"""Self-checks for the parsing/validation layer. No network access.

    ./venv/bin/python test_pipeline.py
"""

from __future__ import annotations

import unittest

from src.classifier import CompetitionClassifier
from src.dedupe import Deduplicator, compute_fingerprint, jaccard, normalize_title_tokens
from src.models import CompetitionRecord, sanitize_text
from src.normalizer import (
    guess_fee,
    guess_location,
    guess_organizer,
    guess_registration_deadline,
    guess_target,
    html_to_text,
    normalize_url,
    parse_indonesian_date,
    split_links,
)


class TestDates(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(parse_indonesian_date("2026-11-07")[0], "2026-11-07")

    def test_indonesian_long(self):
        self.assertEqual(parse_indonesian_date("15 November 2026")[0], "2026-11-15")

    def test_range_takes_closing_boundary(self):
        self.assertEqual(parse_indonesian_date("12 Sep - 26 Okt 2026")[0], "2026-10-26")

    def test_range_without_spaces_is_not_split(self):
        # regression: the old implementation split on every "-"
        self.assertEqual(parse_indonesian_date("10-10-2026")[0], "2026-10-10")

    def test_slash_format(self):
        self.assertEqual(parse_indonesian_date("05/11/2026")[0], "2026-11-05")

    def test_garbage(self):
        self.assertEqual(parse_indonesian_date("tutup segera")[0], None)

    def test_indonesian_year_word(self):
        self.assertEqual(parse_indonesian_date("7 Agustus tahun 2026")[0], "2026-08-07")

    def test_range_with_en_dash(self):
        self.assertEqual(parse_indonesian_date("7 September–5 Oktober 2026")[0], "2026-10-05")


class TestRegistrationDeadline(unittest.TestCase):
    def test_latest_registration_phase_wins(self):
        text = (
            "Timeline Early Bird Registration 13 - 23 Juli 2026 Batch 1 Registration "
            "24 Juli - 30 Agustus 2026 Batch 2 Registration 31 Agustus - 2 Oktober 2026"
        )
        self.assertEqual(guess_registration_deadline(text), "2026-10-02")

    def test_re_registration_is_ignored(self):
        text = (
            "Batch 2 Registration 31 Agustus - 2 Oktober 2026 Registrasi Ulang "
            "Semifinalis 31 Oktober - 10 November 2026"
        )
        self.assertEqual(guess_registration_deadline(text), "2026-10-02")


class TestUrls(unittest.TestCase):
    def test_tracking_params_stripped_but_meaningful_kept(self):
        out = normalize_url("https://WWW.InfoLomba.Net/2026/10/x.html/?utm_source=ig&fbclid=123&id=77")
        self.assertEqual(out, "https://www.infolomba.net/2026/10/x.html?id=77")

    def test_invalid(self):
        self.assertEqual(normalize_url("not-a-url"), "-")


class TestText(unittest.TestCase):
    def test_emoji_removed_but_cjk_kept(self):
        # regression: an earlier emoji range swallowed CJK ideographs
        out = sanitize_text("Lomba 漢字 2026 🚀")
        self.assertNotIn("🚀", out)
        self.assertIn("漢字", out)

    def test_html_to_text(self):
        self.assertEqual(html_to_text("<p>Halo <b>Dunia</b></p>"), "Halo Dunia")

    def test_math_bold_letters_are_normalized(self):
        # Blogger/Instagram posts write dates in "math bold" glyphs
        self.assertEqual(html_to_text("<p>\U0001D7CF\U0001D7D2 \U0001D409\U0001D42E\U0001D427\U0001D422 \U0001D7D0\U0001D7CE\U0001D7D0\U0001D7D4</p>"), "14 Juni 2026")


class TestHeuristics(unittest.TestCase):
    def test_fee(self):
        self.assertEqual(guess_fee("Pendaftaran GRATIS untuk mahasiswa"), "GRATIS")
        self.assertEqual(guess_fee("Biaya Rp 75.000"), "Rp 75.000")

    def test_location(self):
        self.assertEqual(guess_location("fully online via zoom"), "Online")
        self.assertEqual(guess_location("tatap muka di jakarta"), "Offline")

    def test_target(self):
        self.assertIn("Mahasiswa", guess_target("terbuka untuk mahasiswa dan SMA"))

    def test_organizer_rejects_substring_noise(self):
        # "akademisi"/"panitia" inside a sentence is not an institution name
        self.assertEqual(guess_organizer("Mendapatkan masukan langsung dari akademisi dan peneliti"), "-")
        self.assertEqual(guess_organizer("Format penulisan harus mengikuti ketentuan resmi dari panitia"), "-")
        self.assertEqual(guess_organizer("HIMTI USUEXPORT 2026"), "HIMTI USUEXPORT 2026")


class TestLinks(unittest.TestCase):
    def test_split(self):
        links = [
            {"text": "panduan lomba", "url": "https://drive.google.com/file/d/x/view"},
            {"text": "daftar sekarang", "url": "https://bit.ly/Reg"},
        ]
        reg, guide = split_links(links, "infolomba.id")
        self.assertEqual(reg, "https://bit.ly/Reg")
        self.assertEqual(guide, "https://drive.google.com/file/d/x/view")

    def test_poster_and_social_links_ignored(self):
        links = [
            {"text": "poster", "url": "https://blogger.googleusercontent.com/img/R29vZ2xl/x/s1600/1.jpg"},
            {"text": "instagram", "url": "https://instagram.com/lomba"},
            {"text": "formulir", "url": "https://forms.gle/abc"},
        ]
        reg, guide = split_links(links, "infolombait.com")
        self.assertEqual(reg, "https://forms.gle/abc")
        self.assertEqual(guide, "-")

    def test_guide_link_does_not_swallow_registration(self):
        links = [
            {"text": "", "url": "https://bit.ly/GuideBookPekanIT"},
            {"text": "", "url": "https://bit.ly/PendaftaranNIC2026"},
        ]
        reg, guide = split_links(links, "infolombait.com")
        self.assertEqual(reg, "https://bit.ly/PendaftaranNIC2026")
        self.assertEqual(guide, "https://bit.ly/GuideBookPekanIT")


class TestClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = CompetitionClassifier()

    def test_noise_dropped(self):
        self.assertTrue(self.classifier.is_noise("Loker Internship PT XYZ来了"))
        self.assertTrue(self.classifier.is_noise("Beasiswa Unggulan 2026"))

    def test_school_and_confidence(self):
        result = self.classifier.classify(
            "National AI Hackathon 2026", "programming and machine learning", True, True
        )
        self.assertEqual(result["school"], "SEN")
        self.assertGreaterEqual(result["confidence"], 0.5)

    def test_no_match_is_manual_check(self):
        result = self.classifier.classify("Lomba Menggambar Kucing", "", False, False)
        self.assertEqual(result["school"], "UMUM")
        self.assertEqual(result["status_review"].value, "MANUAL_CHECK")


class TestDedupe(unittest.TestCase):
    def test_fingerprint_stable(self):
        a = compute_fingerprint("Lomba Esai Nasional 2026", "2026-10-01")
        b = compute_fingerprint("esai nasional lomba 2026", "2026-10-01")
        self.assertEqual(a, b)

    def test_jaccard(self):
        self.assertEqual(jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(jaccard({"a"}, {"b"}), 0.0)

    def test_cross_source_duplicate_dropped(self):
        deduper = Deduplicator(known_entries=[("Lomba Esai Nasional 2026", "2026-10-01")])
        record = CompetitionRecord(
            id="infolomba_1", source_id="infolomba", title="Lomba Esai Nasional 2026", deadline="2026-10-01"
        )
        dup, reason = deduper.is_duplicate(record)
        self.assertTrue(dup, reason)


class TestRecord(unittest.TestCase):
    def test_row_shape(self):
        record = CompetitionRecord(
            id="infolomba_2128",
            source_id="infolomba",
            title="Business Plan Competition",
            deadline="2026-09-20",
            confidence=0.67,
        )
        row = record.to_row()
        self.assertEqual(len(row), 15)
        self.assertEqual(row[0], "infolomba_2128")
        self.assertEqual(row[6], "2026-09-20")
        self.assertEqual(row[8], "0.67")
        self.assertEqual(row[9], "MANUAL_CHECK")

    def test_invalid_deadline_is_dropped(self):
        record = CompetitionRecord(
            id="x", source_id="s", title="t", deadline="2026-99-99"
        )
        self.assertIsNone(record.deadline)


if __name__ == "__main__":
    unittest.main(verbosity=2)
