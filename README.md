# Intern Hunt daily monitor

Your original company board now includes a daily job monitor, with company priorities, per-role application tracking, search, DC/MD/VA and remote filters, unread updates, ignored roles, and backup/restore.

## Open the board

The hosted dashboard is available at [Intern Hunt](https://syedrayanali53-art.github.io/Intern-dashboard/intern-hunt.html).

The published **intern-hunt.html** is self-contained: styling, JavaScript, company seed, and a public job snapshot are embedded. Download it from the deployed site or the latest workflow artifact and open it directly. No accompanying files are required. The repository HTML is the source template; the publishing step embeds the latest monitoring snapshot.

The HTML file does not perform background checks by itself. The checker runs on GitHub or on your computer. “Reload results” reads the latest generated data; it does not scrape employers.

Your personal application changes stay in this browser's localStorage. Use **Back up tracking** before moving devices, switching browsers, changing the board's location, or clearing browser data. On the first upgraded load, both raw storage values are saved under `internhunt.backup.before-posting-v2` before migration. If that backup fails, existing tracking is left untouched and saves are disabled. Restore and reset also make recovery snapshots. Version 1 JSON backups and the original CSV columns remain compatible.

## Eligibility and bulk actions

Each posting is classified from its own title and captured description/requirements. Company reputation and legacy feed labels do not affect eligibility. `sponsorship_state` is `sponsors`, `silent`, `blocked`, or `review`. Explicit sponsorship/immigration support or acceptance of F-1/CPT/OPT candidates counts as positive. Silence is included; unavailable body text is labeled **Couldn't check**. Contradictory signals stay visible for review. Explicit refusal is hidden by default but retained. Citizenship/clearance requirements have a separate flag and visibility control.

The checker captures descriptions already provided by Greenhouse, Lever, Ashby, structured job pages, and community feeds. Workday search summaries and other title-only leads may not include readable requirements; those remain unchecked. Daily new/reopened alerts exclude only the individual posting's explicit refusal or citizenship/clearance flag.

Use **Select companies** in My companies or **Select roles** in Discover internships. Filter changes clear selections that are no longer shown. Company deletion removes personal cards and their saved links; monitored-role deletion hides those roles in this browser. Both have persistent undo. Deleted monitored roles are also recoverable using the **Deleted roles** filter.

## Turn on daily checks on GitHub

1. Put this folder's contents at the root of your own repository, including `.github/workflows/update-jobs.yml`. Use a private repository if you want the embedded company notes and application history from the original board to stay private.
2. Commit to the repository's default branch. The workflow needs **Read and write permissions** under Settings → Actions → General. Issues must be enabled. If branch protection prohibits bot commits, allow this workflow's data updates or use a dedicated repository.
3. Go to **Actions → Daily internship monitor → Run workflow**. Leave “Send pending GitHub issue digests” selected when you want alerts.
4. Use **Watch → Custom → Issues** on the repository and enable email notifications in your GitHub notification settings. Issue creation by the automation is not a guarantee of email delivery; your notification settings control it.
5. Each successful run updates the GitHub Pages dashboard and includes an **intern-hunt-board** download under Artifacts.

The schedule is **12:17 UTC daily**: 8:17 a.m. New York time during daylight saving time, 7:17 a.m. during standard time. GitHub schedules can be delayed. Schedules run from the default branch; inactive public repositories can have schedules disabled. [GitHub scheduling documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

The included workflow deploys the updated board to GitHub Pages in the same run. An old downloaded copy on your computer does not update when GitHub has new data.

## Run it on your computer

Install Python 3.11 or newer if it is not already available. No additional Python packages are needed. From this folder:

```sh
python scripts/monitor.py
python scripts/publish.py
python -m http.server 8000 --directory _site
```

Open `http://localhost:8000/intern-hunt.html`, or double-click `_site/intern-hunt.html` after building. On Windows you can use **Update jobs.cmd** to check and build. This is a manual check, not a Windows scheduled task.

To send pending GitHub issue digests manually, set `GH_TOKEN` and `GITHUB_REPOSITORY=owner/repository`, then run `python scripts/monitor.py --notify`. The token needs issue access. The scheduled workflow uses GitHub's built-in token; you do not need to paste credentials into any website or file.

## What the checker does

- Imports the community [Summer2027-Internships feed](https://github.com/vanshb03/Summer2027-Internships).
- Checks all enabled careers URLs in `data/companies.json`.
- Supports Greenhouse, Lever, Ashby, and Workday job feeds, including recognized boards linked or embedded in careers pages. Workday currently searches for `intern`; co-op-only titles that do not match that search may need a separate source.
- Extracts structured JobPosting data and internship links on other pages. These are partial sources, not complete inventories. Plain links are labeled unverified.
- Watches visible text on readable pages without a job feed. A change produces a **careers page changed** alert for manual review. Other page text changes can also cause these alerts, and jobs loaded only through JavaScript may be missed.
- Shows blocked, unreadable, or missing careers URLs in source coverage. It does not bypass access restrictions.

Most URLs came from your sheet. Missing careers URLs were supplemented from official employer sites where identifiable, and some ATS board URLs were recovered from matching imported job postings. Every configured source is listed in `data/companies.json`, including URL provenance. Remaining ambiguous companies are left visible as needing a careers URL.

Feed documentation: [Greenhouse](https://docs.greenhouse.io/job-board.html), [Lever](https://github.com/lever/postings-api), [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api). Workday uses its public careers search endpoint, which can change independently and is reported as a source failure if its format changes.

## Detection and alerts

The first successful check of each source establishes a baseline and does not call every existing role “new.” After that:

- **New:** a newly observed role.
- **Reopened:** a role observed open after previously being closed.
- **Closed:** explicitly inactive in a feed, or absent on two distinct days of successful complete checks. Partial pages and failed checks never close roles merely because a role is missing.
- **Changed:** title, location, season, or sponsorship details changed. These are retained in history, without an email digest by default.

Job URLs are normalized and source IDs are retained. Matching URLs from different sources are combined; different employer URLs for the same requisition may still need manual deduplication. If another source still reports a role open, it remains open, with the last verification time shown. A site being reachable or a community feed marking a job active does not guarantee that applications are still accepted.

Alerts default to new/reopened roles at your 125 curated companies, careers page changes, and sources failing on three daily checks. All other community roles remain browsable by unchecking **My companies only**. Set `alerts_watchlist_only` to `false` for new/reopened alerts from the whole community feed. Digests contain up to 100 queued changes per run. Recorded event markers recover receipts after retries, checking the repository's most recent 100 issues.

Your original company status and per-role application status are separate. Automated job updates never overwrite either. Adding a role to a company leaves that company's current application status in place.

## Maintain the watchlist

Edit `data/companies.json` to change priorities, aliases, URLs, or `enabled`. Company IDs are stable; keep them when renaming a company. Use actual careers search pages or ATS board URLs to discover future roles. Individual old job links generally cannot reveal new positions.

Adding a company in the browser adds a personal tracking card only. To schedule checks for it, also add it to `data/companies.json`. Browser filters do not change scheduled alert criteria. Unknown sponsorship is shown as unknown, and the checker does not infer internship year from a repository's name.

The history lives in `data/monitor.json`. Keep it when upgrading so first-seen dates and reopen detection are preserved. Publishing embeds the public snapshot into the HTML and exposes a public JSON refresh endpoint without notification receipts. No personal browser tracking is published. Static HTML, text and JSON directories remain available to readers that do not run JavaScript.

## Tests

```sh
python -m unittest discover -s scripts -p 'test_*.py' -v
node scripts/test_eligibility.cjs
```

Tests cover baselines, new/reopened roles, failed and partial sources, duplicate sources, changed URLs, pagination, page-change alerts, and retry-safe notification receipts. The board was also checked in Chrome for rendering, search, persistent application status, source reload, Scout feed, and mobile overflow. No real GitHub digest was sent during local testing.

`scripts/test_board.cjs` runs the browser integration checks when Playwright and Chrome are available (set `CHROME_PATH` if needed). It checks per-posting filtering, migration backups, deletion/undo, backward-compatible file formats, mobile layout, and the standalone build.
