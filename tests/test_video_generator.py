import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.video_generator import VideoGenerationError, create_seedance_job, refresh_seedance_job


class JsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class BinaryResponse:
    def __init__(self, content):
        self.content = content
        self.offset = 0
        self.headers = {"Content-Length": str(len(content))}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size=-1):
        if self.offset >= len(self.content):
            return b""
        end = len(self.content) if size < 0 else min(self.offset + size, len(self.content))
        chunk = self.content[self.offset:end]
        self.offset = end
        return chunk


class VideoGeneratorTest(unittest.TestCase):
    def make_root(self, temporary):
        root = Path(temporary) / "agent"
        (root / "config").mkdir(parents=True)
        source = Path(__file__).resolve().parents[1] / "config" / "model_providers.json"
        shutil.copyfile(source, root / "config" / "model_providers.json")
        return root

    def test_cost_confirmation_is_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            with self.assertRaises(VideoGenerationError):
                create_seedance_job("品牌广告片", root=root)

    def test_create_and_refresh_downloads_completed_video(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            captured = {}

            def create_transport(request, **_kwargs):
                captured["url"] = request.full_url
                captured["body"] = json.loads(request.data.decode())
                return JsonResponse({"id": "cgt-test-123"})

            with patch.dict(os.environ, {"ARK_API_KEY": "test-key"}):
                job = create_seedance_job(
                    "0-3秒展示成本上涨，镜头快速推进",
                    ratio="9:16",
                    duration=5,
                    resolution="720p",
                    confirmed_cost=True,
                    root=root,
                    transport=create_transport,
                )
            self.assertTrue(captured["url"].endswith("/contents/generations/tasks"))
            self.assertEqual(captured["body"]["model"], "doubao-seedance-2-0-260128")
            self.assertIn("--ratio 9:16", captured["body"]["content"][0]["text"])
            self.assertEqual(job["status"], "queued")

            def status_transport(request, **_kwargs):
                self.assertTrue(request.full_url.endswith("/cgt-test-123"))
                return JsonResponse({
                    "id": "cgt-test-123",
                    "status": "succeeded",
                    "content": {"video_url": "https://example.com/video.mp4"},
                })

            with patch.dict(os.environ, {"ARK_API_KEY": "test-key"}):
                completed = refresh_seedance_job(
                    "cgt-test-123",
                    root=root,
                    transport=status_transport,
                    downloader=lambda *_args, **_kwargs: BinaryResponse(b"video-content"),
                )
            self.assertEqual(completed["status"], "succeeded")
            self.assertEqual(Path(completed["output_path"]).read_bytes(), b"video-content")


if __name__ == "__main__":
    unittest.main()
