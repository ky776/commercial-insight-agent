import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.content_generator import (
    GenerationError,
    approve_to_vault,
    generate,
    list_artifacts,
    revise,
    save_artifact,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class ContentGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.brief = {
            "id": "job-1",
            "goal": "分析平台流量变化",
            "audience": "中小品牌老板",
            "deliverable": "公众号文章大纲与标题候选",
            "deliverableType": "article_outline",
            "privacy": "internal",
            "constraints": ["事实与观点分开"],
        }
        self.evidence = [{
            "title": "企业号成为经营阵地",
            "heading": "核心判断",
            "citation": "[[30_Insights/企业号.md#核心判断]]",
            "confidence": "medium",
            "excerpt": "平台流量向企业经营场景迁移。",
        }]

    def test_evidence_mode_preserves_citations(self):
        result = generate(self.brief, self.evidence, provider="evidence")
        self.assertEqual(result.provider, "evidence")
        self.assertIn("[[30_Insights/企业号.md#核心判断]]", result.markdown)
        self.assertIn("本地证据模式", result.markdown)

    def test_restricted_content_rejects_explicit_cloud_provider(self):
        brief = {**self.brief, "privacy": "restricted"}
        with self.assertRaises(GenerationError):
            generate(brief, self.evidence, provider="openai")

    def test_cloud_generation_excludes_restricted_evidence(self):
        response = {"output_text": "# 安全工作稿"}
        captured = {}

        def transport(request, **_kwargs):
            captured.update(json.loads(request.data.decode("utf-8")))
            return FakeResponse(response)

        restricted = {
            **self.evidence[0],
            "title": "公司内部材料",
            "excerpt": "不得离开本机的内容",
            "sensitivity": "restricted",
        }
        public = {**self.evidence[0], "sensitivity": "public"}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            generate(self.brief, [restricted, public], provider="openai", transport=transport)
        self.assertNotIn("不得离开本机的内容", captured["input"])
        self.assertIn(public["excerpt"], captured["input"])

    def test_openai_response_and_versioned_artifacts(self):
        response = {"output": [{"content": [{"type": "output_text", "text": "# 模型工作稿"}]}], "usage": {"total_tokens": 42}}
        transport = lambda *_args, **_kwargs: FakeResponse(response)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}):
            result = generate(self.brief, self.evidence, provider="openai", transport=transport)
        self.assertEqual(result.markdown, "# 模型工作稿")
        self.assertEqual(result.model, "test-model")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = save_artifact(self.brief, result, root)
            second = save_artifact(self.brief, result, root)
            self.assertTrue(first.artifact_path.endswith("artifact-v001.md"))
            self.assertTrue(second.artifact_path.endswith("artifact-v002.md"))
            history = list_artifacts("job-1", root)
            self.assertEqual([item["version"] for item in history], ["002", "001"])
            self.assertEqual(history[0]["status"], "draft")

    def test_scoped_revision_uses_existing_draft(self):
        response = {"output_text": "# 修改后的工作稿", "usage": {"total_tokens": 23}}
        captured = {}

        def transport(request, **_kwargs):
            captured.update(json.loads(request.data.decode("utf-8")))
            return FakeResponse(response)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            result = revise(self.brief, "# 原工作稿", "只修改开头", transport=transport)
        self.assertEqual(result.markdown, "# 修改后的工作稿")
        self.assertIn("只修改开头", captured["input"])
        self.assertIn("# 原工作稿", captured["input"])

    def test_approved_draft_is_written_to_content_vault(self):
        result = generate(self.brief, self.evidence, provider="evidence")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saved = save_artifact(self.brief, result, root / "outputs", status="approved")
            note = approve_to_vault(self.brief, saved, root / "vault")
            self.assertEqual(note.parent.name, "40_Content")
            content = note.read_text(encoding="utf-8")
            self.assertIn('status: "approved"', content)
            self.assertIn(saved.artifact_path, content)
            self.assertIn("本地证据模式", content)


if __name__ == "__main__":
    unittest.main()
