import unittest
from publish import directory, public_jobs


class PublishTests(unittest.TestCase):
    def test_public_directory_escapes_source_text_and_omits_private_fields(self):
        data = {"jobs": {"1": {"id": "1", "company": "A & B", "title": "<script>Intern</script>", "url": "javascript:alert(1)", "locations": ["VA"], "status": "open", "observations": {"private": True}}}, "notifications": [{"secret": True}]}
        page = directory(data)
        self.assertIn('A &amp; B', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('javascript:', page)
        self.assertNotIn('observations', public_jobs(data)[0])
        self.assertNotIn('notifications', public_jobs(data)[0])


if __name__ == "__main__":
    unittest.main()
