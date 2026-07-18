#!/usr/bin/env python3
"""Generate cited content drafts from a task brief and local evidence."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


DEFAULT_MODEL = "gpt-5.6-luna"
PROMPT_FILES = {
    "short_video_script": "short_video_script.md",
    "article_outline": "article_outline.md",
    "material_analysis": "material_analysis.md",
}


class GenerationError(RuntimeError):
    """Raised when a configured generation provider cannot return a draft."""


@dataclass
class GenerationResult:
    markdown: str
    provider: str
    model: str | None
    usage: dict
    artifact_path: str | None = None


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def infer_deliverable_type(brief: dict) -> str:
    explicit = brief.get("deliverableType")
    if explicit:
        return explicit
    label = str(brief.get("deliverable", ""))
    if "短视频" in label or "口播" in label:
        return "short_video_script"
    if "公众号" in label or "文章" in label:
        return "article_outline"
    if "拆解" in label or "素材" in label:
        return "material_analysis"
    if "日报" in label:
        return "daily_digest"
    return "topic_pool"


def _list(items: list[str] | None, fallback: str = "待补充") -> str:
    values = [str(item).strip() for item in (items or []) if str(item).strip()]
    return "\n".join(f"- {item}" for item in values) if values else f"- {fallback}"


def evidence_markdown(evidence: list[dict]) -> str:
    if not evidence:
        return "当前知识库未检索到直接证据。不得把推测写成事实。"
    blocks = []
    for index, item in enumerate(evidence[:8], 1):
        blocks.append(
            f"[{index}] {item.get('title', '未命名')} / {item.get('heading', '正文')}\n"
            f"引用：{item.get('citation', item.get('path', ''))}\n"
            f"置信度：{item.get('confidence') or '未标注'}\n"
            f"片段：{item.get('excerpt', '')}"
        )
    return "\n\n".join(blocks)


def build_instructions(deliverable_type: str, root: Path | None = None) -> str:
    root = root or project_root()
    system = (root / "prompts" / "system.md").read_text(encoding="utf-8")
    prompt_name = PROMPT_FILES.get(deliverable_type)
    task = (root / "prompts" / prompt_name).read_text(encoding="utf-8") if prompt_name else ""
    return (
        f"{system}\n\n{task}\n\n"
        "额外规则：只使用给定 Brief 与证据包；事实、推断、建议必须分开；"
        "事实后保留 Obsidian 引用；证据不足时明确写待验证；不要编造案例、数据或来源。"
    )


def build_input(brief: dict, evidence: list[dict]) -> str:
    material_blocks = []
    for item in brief.get("materialExcerpts", [])[:6]:
        name = str(item.get("name", "未命名素材"))
        text = str(item.get("text", ""))[:12000]
        if text:
            material_blocks.append(f"### {name}\n\n{text}")
    materials = "\n\n".join(material_blocks) or "未提供可直接解析的正文。"
    return f"""# 已确认任务 Brief

- 目标：{brief.get('goal', '待确认')}
- 目标受众：{brief.get('audience', '待确认')}
- 产物：{brief.get('deliverable', '待确认')}
- 隐私级别：{brief.get('privacy', 'internal')}

## 输入来源
{_list(brief.get('inputs'))}

## 约束
{_list(brief.get('constraints'))}

## 工作假设
{_list(brief.get('assumptions'))}

## 用户选择的素材正文
{materials}

## 本地知识库证据包
{evidence_markdown(evidence)}

请直接输出可供人工编辑的 Markdown 草稿。不要解释你的工作过程。
"""


def evidence_only_draft(brief: dict, evidence: list[dict]) -> str:
    kind = infer_deliverable_type(brief)
    title = brief.get("goal") or brief.get("deliverable") or "未命名任务"
    sources = "\n".join(
        f"- **{item.get('title', '未命名')}**：{item.get('excerpt', '')} {item.get('citation', '')}"
        for item in evidence
    ) or "- 暂无直接证据，需要补充素材或调整检索词。"
    material_lines = []
    for item in brief.get("materialExcerpts", [])[:6]:
        if item.get("text"):
            clean_text = re.sub(r"\s+", " ", str(item["text"]))[:500]
            material_lines.append(f"- **{item.get('name', '未命名素材')}**：{clean_text}")
    selected_materials = "\n".join(material_lines) or "- 未提供可直接解析的正文。"
    shared = f"""# {title}

