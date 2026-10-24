import unittest
import json
from pathlib import Path
import tempfile
from publish import directory, public_jobs, build, ROOT


class PublishTests(unittest.TestCase):
    def test_public_directory_escapes_source_text_and_omits_private_fields(self):
        data = {"jobs": {"1": {"id": "1", "company": "A & B", "title": "<script>Intern</script>", "url": "javascript:alert(1)", "locations": ["VA"], "status": "open", "observations": {"private": True}}}, "notifications": [{"secret": True}]}
        page = directory(data)
        self.assertIn('A &amp; B', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('javascript:', page)
        self.assertNotIn('observations', public_jobs(data)[0])
        self.assertNotIn('notifications', public_jobs(data)[0])

    def test_build_is_self_contained_with_public_snapshot_and_static_listings(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'scripts').mkdir()
            (root / 'intern-hunt.html').write_text((ROOT / 'intern-hunt.html').read_text(encoding='utf-8'), encoding='utf-8')
            (root / 'scripts/monitor.py').write_text('# public checker', encoding='utf-8')
            data = {'jobs': {'x': {'id':'x', 'company':'Example', 'title':'Intern </script>', 'url':'https://example.com/job', 'locations':['VA'], 'status':'open', 'posting_text':'No sponsorship for full-time. OPT welcome.'}}, 'notifications':[{'private_receipt':True}], 'sources':{}, 'events':[], 'companies':[]}
            (root / 'data/monitor.json').write_text(json.dumps(data), encoding='utf-8')
            build(root)
            board = (root / '_site/intern-hunt.html').read_text(encoding='utf-8')
            self.assertNotRegex(board, r'<script[^>]+src=')
            self.assertNotIn('rel="stylesheet"', board)
            self.assertIn('id="public-directory"', board)
            self.assertIn('Intern &lt;/script&gt;', board)
            self.assertNotIn('private_receipt', board)
            exported = json.loads((root / '_site/jobs.json').read_text(encoding='utf-8'))['jobs'][0]
            self.assertEqual(exported['sponsorship_state'], 'review')
            self.assertEqual(board.count('</html>'), 1)


if __name__ == "__main__":
    unittest.main()
