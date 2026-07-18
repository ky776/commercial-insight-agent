#!/usr/bin/env python3
"""Serve the local workspace UI, knowledge retrieval, and draft generation API."""

from __future__ import annotations

import argparse
import cgi
import json
import mimetypes
import os
import shutil
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from content_generator import (  # noqa: E402
    GenerationError,
    GenerationResult,
    approve_to_vault,
    generate,
    list_artifacts,
    result_dict,
    revise,
    save_artifact,
)
from knowledge_store import default_paths, index_status, rebuild_index, search_index  # noqa: E402
from material_processor import MaterialError, ingest_stream  # noqa: E402
from model_providers import ProviderError, analyze_material, provider_status  # noqa: E402
from social_collector import CollectionError, collect  # noqa: E402
from social_service import add_watch_source, default_social_paths, radar_status  # noqa: E402
from conversation_importer import import_export  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
MAX_BODY = 1_000_000
MAX_UPLOAD_BODY = 250_000_000
MAX_MATERIAL_UPLOAD = 100_000_000


def conversation_import_status() -> list[dict]:
    manifests = sorted((ROOT / "local" / "conversations").glob("*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    results = []
    for path in manifests[:20]:
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return results


def retrieve_for_brief(brief: dict, top_k: int = 8) -> list[dict]:
    vault, database = default_paths()
    if not index_status(database)["ready"]:
        rebuild_index(vault, database)
    material_text = " ".join(str(item.get("text", ""))[:3000] for item in brief.get("materialExcerpts", [])[:6])
    query_parts = [brief.get("goal", ""), *brief.get("knowledgeQueries", []), *brief.get("inputs", []), material_text]
    query = " ".join(str(item) for item in query_parts if item)
    return search_index(database, query, top_k=top_k)


def health_payload() -> dict:
    vault, database = default_paths()
    return {
        "ok": True,
        "service": "commercial-insight-workspace",
        "knowledge": {**index_status(database), "vault": str(vault)},
        "generation": {
            "openaiConfigured": bool(os.environ.get("OPENAI_API_KEY")),
            "defaultModel": os.environ.get("OPENAI_MODEL", "gpt-5.6-luna"),
            "evidenceMode": True,
            "providers": provider_status(ROOT),
        },
        "materials": {
            "maxUploadBytes": MAX_MATERIAL_UPLOAD,
            "localStorage": True,
            "localSemanticModels": False,
            "externalApiAnalysis": True,
            "inlineApiBytes": 20_000_000,
        },
    }


class WorkspaceHandler(BaseHTTPRequestHandler):
    server_version = "CommercialInsight/0.1"

    def log_message(self, message: str, *args) -> None:
        print(f"[workspace] {self.address_string()} {message % args}")

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            raise ValueError("请求体为空或超过 1 MB")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self._json(200, health_payload())
            return
        if path == "/api/artifacts":
            from urllib.parse import parse_qs

            job_id = parse_qs(parsed.query).get("jobId", [""])[0]
            if not job_id:
                self._json(400, {"ok": False, "error": "缺少 jobId"})
            else:
                self._json(200, {"ok": True, "artifacts": list_artifacts(job_id)})
            return
        if path == "/api/signals/status":
            config, local_dir = default_social_paths(ROOT)
            self._json(200, {"ok": True, **radar_status(config, local_dir)})
            return
        if path == "/api/conversations/status":
            self._json(200, {"ok": True, "imports": conversation_import_status()})
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/conversations/import":
                self._import_conversation()
                return
            if path == "/api/materials/upload":
                self._upload_material()
                return
            payload = self._body()
            if path == "/api/reindex":
                vault, database = default_paths()
                self._json(200, {"ok": True, "knowledge": rebuild_index(vault, database)})
                return
            if path == "/api/signals/sources":
                config, local_dir = default_social_paths(ROOT)
                added = add_watch_source(config, str(payload.get("sourceType", "")), str(payload.get("value", "")))
                self._json(200, {"ok": True, "added": added, **radar_status(config, local_dir)})
                return
            if path == "/api/signals/collect":
                config, local_dir = default_social_paths(ROOT)
                vault, database = default_paths()
                report = collect(config, vault, local_dir)
                knowledge = rebuild_index(vault, database)
                self._json(200, {"ok": True, "report": report, "knowledge": knowledge, **radar_status(config, local_dir)})
                return
            if path == "/api/materials/analyze":
                content_hash = str(payload.get("contentHash", "")).strip()
                if not content_hash:
                    raise ValueError("缺少素材 contentHash")
                result = analyze_material(
                    content_hash,
                    provider_id=str(payload.get("provider", "auto")),
                    model=str(payload.get("model", "")).strip() or None,
                    prompt=str(payload.get("prompt", "")).strip() or None,
                    allow_external_model=bool(payload.get("allowExternalModel", False)),
                    root=ROOT,
                )
                self._json(200, {"ok": True, "result": result})
                return
            brief = payload.get("brief")
            if not isinstance(brief, dict):
                raise ValueError("缺少 brief")
            if path == "/api/retrieve":
                evidence = retrieve_for_brief(brief, int(payload.get("topK", 8)))
                self._json(200, {"ok": True, "evidence": evidence})
                return
            if path == "/api/generate":
                evidence = retrieve_for_brief(brief, int(payload.get("topK", 8)))
                result = generate(
                    brief,
                    evidence,
                    provider=payload.get("provider", "auto"),
                    allow_external_model=bool(payload.get("allowExternalModel", False)),
                )
                result = save_artifact(brief, result)
                self._json(200, {"ok": True, "evidence": evidence, "result": result_dict(result)})
                return
            if path == "/api/artifacts/save":
                markdown = str(payload.get("markdown", "")).strip()
                if not markdown:
                    raise ValueError("工作稿不能为空")
                result = save_artifact(
                    brief,
                    GenerationResult(markdown=markdown, provider="human", model=None, usage={}),
                    revision_instruction=payload.get("revisionInstruction"),
                )
                self._json(200, {"ok": True, "result": result_dict(result), "artifacts": list_artifacts(str(brief.get("id", "task")))})
                return
            if path == "/api/artifacts/revise":
                result = revise(
                    brief,
                    str(payload.get("markdown", "")),
                    str(payload.get("instruction", "")),
                    allow_external_model=bool(payload.get("allowExternalModel", False)),
                )
                result = save_artifact(brief, result, revision_instruction=str(payload.get("instruction", "")))
                self._json(200, {"ok": True, "result": result_dict(result), "artifacts": list_artifacts(str(brief.get("id", "task")))})
                return
            if path == "/api/artifacts/approve":
                markdown = str(payload.get("markdown", "")).strip()
                if not markdown:
                    raise ValueError("工作稿不能为空")
                result = save_artifact(
                    brief,
                    GenerationResult(markdown=markdown, provider="human", model=None, usage={}),
                    status="approved",
                )
                vault, _ = default_paths()
                vault_path = approve_to_vault(brief, result, vault)
                self._json(200, {
                    "ok": True,
                    "result": result_dict(result),
                    "vaultPath": str(vault_path),
                    "artifacts": list_artifacts(str(brief.get("id", "task"))),
                })
                return
            self._json(404, {"ok": False, "error": "接口不存在"})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except GenerationError as exc:
            self._json(502, {"ok": False, "error": str(exc)})
        except ProviderError as exc:
            self._json(502, {"ok": False, "error": str(exc)})
        except CollectionError as exc:
            self._json(502, {"ok": False, "error": str(exc)})
        except MaterialError as exc:
            self._json(500, {"ok": False, "error": str(exc)})
        except (OSError, RuntimeError) as exc:
            self._json(500, {"ok": False, "error": str(exc)})

    def _upload_material(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_MATERIAL_UPLOAD:
            raise ValueError("素材文件为空或超过 100 MB")
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            raise ValueError("素材上传必须使用 multipart/form-data")
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type, "CONTENT_LENGTH": str(length)},
            keep_blank_values=True,
        )
        upload = form["file"] if "file" in form else None
        if upload is None or not getattr(upload, "filename", None):
            raise ValueError("缺少素材文件")
        privacy = str(form.getfirst("privacy", "internal"))
        if privacy not in {"public", "internal", "restricted"}:
            raise ValueError("隐私级别不正确")
        material = ingest_stream(
            upload.file,
            Path(upload.filename).name,
            job_id=str(form.getfirst("jobId", "capture")),
            privacy=privacy,
            root=ROOT,
        )
        self._json(200, {"ok": True, "material": material})

    def _import_conversation(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_BODY:
            raise ValueError("会话导出文件为空或超过 250 MB")
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            raise ValueError("会话导入必须使用 multipart/form-data")
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type, "CONTENT_LENGTH": str(length)},
            keep_blank_values=True,
        )
        upload = form["file"] if "file" in form else None
        if upload is None or not getattr(upload, "filename", None):
            raise ValueError("缺少会话导出文件")
        filename = Path(upload.filename).name
        if Path(filename).suffix.lower() not in {".zip", ".json", ".jsonl", ".md", ".txt"}:
            raise ValueError("仅支持 ZIP、JSON、JSONL、Markdown 和 TXT")
        project = str(form.getfirst("project", "")).strip() or None
        if project and project not in {"project-a", "project-b", "project-c", "project-d"}:
            raise ValueError("项目 ID 不正确")
        sensitivity = str(form.getfirst("sensitivity", "internal"))
        if sensitivity not in {"public", "internal", "restricted"}:
            raise ValueError("敏感级别不正确")
        upload_dir = ROOT / "local" / "uploads" / "conversations"
        upload_dir.mkdir(parents=True, exist_ok=True)
        temporary = upload_dir / filename
        with temporary.open("wb") as destination:
            shutil.copyfileobj(upload.file, destination)
        try:
            vault, database = default_paths()
            report = import_export(temporary, vault, ROOT / "local", project, sensitivity)
            knowledge = rebuild_index(vault, database)
        finally:
            temporary.unlink(missing_ok=True)
        self._json(200, {"ok": True, "report": report, "knowledge": knowledge, "imports": conversation_import_status()})

    def _serve_static(self, raw_path: str) -> None:
        relative = unquote(raw_path).lstrip("/") or "index.html"
        target = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    parser.add_argument("--port", default=4173, type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), WorkspaceHandler)
    print(f"Commercial Insight Workspace: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