> 本地证据模式：以下是结构化工作底稿，没有调用外部模型。所有结论需人工确认。

## 用户选择的素材

{selected_materials}

## 核心证据

{sources}

## 事实、推断与待验证

- **已知事实**：仅采用上方有引用的知识片段。
- **可讨论推断**：结合目标受众，判断这些变化如何影响预算、内容资产与经营效率。
- **待验证**：补充最新平台规则、案例口径和可公开数据。
"""
    if kind == "short_video_script":
        body = """
## 口播结构

1. **开头 3 秒**：直接指出品牌老板正在承担的具体成本问题。
2. **核心判断**：用一句话解释平台流量与企业内容经营之间的变化。
3. **证据或例子**：从核心证据中选择 1-2 条，不添加未证实数字。
4. **行动清单**：检查预算、内容资产、代理透明度三个环节。
5. **结尾 CTA**：邀请领取诊断清单或提交具体问题。

## 分镜建议

- 人物口播为主，关键判断使用简单字幕卡。
- 引用数据前显示来源，未经核验的数据不进入成片。
"""
    elif kind == "article_outline":
        body = """
## 标题方向

1. 成本越来越高，品牌老板真正该检查的不是投放按钮
2. 平台把流量推向企业经营后，中小品牌要补哪三项能力
3. 代理商报表之外，老板还应该看见什么

## 文章结构

1. 品牌老板能感知的问题
2. 常见误判与错误归因
3. 平台、内容与经营系统的底层变化
4. 可执行检查清单
5. 诊断或咨询的自然承接
"""
    elif kind == "material_analysis":
        body = """
## 素材拆解

- **目标受众与问题**：待人工确认。
- **开头钩子**：提炼原素材使用的痛点或信息差。
- **论证结构**：记录观点顺序、证据位置和 CTA。
- **可复用模式**：只复用结构，不复制表达与视觉资产。
- **风险**：核验版权、数据来源和敏感商业结论。
"""
    elif kind == "daily_digest":
        body = """
## 今日信号

- 按商业价值、证据可信度和内容适配度排序核心证据。

## 建议跟进

- 选出最多三条需要继续验证或转化为内容的信号。
"""
    else:
        body = """
## 候选选题

- 将每条核心证据转化为一个面向品牌老板的具体问题。
- 按客户相关性、差异化、证据强度和制作成本评分。
"""
    return shared + body


def extract_response_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()
    parts = []
    for output in payload.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])
    if not parts:
        raise GenerationError("模型响应中没有可用文本")
    return "\n".join(parts).strip()


def call_openai(
    brief: dict,
    evidence: list[dict],
    *,
    model: str | None = None,
    transport: Callable | None = None,
) -> GenerationResult:
    return _openai_request(
        instructions=build_instructions(infer_deliverable_type(brief)),
        input_text=build_input(brief, evidence),
        model=model,
        transport=transport,
    )


def _openai_request(
    *,
    instructions: str,
    input_text: str,
    model: str | None = None,
    transport: Callable | None = None,
) -> GenerationResult:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise GenerationError("未配置 OPENAI_API_KEY")
    model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 3200,
        "store": False,
    }
    request = urllib.request.Request(
        os.environ.get("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses"),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    opener = transport or urllib.request.urlopen
    try:
        with opener(request, timeout=120) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise GenerationError(f"模型请求失败（HTTP {exc.code}）：{detail}") from exc
    except (OSError, ValueError) as exc:
        raise GenerationError(f"模型请求失败：{exc}") from exc
    return GenerationResult(
        markdown=extract_response_text(response_payload),
        provider="openai",
        model=model,
        usage=response_payload.get("usage") or {},
    )


def revise(
    brief: dict,
    current_markdown: str,
    instruction: str,
    *,
    allow_external_model: bool = False,
    transport: Callable | None = None,
) -> GenerationResult:
    if brief.get("privacy") == "restricted" and not allow_external_model:
        raise GenerationError("受限资料需要明确确认后才能调用外部模型修改")
    if not current_markdown.strip() or not instruction.strip():
        raise GenerationError("当前工作稿和修改要求不能为空")
    instructions = (
        build_instructions(infer_deliverable_type(brief))
        + "\n\n你正在修改一份已有工作稿。严格按修改要求调整，未要求变化的部分尽量保持。"
        + "保留有效的 Obsidian 引用，不得通过改写制造新事实。只输出修改后的完整 Markdown。"
    )
    input_text = f"""# 任务目标
{brief.get('goal', '')}

