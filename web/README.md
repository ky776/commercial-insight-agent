# Local Founder Workspace

Start the local service from the repository root:

```bash
./scripts/run_workspace.sh
```

Open `http://127.0.0.1:4173`. Opening `index.html` directly only provides an offline layout preview; knowledge retrieval, model calls, uploads, and rendering require the local service.

The interface uses a two-level workbench:

- The outer workspace shows recent jobs, operating status, signal counts, and module entry points.
- A content job follows `素材 -> 任务简报 -> 生成内容 -> 审核交付`.
- A video project follows `脚本方案 -> 真人素材 -> Seedance 辅助镜头 -> 合成导出`.
- Signal collection and Obsidian imports stay available as separate modules.

Human A-roll and audio are stored locally. Finished 9:16 MP4 files are written to `local/projects/<project-id>/exports/`. Seedance is only called after a cost confirmation and its completed clips are stored under `local/video_outputs/`.

Browser local storage contains lightweight task summaries. Source files, parse caches, generated artifacts, and finished media use repository-local ignored directories or the private sibling Obsidian Vault.
