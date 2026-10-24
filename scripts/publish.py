"""Build the public Pages site, including listings readable without JavaScript."""
import html
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://syedrayanali53-art.github.io/Intern-dashboard/"
FIELDS = ("id", "company", "title", "url", "locations", "status", "season", "sponsorship", "first_seen", "last_seen", "last_verified", "verified")


def public_jobs(data):
    return [{key: job.get(key) for key in FIELDS} for job in data["jobs"].values()]


def directory(data):
    groups = {}
    for job in sorted(public_jobs(data), key=lambda j: (j["company"].casefold(), j["title"].casefold())):
        if job["status"] == "open":
            groups.setdefault(job["company"], []).append(job)
    parts = ['<h1>Intern Hunt internship directory</h1>',
             '<p><a href="intern-hunt.html">Interactive board</a> · <a href="jobs.json">JSON listings</a> · <a href="jobs.txt">Text listings</a> · <a href="source.txt">HTML, styling, and Scout source code</a> · <a href="llms.txt">Guide for AI readers</a></p>',
             '<p>Updated: ' + html.escape(str(data.get("generated_at", "Unknown"))) + '</p>',
             '<p>Public source listings grouped by company. Open means last reported open; verify the employer posting. Sponsorship not supplied means unknown. This directory includes all open roles before the interactive board’s filters.</p>']
    for company, jobs in groups.items():
        parts.append('<section><h2>' + html.escape(company) + '</h2><ul>')
        for job in jobs:
            address = str(job.get("url") or "")
            address = address if urlsplit(address).scheme in ("https", "http") else "#"
            details = " · ".join(str(value) for value in (", ".join(job.get("locations") or []), job.get("season"), job.get("sponsorship") or "Sponsorship not supplied") if value)
            parts.append('<li><a href="' + html.escape(address, quote=True) + '">' + html.escape(job["title"]) + '</a> — ' + html.escape(details) + '</li>')
        parts.append('</ul></section>')
    return '\n'.join(parts)


def build(root=ROOT, target=None):
    target = target or root / "_site"
    target.mkdir(parents=True, exist_ok=True)
    data = json.loads((root / "data/monitor.json").read_text(encoding="utf-8"))
    for name in ("intern-hunt.html", "monitor-ui.js", "monitor.css", "storage.js"):
        shutil.copy2(root / name, target / name)
    (target / "data").mkdir(exist_ok=True)
    shutil.copy2(root / "data/monitor-data.js", target / "data/monitor-data.js")
    content = directory(data)
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow"><title>Intern Hunt internship directory</title><style>body{max-width:1000px;margin:40px auto;padding:0 20px;font:16px/1.6 system-ui}li{margin:12px 0;overflow-wrap:anywhere}</style><body>' + content + '</body></html>'
    for name in ("index.html", "jobs.html"):
        (target / name).write_text(page, encoding="utf-8")
    board = (target / "intern-hunt.html").read_text(encoding="utf-8")
    links = '<p style="margin:20px;font:14px/1.5 system-ui">Read without JavaScript: <a href="jobs.html">internship directory</a> · <a href="jobs.txt">plain text</a> · <a href="jobs.json">JSON</a> · <a href="source.txt">HTML, styles, and Scout source code</a></p>'
    board = board.replace('</style>', '</style>\n' + links, 1)
    # Raw HTML readers see ordinary content; browsers can collapse the long directory.
    board += '\n<section id="public-directory" style="margin:24px;padding:20px;border:1px solid">' + content + '</section>\n<script>const publicDirectory=document.getElementById("public-directory");const directoryToggle=document.createElement("details");const directorySummary=document.createElement("summary");directorySummary.textContent="Public internship directory — readable without JavaScript";publicDirectory.before(directoryToggle);directoryToggle.append(directorySummary,publicDirectory);</script>\n'
    (target / "intern-hunt.html").write_text(board, encoding="utf-8")
    source_files = ('intern-hunt.html', 'monitor.css', 'monitor-ui.js', 'storage.js', 'scripts/monitor.py')
    source = '\n\n'.join('===== ' + name + ' =====\n' + (root / name).read_text(encoding="utf-8") for name in source_files)
    (target / "source.txt").write_text(source, encoding="utf-8")
    lines = ['Intern Hunt public listings', 'Updated: ' + str(data.get('generated_at', 'Unknown'))]
    for job in sorted(public_jobs(data), key=lambda j: (j['company'].casefold(), j['title'].casefold())):
        if job['status'] == 'open':
            lines.append('\n' + job['company'] + ' — ' + job['title'] + '\n' + str(job.get('url') or '') + '\n' + ', '.join(job.get('locations') or []) + '\n' + str(job.get('sponsorship') or 'Sponsorship unknown'))
    (target / "jobs.txt").write_text('\n'.join(lines), encoding="utf-8")
    (target / "jobs.json").write_text(json.dumps({"generated_at": data.get("generated_at"), "jobs": public_jobs(data)}, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / "llms.txt").write_text('# Intern Hunt\n\nPublic internship monitoring board. No login or JavaScript is required for the directory and JSON feed.\n\n- Directory: ' + BASE + 'jobs.html\n- Plain text listings: ' + BASE + 'jobs.txt\n- Structured data: ' + BASE + 'jobs.json\n- Complete HTML, CSS, Scout JavaScript, and monitoring source: ' + BASE + 'source.txt\n- Interactive board: ' + BASE + 'intern-hunt.html\n\nJSON includes open and closed listings. Check status, last_verified, verified, and sponsorship. Missing sponsorship is unknown. Employer links are the authoritative application destinations. Personal browser tracking is not included. Source code reveals styling and logic, but visual rendering requires a browser or screenshots.\n', encoding="utf-8")
    (target / "robots.txt").write_text('User-agent: *\nAllow: /Intern-dashboard/\nSitemap: ' + BASE + 'sitemap.xml\n', encoding="utf-8")
    (target / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>' + BASE + name + '</loc></url>' for name in ('', 'intern-hunt.html', 'jobs.html', 'jobs.json', 'llms.txt')) + '</urlset>', encoding="utf-8")


if __name__ == "__main__":
    build()

