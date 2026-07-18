#!/usr/bin/env python3
"""Serve the local workspace UI, knowledge retrieval, and draft generation API."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
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
from social_collector import CollectionError, collect  # noqa: E402
from social_service import add_watch_source, default_social_paths, radar_status  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
MAX_BODY = 1_000_000


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
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
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
        except CollectionError as exc:
            self._json(502, {"ok": False, "error": str(exc)})
        except (OSError, RuntimeError) as exc:
            self._json(500, {"ok": False, "error": str(exc)})

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