# 本轮修改要求
{instruction.strip()}

# 当前工作稿
{current_markdown[:50000]}
"""
    return _openai_request(instructions=instructions, input_text=input_text, transport=transport)


def generate(
    brief: dict,
    evidence: list[dict],
    *,
    provider: str = "auto",
    allow_external_model: bool = False,
    transport: Callable | None = None,
) -> GenerationResult:
    privacy = brief.get("privacy", "internal")
    can_use_cloud = privacy != "restricted" or allow_external_model
    if provider == "openai" and not can_use_cloud:
        raise GenerationError("受限资料默认禁止发送给外部模型")
    if provider == "openai" or (provider == "auto" and can_use_cloud and os.environ.get("OPENAI_API_KEY")):
        cloud_evidence = [item for item in evidence if item.get("sensitivity") != "restricted"]
        return call_openai(brief, cloud_evidence, transport=transport)
    return GenerationResult(
        markdown=evidence_only_draft(brief, evidence),
        provider="evidence",
        model=None,
        usage={},
    )


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return slug[:64] or "task"


def save_artifact(
    brief: dict,
    result: GenerationResult,
    output_root: Path | None = None,
    *,
    status: str = "draft",
    revision_instruction: str | None = None,
) -> GenerationResult:
    output_root = output_root or project_root() / "local" / "outputs"
    task_dir = output_root / _safe_slug(str(brief.get("id") or brief.get("goal") or "task"))
    task_dir.mkdir(parents=True, exist_ok=True)
    versions = [int(path.stem.split("v")[-1]) for path in task_dir.glob("artifact-v*.md") if path.stem.split("v")[-1].isdigit()]
    version = max(versions, default=0) + 1
    artifact = task_dir / f"artifact-v{version:03d}.md"
    metadata = task_dir / f"artifact-v{version:03d}.json"
    artifact_temp = artifact.with_suffix(".md.tmp")
    metadata_temp = metadata.with_suffix(".json.tmp")
    artifact_temp.write_text(result.markdown, encoding="utf-8")
    metadata_payload = {
        "brief_id": brief.get("id"),
        "goal": brief.get("goal"),
        "deliverable_type": infer_deliverable_type(brief),
        "provider": result.provider,
        "model": result.model,
        "usage": result.usage,
        "status": status,
        "revision_instruction": revision_instruction,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_temp.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact_temp.replace(artifact)
    metadata_temp.replace(metadata)
    return replace(result, artifact_path=str(artifact))


def list_artifacts(job_id: str, output_root: Path | None = None) -> list[dict]:
    output_root = output_root or project_root() / "local" / "outputs"
    task_dir = output_root / _safe_slug(job_id)
    items = []
    for metadata in sorted(task_dir.glob("artifact-v*.json"), reverse=True):
        try:
            item = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        artifact = metadata.with_suffix(".md")
        if not artifact.is_file():
            continue
        item.update({
            "version": artifact.stem.split("-v")[-1],
            "artifact_path": str(artifact),
            "markdown": artifact.read_text(encoding="utf-8"),
        })
        items.append(item)
    return items


def approve_to_vault(brief: dict, result: GenerationResult, vault: Path) -> Path:
    content_dir = vault / "40_Content"
    content_dir.mkdir(parents=True, exist_ok=True)
    title = str(brief.get("goal") or "未命名内容").strip()[:80]
    safe_title = re.sub(r"[\\/:*?\"<>|]", "-", title).strip(" .") or "未命名内容"
    date = datetime.now().strftime("%Y-%m-%d")
    destination = content_dir / f"{date}-{safe_title}.md"
    suffix = 2
    while destination.exists():
        destination = content_dir / f"{date}-{safe_title}-{suffix}.md"
        suffix += 1
    frontmatter = {
        "type": "content-draft",
        "status": "approved",
        "channel": infer_deliverable_type(brief),
        "audience": brief.get("audience", ""),
        "source_artifact": result.artifact_path or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    yaml_lines = ["---", *[f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in frontmatter.items()], "---", ""]
    temporary = destination.with_suffix(".md.tmp")
    temporary.write_text("\n".join(yaml_lines) + result.markdown.strip() + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


def result_dict(result: GenerationResult) -> dict:
    return asdict(result)
