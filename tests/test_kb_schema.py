import unittest
import json
from pathlib import Path


class TestKBSchema(unittest.TestCase):
    def test_legacy_kb_files_valid(self):
        """Legacy KB schema: backend/knowledgebase/deprecated/*.json should be
        lists of {question, answer} for backwards compatibility.
        Structured KB (faq.json, hours.json, etc.) is validated elsewhere.
        """
        legacy_dir = Path('backend/knowledgebase/deprecated')
        if not legacy_dir.exists():
            self.skipTest('legacy knowledgebase/deprecated folder not present')
        files = list(legacy_dir.glob('*.json'))
        for f in files:
            data = json.loads(f.read_text(encoding='utf-8'))
            self.assertIsInstance(data, list, f'{f.name} is not a list')
            for idx, row in enumerate(data):
                self.assertIsInstance(row, dict, f'{f.name}[{idx}] not an object')
                q = (row.get('question') or '').strip()
                a = (row.get('answer') or '').strip()
                self.assertTrue(q and a, f'{f.name}[{idx}] missing question/answer')

    def test_main_kb_files_are_json(self):
        """Structured KB files should be valid JSON (shape is validated by code)."""
        kb_dir = Path('backend/knowledgebase')
        self.assertTrue(kb_dir.exists(), 'knowledgebase folder missing')
        files = list(kb_dir.glob('*.json'))
        self.assertTrue(len(files) > 0, 'no KB json files found')
        for f in files:
            # Just ensure they parse as JSON
            try:
                json.loads(f.read_text(encoding='utf-8'))
            except Exception as e:
                self.fail(f'{f.name} is not valid JSON: {e}')


if __name__ == '__main__':
    unittest.main()
