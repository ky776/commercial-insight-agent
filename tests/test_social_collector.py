import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.social_collector import CollectionError, HttpClient, Signal, collect, deduplicate_by_url, parse_feed, render_daily_note, score_signal, validate_public_url


TOPICS = {
    "model_release": ["new model", "模型发布"],
    "agent_ecosystem": ["agent", "mcp"],
    "business_model": ["pricing", "商业模式"],
}


class SocialCollectorTest(unittest.TestCase):
    def test_parse_atom_feed(self):
        payload = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>New model and Agent release</title>
    <id>entry-1</id>
    <link href="https://example.com/release" />
    <updated>2026-07-18T08:00:00Z</updated>
    <summary>New model supports Agent tool use and pricing changes.</summary>
  </entry>
</feed>"""
        since = dt.datetime(2026, 7, 17, tzinfo=dt.timezone.utc)
        signals = parse_feed(payload, "https://example.com/feed.xml", since)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].source_url, "https://example.com/release")

    def test_scoring_and_markdown_features(self):
        now = dt.datetime(2026, 7, 18, 10, tzinfo=dt.timezone.utc)
        signal = Signal(
            id="signal-1",
            platform="github",
            source_type="github_release",
            author="team",
            company="company",
            title="New model Agent release",
            source_url="https://example.com/release",
            published_at="2026-07-18T08:00:00Z",
            collected_at="2026-07-18T10:00:00Z",
            categories=[],
            summary="Agent tool use with new pricing",
            raw_excerpt="Agent tool use with new pricing",
            evidence_status="public_primary",
        )
        scored = score_signal(signal, TOPICS, now)
        self.assertIn("model_release", scored.categories)
        self.assertIn("agent_ecosystem", scored.categories)
        self.assertGreater(scored.business_value_score, 50)
        note = render_daily_note("2026-07-18", [scored], [], scored.collected_at)
        self.assertIn("商业价值分", note)
        self.assertIn("新颖度分", note)
        self.assertIn("原始链接：https://example.com/release", note)

    def test_deduplicates_same_public_url(self):
        base = dict(
            platform="github",
            author="team",
            company="company",
            title="Release",
            source_url="https://example.com/release",
            published_at="2026-07-18T08:00:00Z",
            collected_at="2026-07-18T10:00:00Z",
            categories=["model_release"],
            summary="summary",
            raw_excerpt="summary",
        )
        weaker = Signal(id="one", source_type="github_event", business_value_score=50, **base)
        stronger = Signal(id="two", source_type="github_release", business_value_score=80, **base)
        results = deduplicate_by_url([weaker, stronger])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "two")

    def test_blocks_local_urls(self):
        with self.assertRaises(CollectionError):
            validate_public_url("http://127.0.0.1/private")
        with self.assertRaises(CollectionError):
            validate_public_url("file:///Users/ky/private.txt")
        validate_public_url("https://api.github.com/events")

    def test_end_to_end_feed_writes_vault_and_state(self):
        payload = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <title>New model Agent release</title><id>entry-1</id>
          <link href="https://example.com/release" />
          <updated>2026-07-18T08:00:00Z</updated>
          <summary>New model supports Agent tool use and pricing.</summary>
        </entry></feed>"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.json"
            vault = root / "vault"
            local = root / "local"
            vault.mkdir()
            config.write_text(json.dumps({
                "daily_limit": 100,
                "lookback_hours": 100000,
                "minimum_value_score": 1,
                "github": {"users": [], "repositories": []},
                "feeds": ["https://example.com/feed.xml"],
                "public_post_urls": [],
                "topics": TOPICS,
            }), encoding="utf-8")
            with patch.object(HttpClient, "get", return_value=(payload, {})):
                report = collect(config, vault, local)
            self.assertEqual(report["signals"], 1)
            self.assertTrue(Path(report["note"]).is_file())
            self.assertTrue((local / "social_state.json").is_file())
            self.assertIn("New model Agent release", Path(report["note"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
