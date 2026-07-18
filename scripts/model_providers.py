#!/usr/bin/env python3
"""API provider registry and multimodal material analysis adapters."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


class ProviderError(RuntimeError):
    """Raised when a model provider is unavailable or returns an invalid result."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_provider_config(root: Path | None = None) -> dict:
    root = root or project_root()
    return json.loads((root / "config" / "model_providers.json").read_text(encoding="utf-8"))


def provider_status(root: Path | None = None) -> list[dict]:
    config = load_provider_config(root)
    statuses = []
    for provider_id, item in config["providers"].items():
        key_env = item.get("api_key_env", "")
        statuses.append({
            "id": provider_id,
            "label": item.get("label", provider_id),
            "adapter": item.get("adapter"),
            "configured": bool(key_env and os.environ.get(key_env)),
            "apiKeyEnv": key_env,
            "capabilities": item.get("capabilities", []),
            "models": item.get("models", {}),
        })
    return statuses


def _provider(provider_id: str, capability: str, root: Path | None = None) -> tuple[dict, str, str]:
    config = load_provider_config(root)
    if provider_id == "auto":
        provider_id = config.get("routing", {}).get(capability, "")
    item = config.get("providers", {}).get(provider_id)
    if not item:
        raise ProviderError(f"未知模型供应商：{provider_id or '未配置'}")
    if capability not in item.get("capabilities", []):
        raise ProviderError(f"{item.get('label', provider_id)} 不支持 {capability}")
    key_env = item.get("api_key_env", "")
    api_key = os.environ.get(key_env, "")
    if not api_key:
        raise ProviderError(f"未配置 {key_env}")
    return item, provider_id, api_key


def _request_json(
    request: urllib.request.Request,
    *,
    transport: Callable | None = None,
    timeout: int = 180,
) -> dict:
    opener = transport or urllib.request.urlopen
    try:
        with opener(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise ProviderError(f"模型 API 请求失败（HTTP {exc.code}）：{detail}") from exc
    except (OSError, ValueError) as exc:
        raise ProviderError(f"模型 API 请求失败：{exc}") from exc


def _chat_text(payload: dict) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("兼容接口响应中没有可用文本") from exc
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict)).strip()
    raise ProviderError("兼容接口返回了无法识别的内容格式")


def _gemini_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()
    texts = []
    for step in payload.get("steps", []):
        for item in step.get("content", []):
            if isinstance(item, dict) and item.get("text"):
                texts.append(item["text"])
    if not texts:
        raise ProviderError("Gemini 响应中没有可用文本")
    return "\n".join(texts).strip()


def call_text_model(
    instructions: str,
    input_text: str,
    *,
    provider_id: str,
    capability: str = "text",
    model: str | None = None,
    root: Path | None = None,
    transport: Callable | None = None,
) -> dict:
    item, resolved_id, api_key = _provider(provider_id, capability, root)
    model = model or os.environ.get(f"{resolved_id.upper()}_{capability.upper()}_MODEL") or item["models"][capability]
    adapter = item["adapter"]
    if adapter == "openai_responses":
        payload = {
            "model": model,
            "instructions": instructions,
            "input": input_text,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 3200,
            "store": False,
        }
        endpoint = item["base_url"]
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    elif adapter in {"openai_chat", "openai_chat_multimodal"}:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "stream": False,
        }
        if resolved_id == "deepseek":
            payload["thinking"] = {"type": "enabled" if capability == "reasoning" else "disabled"}
            if capability == "reasoning":
                payload["reasoning_effort"] = "high"
        endpoint = item["base_url"].rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    elif adapter == "gemini_interactions":
        payload = {
            "model": model,
            "system_instruction": instructions,
            "input": [{"type": "text", "text": input_text}],
        }
        endpoint = item["base_url"]
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    else:
        raise ProviderError(f"尚未实现适配器：{adapter}")
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    response = _request_json(request, transport=transport)
    if adapter == "openai_responses":
        from content_generator import extract_response_text

        text = extract_response_text(response)
    elif adapter == "gemini_interactions":
        text = _gemini_text(response)
    else:
        text = _chat_text(response)
    return {"text": text, "provider": resolved_id, "model": model, "usage": response.get("usage") or response.get("usageMetadata") or {}}


def material_capability(media_type: str) -> str:
    if media_type.startswith("video/"):
        return "audio_video"
    if media_type.startswith("image/"):
        return "image"
    if media_type.startswith("audio/"):
        return "audio_video"
    return "text"


