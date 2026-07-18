#!/usr/bin/env python3
"""Install the project brief-router as a global Codex skill without copying it."""

from __future__ import annotations

import os
from pathlib import Path


MARKER_START = "<!-- commercial-insight brief-router:start -->"
MARKER_END = "<!-- commercial-insight brief-router:end -->"
GLOBAL_GUIDANCE = f"""{MARKER_START}
For every substantive request, apply the global `brief-router` skill before expensive retrieval, analysis, or generation. Answer trivial direct questions directly. Use the private communication profile from `$CODEX_HOME/brief-router/profile.yaml` when relevant. Ask no more than three blocking questions. Never change the profile without explicit user confirmation.
{MARKER_END}
"""


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    source_skill = repo_root / "skills" / "brief-router"
    source_profile = repo_root / "local" / "preferences" / "communication_profile.yaml"
    fallback_profile = source_skill / "assets" / "default-profile.yaml"

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    skills_dir = codex_home / "skills"
    destination = skills_dir / "brief-router"
    profile_dir = codex_home / "brief-router"
    profile_path = profile_dir / "profile.yaml"
    guidance_path = codex_home / "AGENTS.md"

    skills_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    if destination.is_symlink():
        if destination.resolve() != source_skill.resolve():
            raise RuntimeError(f"Existing brief-router points elsewhere: {destination}")
    elif destination.exists():
        raise RuntimeError(f"Destination already exists and is not a symlink: {destination}")
    else:
        destination.symlink_to(source_skill, target_is_directory=True)

    if not profile_path.exists():
        profile_source = source_profile if source_profile.exists() else fallback_profile
        profile_path.write_text(profile_source.read_text(encoding="utf-8"), encoding="utf-8")

    existing = guidance_path.read_text(encoding="utf-8") if guidance_path.exists() else ""
    if MARKER_START not in existing:
        separator = "" if not existing or existing.endswith("\n") else "\n"
        guidance_path.write_text(existing + separator + GLOBAL_GUIDANCE, encoding="utf-8")

    print(f"Global skill: {destination} -> {source_skill}")
    print(f"Private profile: {profile_path}")
    print(f"Global guidance: {guidance_path}")
    print("Restart Codex or start a new task to load the global skill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
