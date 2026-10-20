import unittest
from src.classifier import classify_school
from src.models import CompetitionItem, normalize_url
from src.normalizer import parse_indonesian_date


class TestPipelineCoreV2(unittest.TestCase):
    def test_normalize_url(self):
        url = "https://WWW.InfoLomba.Net/2026/10/hackathon-ai.html/?utm_source=ig&fbclid=123"
        expected = "https://www.infolomba.net/2026/10/hackathon-ai.html"
        self.assertEqual(normalize_url(url), expected)

    def test_classify_school_primary_and_tie_break(self):
        title = "National AI Hackathon 2026"
        desc = "Lomba coding dan data science tingkat mahasiswa"
        primary, secondaries = classify_school(title, desc)
        self.assertEqual(primary, "SEN")

        title_multi = "UI/UX Design Competition"
        desc_multi = "Lomba desain poster dan coding prototype aplikasi"
        primary_multi, secondaries_multi = classify_school(title_multi, desc_multi)
        self.assertEqual(primary_multi, "SCD")
        self.assertIn("SEN", secondaries_multi)

    def test_parse_indonesian_date(self):
        date_str, dt = parse_indonesian_date("12 Sep - 26 Okt 2026")
        self.assertEqual(date_str, "2026-10-26")
        self.assertIsNotNone(dt)

        date_str_single, dt_single = parse_indonesian_date("15 November 2026")
        self.assertEqual(date_str_single, "2026-11-15")
        self.assertIsNotNone(dt_single)

        invalid_str, invalid_dt = parse_indonesian_date("tutup segera")
        self.assertEqual(invalid_str, "-")
        self.assertIsNone(invalid_dt)

    def test_competition_item_row(self):
        item = CompetitionItem(
            scraped_at="20/10/2026 10:00",
            title="Lomba Hackathon",
            organizer="Univ Cakrawala",
            school="SEN",
            fee="Gratis",
            deadline="2026-11-01",
            source_url="https://infolomba.id/hackathon-1",
            registration_url="https://forms.gle/xyz",
            guidebook_url="https://drive.google.com/doc",
            status_review="Pending",
        )
        row = item.to_row()
        self.assertEqual(len(row), 10)
        self.assertEqual(row[3], "SEN")
        self.assertEqual(row[9], "Pending")


if __name__ == "__main__":
    unittest.main()
