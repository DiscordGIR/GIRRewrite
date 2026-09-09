import ast
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def slash_command_names():
    names = []
    for source in (ROOT / "cogs").rglob("*.py"):
        if source.name.startswith("._"):
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                owner = decorator.func.value
                if not (isinstance(owner, ast.Name) and owner.id == "app_commands" and decorator.func.attr == "command"):
                    continue
                explicit_name = next(
                    (kw.value.value for kw in decorator.keywords if kw.arg == "name" and isinstance(kw.value, ast.Constant)),
                    None,
                )
                names.append(explicit_name or node.name)
    return names


class CommandRegistryTests(unittest.TestCase):
    def test_top_level_slash_names_are_unique(self):
        names = slash_command_names()
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        self.assertEqual(duplicates, [])

    def test_overlapping_commands_are_consolidated(self):
        names = set(slash_command_names())
        self.assertTrue({"avatar", "serverinfo", "announce", "kick", "roblox"}.issubset(names))
        self.assertTrue({"pfp", "membercount", "embed"}.isdisjoint(names))

    def test_registry_stays_below_discord_limit(self):
        self.assertLessEqual(len(slash_command_names()), 100)


if __name__ == "__main__":
    unittest.main()
