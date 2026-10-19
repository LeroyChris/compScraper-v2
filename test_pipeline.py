import unittest
from main import classify_school, normalize_url, parse_date_id


class TestPipelineCore(unittest.TestCase):
    def test_normalize_url(self):
        url = "https://WWW.InfoLomba.Net/2026/10/hackathon-ai.html/?utm_source=ig&fbclid=123"
        expected = "https://www.infolomba.net/2026/10/hackathon-ai.html"
        self.assertEqual(normalize_url(url), expected)

    def test_classify_school_primary_and_tie_break(self):
        # AI and Hackathon matches SEN (score: 4)
        title = "National AI Hackathon 2026"
        desc = "Lomba coding dan data science tingkat mahasiswa"
        primary, secondaries = classify_school(title, desc)
        self.assertEqual(primary, "SEN")

        # UI/UX matches SCD (score 2 in title), coding in desc matches SEN (score 1)
        title_multi = "UI/UX Design Competition"
        desc_multi = "Lomba desain poster dan coding prototype aplikasi"
        primary_multi, secondaries_multi = classify_school(title_multi, desc_multi)
        self.assertEqual(primary_multi, "SCD")
        self.assertIn("SEN", secondaries_multi)

    def test_classify_school_fallback_umum(self):
        primary, secondaries = classify_school("Turnamen Catur Mahasiswa", "Kategori umum beregu")
        self.assertEqual(primary, "UMUM")
        self.assertEqual(secondaries, [])

    def test_parse_date_id(self):
        self.assertEqual(parse_date_id("15 November 2026"), "2026-11-15")
        self.assertEqual(parse_date_id("2026-12-01"), "2026-12-01")
        self.assertEqual(parse_date_id("05/10/2026"), "2026-10-05")
        self.assertEqual(parse_date_id("invalid date"), "-")


if __name__ == "__main__":
    unittest.main()
