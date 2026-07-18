import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.conversation_importer import import_export, read_export


class ConversationImporterTest(unittest.TestCase):
    def test_chatgpt_export_and_duplicate_detection(self):
        payload = [{
            "id": "conversation-1",
            "title": "Obsidian 与 GitHub 配置",
            "create_time": 1784361600,
            "current_node": "assistant-1",
            "mapping": {
                "user-1": {
                    "id": "user-1", "parent": None,
                    "message": {"id": "user-message", "author": {"role": "user"}, "create_time": 1784361600, "content": {"parts": ["如何配置 Obsidian 和 GitHub？"]}},
                },
                "assistant-1": {
                    "id": "assistant-1", "parent": "user-1",
                    "message": {"id": "assistant-message", "author": {"role": "assistant"}, "create_time": 1784361660, "content": {"parts": ["先建立私有仓库，再配置 SSH。"]}},
                },
            },
        }]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "chatgpt-export.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("conversations.json", json.dumps(payload, ensure_ascii=False))
            vault = root / "vault"
            local = root / "local"
            report = import_export(source, vault, local, project="project-a")
            self.assertEqual(report["platform"], "chatgpt")
            self.assertEqual(report["questions"], 1)
            note = Path(report["notes"][0])
            self.assertIn("70_Conversations/Inbox", note.as_posix())
            content = note.read_text(encoding="utf-8")
            self.assertIn("问题分类：`operations`", content)
            self.assertIn("project-a", content)
            self.assertTrue(Path(report["raw_archive"]).is_file())
            duplicate = import_export(source, vault, local, project="project-a")
            self.assertTrue(duplicate["duplicate"])

    def test_restricted_markdown_stays_in_private_vault_and_redacts_secret(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "codex.md"
            source.write_text("## User\n配置 token: ghp_abcdefghijklmnop\n\n## Assistant\n不要把密钥写入 Git。", encoding="utf-8")
            report = import_export(source, root / "vault", root / "local", sensitivity="restricted")
            note = Path(report["notes"][0])
            self.assertIn("95_Private/Conversations", note.as_posix())
            self.assertNotIn("ghp_abcdefghijklmnop", note.read_text(encoding="utf-8"))
            normalized = Path(report["normalized"]).read_text(encoding="utf-8")
            self.assertNotIn("ghp_abcdefghijklmnop", normalized)

    def test_generic_jsonl(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "turns.jsonl"
            source.write_text(
                '{"role":"user","content":"如何创建 Agent？"}\n'
                '{"role":"assistant","content":"先定义目标和工具边界。"}\n',
                encoding="utf-8",
            )
            platform, conversations = read_export(source)
            self.assertEqual(platform, "codex")
            self.assertEqual(len(conversations[0].turns), 2)


if __name__ == "__main__":
    unittest.main()
