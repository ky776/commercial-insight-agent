# Brief Schema

## Required fields

- `mode`: capture, discuss, decide, or execute
- `goal`: one outcome-oriented sentence
- `audience`: the person who will use or receive the result
- `inputs`: source IDs, paths, URLs, or short user-provided facts
- `constraints`: cost, time, privacy, platform, format, or scope constraints
- `deliverable`: concrete output and expected format

## Control fields

- `confirmed_decisions`: choices that should not be reopened without new evidence
- `assumptions`: reversible working assumptions
- `blocking_questions`: no more than three questions whose answers change execution
- `knowledge_queries`: focused search phrases for the Vault
- `file_scope`: exact files or folders permitted for the task
- `budget_profile`: light, standard, or deep

## Example

```yaml
mode: execute
goal: 将一份行业报告转成可发布的短视频口播稿
audience: 中小品牌老板
inputs:
  - 10_Sources/2026-07-平台流量报告.md
constraints:
  - 90 秒以内
  - 区分事实和个人判断
deliverable: 抖音与视频号共用的口播稿、标题和分镜建议
confirmed_decisions:
  - 真人口播，不生成完整 AI 视频
assumptions:
  - 使用常温、克制、顾问型表达
blocking_questions: []
knowledge_queries:
  - 平台流量 企业号 本地 电商
file_scope:
  - 10_Sources/2026-07-平台流量报告.md
  - 30_Insights/
budget_profile: standard
```
