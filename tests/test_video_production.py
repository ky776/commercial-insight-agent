import json
import tempfile
import unittest
from pathlib import Path

from scripts.video_production import (
    VideoProductionError,
    _safe_id,
    build_caption_cues,
    get_finished_video,
    write_srt,
)


class VideoProductionTest(unittest.TestCase):
    def test_caption_cues_cover_media_duration(self):
        cues = build_caption_cues("第一句说明问题。第二句给出判断！第三句提出行动。", 12.0)

        self.assertEqual(cues[0]["start"], 0.0)
        self.assertEqual(cues[-1]["end"], 12.0)
        self.assertTrue(all(cue["end"] > cue["start"] for cue in cues))
        self.assertTrue(all(len(cue["lines"]) <= 2 for cue in cues))

    def test_markdown_controls_are_removed_from_spoken_captions(self):
        cues = build_caption_cues("# 标题\n\n- **品牌老板**先看到成本。\n> 这行是引用", 6.0)

        text = "".join(cue["text"] for cue in cues)
        self.assertNotIn("#", text)
        self.assertNotIn("**", text)
        self.assertIn("品牌老板", text)

    def test_srt_is_written_with_valid_timestamps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "captions.srt"
            write_srt([{"index": 1, "start": 0.0, "end": 1.25, "text": "测试字幕"}], path)

            content = path.read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 --> 00:00:01,250", content)
            self.assertIn("测试字幕", content)

    def test_production_id_is_sanitized(self):
        self.assertEqual(_safe_id("项目 A/../../video"), "A-video")

    def test_finished_video_must_exist_inside_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(VideoProductionError):
                get_finished_video("missing-project", root)

            output = root / "local" / "projects" / "project-1" / "exports" / "douyin-xiaohongshu-v001.mp4"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"video")
            self.assertEqual(get_finished_video("project-1", root), output)


if __name__ == "__main__":
    unittest.main()
