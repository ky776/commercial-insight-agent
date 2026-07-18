import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.material_processor import ingest_stream
from scripts.model_providers import ProviderError, analyze_material, call_text_model, provider_status


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class ModelProviderTest(unittest.TestCase):
    def make_root(self, temporary: str) -> Path:
        root = Path(temporary) / "agent"
        (root / "config").mkdir(parents=True)
        (root / "local").mkdir()
        source = Path(__file__).resolve().parents[1] / "config" / "model_providers.json"
        shutil.copyfile(source, root / "config" / "model_providers.json")
        return root

    def test_provider_status_never_returns_secret(self):
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "secret-value"}):
            payload = provider_status()
        serialized = json.dumps(payload)
        self.assertNotIn("secret-value", serialized)
        self.assertTrue(next(item for item in payload if item["id"] == "dashscope")["configured"])

    def test_deepseek_uses_openai_compatible_chat(self):
        captured = {}

        def transport(request, **_kwargs):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"choices": [{"message": {"content": "# 推理结果"}}], "usage": {"total_tokens": 12}})

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            result = call_text_model("系统", "输入", provider_id="deepseek", capability="reasoning", transport=transport)
        self.assertTrue(captured["url"].endswith("/chat/completions"))
        self.assertEqual(captured["body"]["model"], "deepseek-v4-pro")
        self.assertEqual(captured["body"]["thinking"], {"type": "enabled"})
        self.assertEqual(result["text"], "# 推理结果")

    def test_dashscope_video_is_sent_once_then_cached(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            material = ingest_stream(io.BytesIO(b"video-bytes"), "sample.mp4", job_id="job", privacy="internal", root=root)
            captured = {"calls": 0}

            def transport(request, **_kwargs):
                captured["calls"] += 1
                body = json.loads(request.data.decode("utf-8"))
                media = body["messages"][0]["content"][0]
                self.assertEqual(media["type"], "video_url")
                self.assertTrue(media["video_url"]["url"].startswith("data:video/mp4;base64,"))
                return FakeResponse({"choices": [{"message": {"content": "# 视频拆解"}}], "usage": {"total_tokens": 25}})

            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
                first = analyze_material(material["content_hash"], provider_id="dashscope", root=root, transport=transport)
                second = analyze_material(material["content_hash"], provider_id="dashscope", root=root, transport=transport)
            self.assertEqual(first["markdown"], "# 视频拆解")
            self.assertFalse(first["cached"])
            self.assertTrue(second["cached"])
            self.assertEqual(captured["calls"], 1)

    def test_restricted_material_requires_per_request_consent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            material = ingest_stream(io.BytesIO(b"video-bytes"), "private.mp4", job_id="job", privacy="restricted", root=root)
            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
                with self.assertRaises(ProviderError):
                    analyze_material(material["content_hash"], provider_id="dashscope", root=root)


if __name__ == "__main__":
    unittest.main()
