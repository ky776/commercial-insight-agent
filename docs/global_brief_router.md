# Global Brief Router

The project keeps one versioned `brief-router` source under `skills/brief-router`. A local installer links that source into the global Codex skills directory and creates a private communication profile outside Git.

Run:

```bash
cd /Users/ky/Documents/Codex/2026-07-01/wo/commercial-insight-agent
python3 scripts/install_global_brief_router.py
```

The installer:

- Creates `~/.codex/skills/brief-router` as a symlink to the project skill
- Creates `~/.codex/brief-router/profile.yaml`
- Adds a bounded brief-router rule to `~/.codex/AGENTS.md` without replacing existing guidance

Restart Codex or start a new task after installation.

The private profile is never committed. Preference updates require explicit confirmation and contain no raw conversation history.
