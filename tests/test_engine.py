"""Engine behaviour that must not regress, tested offline with made-up data.

    python3 -m unittest discover -s tests -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import import_seeds  # noqa: E402
import set_key  # noqa: E402
from engine import audience_geo, seeds  # noqa: E402


class Keys(unittest.TestCase):
    def test_youtube_key_shape(self):
        rx = set_key.KEYS["youtube"][2]
        self.assertTrue(rx.match("AIza" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r"))
        self.assertFalse(rx.match("AIzaTooShort"))
        self.assertFalse(rx.match("youtube-creator-sourcing"))  # the key's name, a common wrong copy

    def test_write_key_replaces_one_line_and_locks_the_file(self):
        d = tempfile.mkdtemp()
        try:
            env = os.path.join(d, ".env")
            with open(env, "w") as f:
                f.write("YOUTUBE_API_KEY=\nSERPER_API_KEY=keep\n")
            old = set_key.ENV
            set_key.ENV = env
            set_key.write_key("YOUTUBE_API_KEY", "AIzaX")
            set_key.ENV = old
            with open(env) as f:
                self.assertEqual(f.read(), "YOUTUBE_API_KEY=AIzaX\nSERPER_API_KEY=keep\n")
            self.assertEqual(os.stat(env).st_mode & 0o777, 0o600)
        finally:
            shutil.rmtree(d)


class SeedImport(unittest.TestCase):
    def test_number(self):
        self.assertEqual(import_seeds.number("£1,200"), 1200)
        self.assertEqual(import_seeds.number("1.5k"), 1500)
        self.assertIsNone(import_seeds.number("n/a"))

    def test_dates(self):
        self.assertEqual(str(import_seeds.when("2026-09-01")), "2026-09-01")
        self.assertEqual(str(import_seeds.when("01/09/2026")), "2026-09-01")
        self.assertEqual(str(import_seeds.when("2026-09-01T10:00:00Z")), "2026-09-01")

    def test_columns(self):
        h = ["Creator", "Video URL", "Go-live date", "Sign-ups", "Spend"]
        v = import_seeds.find_col(h, import_seeds.VIDEO_COLS)
        self.assertEqual(v, "Video URL")
        self.assertEqual(import_seeds.find_col(h, import_seeds.CHANNEL_COLS, exclude=(v,)), "Creator")
        self.assertEqual(import_seeds.find_col(h, import_seeds.METRIC_COLS, exclude=(v,)), "Sign-ups")
        self.assertEqual(import_seeds.find_col(["video_url", "result", "date"], import_seeds.METRIC_COLS, exclude=("video_url",)), "result")


class Lateral(unittest.TestCase):
    BRAND = "zz-unit-test-brand"

    def setUp(self):
        self.files = [seeds.path(self.BRAND), seeds.angles_path(self.BRAND)]
        seeds.save(self.BRAND, {"imported": "2026-01-01", "seeds": [
            {"channel_id": "UC1", "name": "Plant Corner", "videos": [{"video_id": "v1", "title": "My Sunday plant care routine in a tiny flat", "metric": 90}],
             "profile": {"words": {"plant": 9, "repot": 5, "monstera": 4, "routine": 3}, "subs": 12000, "country": "GB", "format": "longform", "top_video": "v1"}},
            {"channel_id": "UC2", "name": "Leafy Loft", "videos": [{"video_id": "v2", "title": "Repotting every plant I own (October edition)", "metric": 40}],
             "profile": {"words": {"plant": 7, "propagation": 5, "cutting": 4}, "subs": 8000, "country": "GB", "format": "longform", "top_video": "v2"}}]})
        with open(seeds.angles_path(self.BRAND), "w") as f:
            json.dump({"angles": [{"video_id": "v1", "seed": "Plant Corner", "angle": "weekly care routine", "queries": ["my weekly plant care routine small flat"]}],
                       "creators": [{"seed": "Plant Corner", "creator": "calm small-flat collector", "queries": ["small flat plant collection tour"]}]}, f)

    def tearDown(self):
        for f in self.files:
            if os.path.exists(f):
                os.remove(f)

    class Cfg(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

    def plan(self, mode, key):
        cfg = self.Cfg(seeds={"share": 1.0, "suffix": "uk", "content_mode": mode})
        old = seeds.transcripts_on
        seeds.transcripts_on = lambda st: st.get("content_mode") == "transcripts" and key
        try:
            return seeds.plan(cfg, self.BRAND, None, 6, lambda cid: {"videos": []}, lambda t: True)
        finally:
            seeds.transcripts_on = old

    def test_title_query_drops_filler_and_months(self):
        self.assertEqual(seeds.title_query("Repotting every plant I own (October edition)"), "repotting plant own")
        self.assertEqual(seeds.title_query("FIRST plant haul of OCTOBER christmas"), "first plant haul")

    def test_free_mode_uses_titles_and_lookalikes_only(self):
        q, used, status = self.plan("titles", False)
        lanes = Counter(l for l, _, _ in q)
        self.assertEqual(set(lanes), {"seed", "lookalike"})
        self.assertTrue(all(p.endswith(" uk") for _, p, _ in q))
        self.assertIn("free", status)

    def test_transcript_mode_needs_the_key(self):
        q, _, status = self.plan("transcripts", True)
        self.assertIn("content", {l for l, _, _ in q})
        q, _, status = self.plan("transcripts", False)
        self.assertNotIn("content", {l for l, _, _ in q})
        self.assertIn("no ScrapeCreators key", status)

    def test_rotation_prefers_seeds_not_walked_recently(self):
        today = datetime.now().date().isoformat()
        items = [{"channel_id": "a"}, {"channel_id": "b"}]
        self.assertEqual(seeds.pick(items, {"a": today}, 2, 21, lambda s: s["channel_id"])[0]["channel_id"], "b")


class AudienceGeography(unittest.TestCase):
    class Cfg(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

    def sample(self, words, utc_hours, n=120):
        base = datetime(2026, 1, 12, tzinfo=timezone.utc)
        return [{"text": words[i % len(words)], "ts": base + timedelta(days=i % 20, hours=utc_hours[i % len(utc_hours)])} for i in range(n)]

    def test_uk_audience_meets_a_uk_target(self):
        cfg = self.Cfg(geo={"markets": ["GB"], "audience_target": {"countries": ["GB"], "min_share": 0.5}})
        comments = self.sample(["got mine at tesco for £4", "council tax went up again", "lovely video"], [18, 19, 20, 21, 12, 8])
        g = audience_geo.estimate(cfg, comments, Counter({"GB": 18, None: 300, "US": 1}), {"country": "GB"}, [], "", "api")
        self.assertGreater(g["estimate"], 0.7)
        self.assertEqual(g["verdict"], "meets")
        self.assertIn(g["confidence"], ("medium", "high"))
        self.assertIn("Europe and Africa", g["time_mix"])

    def test_us_audience_misses_a_uk_target(self):
        cfg = self.Cfg(geo={"markets": ["GB"], "audience_target": {"countries": ["GB"], "min_share": 0.5}})
        comments = self.sample(["got it at walmart for $5", "my 401k says no", "y'all are great"], [0, 1, 2, 23, 22, 17])
        g = audience_geo.estimate(cfg, comments, Counter({"US": 20, "CA": 2, None: 280}), {"country": "US"}, [], "", "api")
        self.assertLess(g["estimate"], 0.3)
        self.assertEqual(g["verdict"], "misses")

    def test_no_signal_says_so_and_stores_totals_only(self):
        cfg = self.Cfg(geo={"markets": ["GB"]})
        g = audience_geo.estimate(cfg, [], Counter(), {}, [], "", "keyless")
        self.assertIsNone(g["estimate"])
        self.assertIn("screenshot", g["summary"])

    def test_city_is_a_signal_not_a_percentage(self):
        cfg = self.Cfg(geo={"markets": ["GB"], "audience_target": {"countries": ["GB"], "city": "London"}})
        comments = self.sample(["just moved to hackney", "the tube was packed", "tesco meal deal"], [19, 20])
        g = audience_geo.estimate(cfg, comments, Counter({"GB": 5}), {"country": "GB"}, ["London flat tour"], "", "api")
        self.assertEqual(g["city"]["city"], "London")
        self.assertIn(g["city"]["signal"], ("strong", "some"))


if __name__ == "__main__":
    unittest.main()
