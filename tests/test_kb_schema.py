import unittest
import json
from pathlib import Path


class TestKBSchema(unittest.TestCase):
    def test_kb_files_valid(self):
        kb_dir = Path('backend/knowledgebase')
        self.assertTrue(kb_dir.exists(), 'knowledgebase folder missing')
        files = list(kb_dir.glob('*.json'))
        self.assertTrue(len(files) > 0, 'no KB json files found')
        for f in files:
            data = json.loads(f.read_text(encoding='utf-8'))
            self.assertIsInstance(data, list, f'{f.name} is not a list')
            for idx, row in enumerate(data):
                self.assertIsInstance(row, dict, f'{f.name}[{idx}] not an object')
                q = (row.get('question') or '').strip()
                a = (row.get('answer') or '').strip()
                self.assertTrue(q and a, f'{f.name}[{idx}] missing question/answer')


if __name__ == '__main__':
    unittest.main()

