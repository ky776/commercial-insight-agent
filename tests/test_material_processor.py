import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.material_processor import ingest_stream


class MaterialProcessorTest(unittest.TestCase):
    def test_text_upload_is_hashed_cached_and_keeps_unicode_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "agent"
            (root / "local").mkdir(parents=True)
            first = ingest_stream(
                io.BytesIO("广告成本与内容资产".encode()),
                "行业资料.md",
                job_id="job-one",
                privacy="internal",
                root=root,
            )
            second = ingest_stream(
                io.BytesIO("广告成本与内容资产".encode()),
                "行业资料.md",
                job_id="job-two",
                privacy="restricted",
                root=root,
            )
            self.assertEqual(first["parse_status"], "parsed")
            self.assertFalse(first["cached"])
            self.assertTrue(second["cached"])
            self.assertEqual(second["sensitivity"], "restricted")
            self.assertIn("行业资料.md", second["source_file"])
            self.assertIn("广告成本", second["extracted_text"])

    def test_pdf_upload_uses_local_parser_and_cache(self):
        bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
        if not bundled.is_file():
            self.skipTest("bundled PDF runtime unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "agent"
            vault = base / "commercial-insight-vault"
            (root / "local").mkdir(parents=True)
            (root / "scripts").mkdir()
            vault.mkdir()
            source_root = Path(__file__).resolve().parents[1]
            for name in ("ingest_pdf.py", "ingest_pdf.sh"):
                (root / "scripts" / name).write_bytes((source_root / "scripts" / name).read_bytes())
            pdf = base / "report.pdf"
            subprocess.run([
                str(bundled), "-c",
                "from pypdf import PdfWriter; w=PdfWriter(); w.add_blank_page(300,300); w.write(r'" + str(pdf) + "')",
            ], check=True)
            with pdf.open("rb") as stream:
                result = ingest_stream(stream, "测试报告.pdf", job_id="pdf-job", privacy="internal", root=root)
            self.assertEqual(result["parse_status"], "parsed")
            self.assertIn("PDF 提取文本", result["extracted_text"])
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["content_hash"], result["content_hash"])

    def test_video_is_stored_without_local_model_processing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "agent"
            (root / "local").mkdir(parents=True)
            result = ingest_stream(
                io.BytesIO(b"fake-video-content"),
                "sample.mp4",
                job_id="video-job",
                privacy="internal",
                root=root,
            )
            self.assertEqual(result["parse_status"], "stored")
            self.assertEqual(result["metadata"]["engine"], "external_model_api")
            self.assertEqual(result["extracted_text"], "")
            self.assertIn("等待选择外部模型", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