def material_analysis_prompt(original_name: str) -> str:
    return f"""你正在分析素材《{original_name}》，服务对象是有广告平台、商单变现和策略系统经验的商业化顾问。

请同时理解画面、屏幕文字、人物表达和声音信息，并输出 Markdown：
1. 核心内容与结论；
2. 按时间戳列出关键片段、画面、口播和论证作用；
3. 受众、钩子、叙事结构、证据与 CTA；
4. 可复用的内容结构与表达技巧，不复制原作者措辞；
5. 与广告效果、企业内容经营、品牌塑造、商业模式相关的洞见；
6. 适合公众号和短视频口播的选题方向；
7. 事实核验、版权与敏感信息风险。

事实、推断和建议分开；无法确认的内容标记为待验证。"""


def _analysis_cache_path(root: Path, content_hash: str, provider_id: str, model: str, prompt: str) -> Path:
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    safe_model = "".join(character if character.isalnum() or character in "._-" else "-" for character in model)
    return root / "local" / "cache" / "materials" / content_hash / "analyses" / f"{provider_id}-{safe_model}-{prompt_hash}.json"


def analyze_material(
    content_hash: str,
    *,
    provider_id: str = "auto",
    model: str | None = None,
    prompt: str | None = None,
    allow_external_model: bool = False,
    root: Path | None = None,
    transport: Callable | None = None,
) -> dict:
    root = root or project_root()
    manifest_path = root / "local" / "cache" / "materials" / content_hash / "manifest.json"
    if not manifest_path.is_file():
        raise ProviderError("素材不存在或尚未上传")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sensitivity") == "restricted" and not allow_external_model:
        raise ProviderError("受限素材默认禁止外发，请在本次任务中明确授权")
    source = Path(manifest["source_file"])
    if not source.is_file():
        raise ProviderError("素材原文件不存在")
    capability = material_capability(manifest.get("media_type", ""))
    item, resolved_id, api_key = _provider(provider_id, capability, root)
    model = model or os.environ.get(f"{resolved_id.upper()}_{capability.upper()}_MODEL") or item["models"][capability]
    prompt = prompt or material_analysis_prompt(manifest.get("original_name", source.name))
    cache_path = _analysis_cache_path(root, content_hash, resolved_id, model, prompt)
    if cache_path.is_file():
        return {**json.loads(cache_path.read_text(encoding="utf-8")), "cached": True}

    limit = int(load_provider_config(root).get("limits", {}).get("inline_media_bytes", 20_000_000))
    if source.stat().st_size > limit:
        raise ProviderError(f"首版 API 直传仅支持 {limit // 1_000_000} MB 以内素材；更大文件需下一步接厂商 Files API 或对象存储")
    mime_type = manifest.get("media_type") or mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    adapter = item["adapter"]
    if adapter == "openai_chat_multimodal":
        if mime_type.startswith("video/"):
            content_type = "video_url"
            media_part = {"type": content_type, content_type: {"url": f"data:{mime_type};base64,{encoded}"}}
        elif mime_type.startswith("audio/"):
            content_type = "input_audio"
            media_part = {"type": content_type, content_type: {"data": f"data:{mime_type};base64,{encoded}", "format": source.suffix.lstrip(".")}}
        else:
            content_type = "image_url"
            media_part = {"type": content_type, content_type: {"url": f"data:{mime_type};base64,{encoded}"}}
        if content_type == "video_url":
            media_part["fps"] = 1
        payload = {"model": model, "messages": [{"role": "user", "content": [media_part, {"type": "text", "text": prompt}]}], "stream": False}
        endpoint = item["base_url"].rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    elif adapter == "gemini_interactions":
        media_kind = "video" if mime_type.startswith("video/") else "audio" if mime_type.startswith("audio/") else "image"
        payload = {"model": model, "input": [{"type": media_kind, "data": encoded, "mime_type": mime_type}, {"type": "text", "text": prompt}]}
        endpoint = item["base_url"]
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    else:
        raise ProviderError(f"{item.get('label', resolved_id)} 当前不支持文件直传")
    request = urllib.request.Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
    response = _request_json(request, transport=transport, timeout=300)
    text = _gemini_text(response) if adapter == "gemini_interactions" else _chat_text(response)
    result = {
        "content_hash": content_hash,
        "original_name": manifest.get("original_name"),
        "provider": resolved_id,
        "model": model,
        "capability": capability,
        "markdown": text,
        "usage": response.get("usage") or response.get("usageMetadata") or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(cache_path)
    return result
