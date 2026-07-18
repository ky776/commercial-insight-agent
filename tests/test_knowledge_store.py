import tempfile
import unittest
from pathlib import Path

from scripts.knowledge_store import index_status, rebuild_index, search_index
from scripts.brief_retrieve import parse_brief, retrieval_query


class KnowledgeStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.vault = self.root / "vault"
        self.database = self.root / "index.sqlite3"
        (self.vault / "10_Sources").mkdir(parents=True)
        (self.vault / "30_Insights").mkdir(parents=True)
        (self.vault / "95_Private").mkdir(parents=True)
        (self.vault / "10_Sources" / "广告成本.md").write_text(
            """---
type: source
status: verified
topics: [广告效果, 代理商]
confidence: high
---
# 广告成本为什么上升
## 核心事实
流量竞争加剧时，品牌需要同时检查素材效率、归因口径和代理商透明度。
""",
            encoding="utf-8",
        )
        (self.vault / "30_Insights" / "企业号.md").write_text(
            """---
type: insight
status: draft
topics: [企业号, 内容生态]
confidence: medium
---
# 企业号成为经营阵地
## 核心判断
平台流量向企业经营场景迁移，企业需要建设自己的内容能力。
""",
            encoding="utf-8",
        )
        (self.vault / "95_Private" / "内部归因.md").write_text(
            "# 内部归因材料\n## 限制信息\n广告归因内部测试材料。",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_index_and_chinese_search(self):
        report = rebuild_index(self.vault, self.database)
        self.assertEqual(report["notes"], 3)
        self.assertGreaterEqual(report["chunks"], 3)
        self.assertTrue(index_status(self.database)["ready"])

        results = search_index(self.database, "广告效果 代理商透明度", top_k=3)
        self.assertTrue(results)
        self.assertEqual(results[0]["path"], "10_Sources/广告成本.md")
        self.assertIn("[[10_Sources/广告成本.md#", results[0]["citation"])

    def test_type_filter(self):
        rebuild_index(self.vault, self.database)
        results = search_index(self.database, "企业号 内容生态", note_type="insight")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "insight")

    def test_private_directory_defaults_to_restricted(self):
        rebuild_index(self.vault, self.database)
        results = search_index(self.database, "内部归因")
        self.assertTrue(results)
        self.assertEqual(results[0]["sensitivity"], "restricted")

    def test_brief_query_uses_source_filename(self):
        brief = parse_brief("""# 分析这份报告，提炼核心观点，生成自媒体内容

## 输入来源

- 【光大证券】海外AI行业跟踪报告：美股AI算力需求火热如何看待下游AI应用产业趋势？.pdf

## 知识库检索词

- 分析这份报告
- 生成
""")
        query = retrieval_query(brief)
        self.assertIn("AI算力", query)
        self.assertIn("AI应用", query)


if __name__ == "__main__":
    unittest.main()
