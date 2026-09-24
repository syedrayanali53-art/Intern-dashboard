import copy
import unittest
from unittest.mock import patch
from monitor import canonical, job, reconcile, collect, provider, page_jobs, ats_jobs, notify

CONFIG = {"alerts_watchlist_only": True, "companies": [{"id": "acme", "name": "Acme", "priority": "P1", "careers_urls": ["https://example.com/careers"], "enabled": True}]}
SOURCE = {"id": "s", "company": "Acme", "kind": "careers", "url": "https://example.com/careers"}
ROLE = job("Acme", "Data Analyst Intern", "https://example.com/jobs/42", ["Reston, VA"], source_ref="42")


def run(old=None, roles=None, day=1, complete=True, error=None, sources=None):
    sources = sources or [SOURCE]
    result = {"error": error} if error else {"jobs": roles if roles is not None else [ROLE], "complete": complete, "method": "test"}
    return reconcile(old or {}, {s["id"]: copy.deepcopy(result) for s in sources}, sources, CONFIG, f"2026-09-{day:02}T12:00:00+00:00")


class MonitorTests(unittest.TestCase):
    def test_first_check_is_quiet(self):
        data = run()
        self.assertEqual(len(data["jobs"]), 1)
        self.assertEqual(data["events"], [])
        self.assertEqual(data["notifications"], [])

    def test_new_role_then_unchanged_is_one_alert(self):
        first = run(roles=[])
        second = run(first, day=2)
        third = run(second, day=3)
        self.assertEqual([e["kind"] for e in third["events"]], ["new"])
        self.assertEqual(len(third["notifications"]), 1)

    def test_two_distinct_days_close_then_reopen(self):
        data = run()
        data = run(data, [], 2)
        data = run(data, [], 2)
        self.assertEqual(next(iter(data["jobs"].values()))["status"], "open")
        data = run(data, [], 3)
        self.assertEqual(next(iter(data["jobs"].values()))["status"], "closed")
        data = run(data, day=4)
        self.assertEqual([e["kind"] for e in data["events"]], ["closed", "reopened"])
        self.assertEqual(data["notifications"][0]["kind"], "reopened")

    def test_failures_do_not_close_roles(self):
        data = run()
        for day in range(2, 6):
            data = run(data, day=day, error="timeout")
        self.assertEqual(next(iter(data["jobs"].values()))["status"], "open")
        self.assertEqual(len(data["notifications"]), 1)

    def test_partial_sources_never_close_missing_roles(self):
        data = run()
        for day in range(2, 6):
            data = run(data, [], day, complete=False)
        self.assertEqual(next(iter(data["jobs"].values()))["status"], "open")

    def test_explicit_inactive_closes(self):
        data = run()
        data = run(data, [{**ROLE, "active": False}], 2)
        self.assertEqual(next(iter(data["jobs"].values()))["status"], "closed")

    def test_cross_source_dedup(self):
        data = run(sources=[SOURCE, {**SOURCE, "id": "other"}])
        self.assertEqual(len(data["jobs"]), 1)
        self.assertEqual(len(next(iter(data["jobs"].values()))["observations"]), 2)

    def test_changed_url_same_source_id(self):
        data = run()
        data = run(data, [{**ROLE, "url": "https://example.com/jobs/42/new-slug"}], 2)
        self.assertEqual(len(data["jobs"]), 1)
        self.assertFalse(any(e["kind"] == "new" for e in data["events"]))

    def test_job_from_unwatched_company_no_notification(self):
        data = run(roles=[])
        data = run(data, [{**ROLE, "company": "Elsewhere"}], 2)
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["notifications"], [])

    def test_ineligible_job_is_not_queued_for_alerts(self):
        for label in ("U.S. Citizenship is Required", "Does Not Offer Sponsorship"):
            with self.subTest(label=label):
                role = {**ROLE, "sponsorship": label}
                duplicate = {**ROLE, "url": "https://example.com/jobs/43", "source_ref": "43"}
                data = run(run(roles=[]), [role, duplicate], 2)
                self.assertEqual(len(data["events"]), 2)
                self.assertEqual(data["notifications"], [])
                data["notifications"] = [{"job_id": key, "kind": "new"} for key in data["jobs"]]
                self.assertEqual(run(data, [role, duplicate], 3)["notifications"], [])

    def test_urls_keep_identity_parameters(self):
        self.assertEqual(canonical("https://example.com/job?jobId=42&utm_source=feed#top"), "https://example.com/job?jobId=42")
        self.assertEqual(canonical("https://jobs.lever.co/acme/abc/apply?utm_campaign=x"), "https://jobs.lever.co/acme/abc")
        for value in ("javascript:alert(1)", "file:///etc/passwd", "https://user:pass@example.com"):
            with self.assertRaises(ValueError): canonical(value)

    def test_malformed_source_is_failure(self):
        with patch('monitor.get_json', return_value={"error": "changed format"}):
            self.assertIn('error', collect({**SOURCE, "kind": "repo"}))

    def test_workday_pagination_is_complete(self):
        page1 = {"total": 2, "jobPostings": [{"title": "Data Intern", "externalPath": "/job/A/one_1", "locationsText": "VA"}]}
        page2 = {"total": 2, "jobPostings": [{"title": "Software Intern", "externalPath": "/job/A/two_2", "locationsText": "DC"}]}
        with patch('monitor.get_json', side_effect=[page1, page2]), patch('monitor.time.sleep'):
            jobs, full, _ = ats_jobs('https://acme.wd5.myworkdayjobs.com/en-US/External', 'Acme')
            self.assertEqual(len(jobs), 2)
            self.assertTrue(full)

    def test_structured_page_is_partial(self):
        page = '<script type="application/ld+json">{"@type":"JobPosting","title":"Data Intern","url":"/jobs/42"}</script>'
        with patch('monitor.request', return_value=(page, 'https://example.com/careers')):
            found, complete, _ = page_jobs('https://example.com/careers', 'Acme')
            self.assertFalse(complete)
            self.assertEqual(found[0]['url'], 'https://example.com/jobs/42')

    def test_page_change_is_not_a_new_role(self):
        first = {"jobs": [], "complete": False, "method": "page watch", "fingerprint": "a"}
        data = reconcile({}, {"s": first}, [SOURCE], CONFIG, '2026-09-01T12:00:00+00:00')
        self.assertEqual(data['events'], [])
        data = reconcile(data, {"s": {**first, "fingerprint": "b"}}, [SOURCE], CONFIG, '2026-09-02T12:00:00+00:00')
        self.assertEqual(data['events'][0]['kind'], 'page_changed')
        self.assertEqual(data['jobs'], {})

    def test_title_change_is_recorded(self):
        data = run()
        data = run(data, [{**ROLE, 'title': 'Business Analyst Intern'}], 2)
        self.assertEqual(data['events'][0]['kind'], 'changed')
        self.assertEqual(data['notifications'], [])

    def test_retry_recovers_issue_receipt_without_posting(self):
        data = run(run(roles=[]), day=2)
        event_id = data['notifications'][0]['id']
        issue = {'body': f'<!-- intern-hunt-event:{event_id} -->', 'html_url': 'https://github.com/me/jobs/issues/1'}
        with patch('monitor.github_api', return_value=[issue]) as api:
            notify(data, 'me/jobs')
            self.assertEqual(api.call_count, 1)
        self.assertTrue(data['notifications'][0].get('sent_at'))

    def test_greenhouse_embed_board_is_recognized(self):
        self.assertEqual(provider('https://boards.greenhouse.io/embed/job_board?for=acme'), ('greenhouse', 'acme', ''))


if __name__ == '__main__':
    unittest.main()
