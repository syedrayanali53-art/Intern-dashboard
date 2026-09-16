"""Daily internship monitor. Python 3.11+, standard library only."""
import argparse
import concurrent.futures
import hashlib
from functools import lru_cache
import html
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import time
import threading
from datetime import datetime, timezone
import urllib.error
import urllib.parse as url
import urllib.request as http

ROOT = Path(__file__).resolve().parents[1]
AGENT = "InternHuntMonitor/1.0 (personal daily public-job checker)"
INTERN = re.compile(r"\b(intern(?:ship)?s?|co[ -]?op|summer analyst|working student)\b", re.I)
TRACKING = {"source", "ref", "referrer", "gh_src", "lever-source", "lever-origin", "jr_id", "srsltid"}
CONTEXT = threading.local()


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def canonical(value):
    p = url.urlsplit(html.unescape(value.strip()))
    if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
        raise ValueError("Expected a public http(s) URL")
    query = sorted((k, v) for k, v in url.parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in TRACKING)
    path = p.path.rstrip("/")
    if p.hostname in ("jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com"):
        path = re.sub(r"/(apply|application)$", "", path)
    return url.urlunsplit((p.scheme, p.netloc.lower(), path, url.urlencode(query), ""))


def public_url(value):
    p = url.urlsplit(value)
    canonical(value)
    if p.port not in (None, 80, 443):
        raise ValueError("Only standard web ports are allowed")
    for item in socket.getaddrinfo(p.hostname, p.port or 443):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError("Private/local network destinations are not allowed")


class Redirects(http.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def request(address, payload=None, headers=None):
    public_url(address)
    body = json.dumps(payload).encode() if payload is not None else None
    req = http.Request(address, data=body, headers={"User-Agent": AGENT, "Accept": "application/json,text/html", **({"Content-Type": "application/json"} if body else {}), **(headers or {})})
    for attempt in range(2):
        remaining = getattr(CONTEXT, "deadline", time.monotonic() + 120) - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Source exceeded its two-minute time budget")
        try:
            with http.build_opener(Redirects()).open(req, timeout=min(20, remaining)) as response:
                raw = response.read(20_000_001)
                if len(raw) > 20_000_000:
                    raise ValueError("Source exceeds 20 MB limit")
                return raw.decode("utf-8", errors="replace"), response.url
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt or (payload is not None and url.urlsplit(address).hostname == "api.github.com"):
                raise
            time.sleep(min(5, int(exc.headers.get("Retry-After", "2")) if exc.headers.get("Retry-After", "").isdigit() else 2))
        except (TimeoutError, urllib.error.URLError):
            if attempt or (payload is not None and url.urlsplit(address).hostname == "api.github.com"):
                raise
            time.sleep(1)


def get_json(address, payload=None):
    return json.loads(request(address, payload)[0])


def job(company, title, address, locations=None, **extra):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Job title missing")
    address = canonical(address)
    return {"company": company, "title": html.unescape(title.strip()), "url": address,
            "locations": [str(x) for x in (locations or []) if x], "active": True, **extra}


def rows(data, key):
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise ValueError("Source format changed: missing " + key)
    return data[key]


def provider(address):
    p = url.urlsplit(address)
    parts = [x for x in p.path.split("/") if x]
    host = p.hostname or ""
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io") and parts:
        board = url.parse_qs(p.query).get("for", [parts[0]])[0]
        if board == "embed":
            return None
        return "greenhouse", board, "eu" if ".eu." in host else ""
    if host in ("jobs.lever.co", "jobs.eu.lever.co") and parts:
        return "lever", parts[0], "eu" if ".eu." in host else ""
    if host == "jobs.ashbyhq.com" and parts:
        return "ashby", parts[0], ""
    if host.endswith(".myworkdayjobs.com") and parts:
        parts = [x for x in parts if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", x)]
        return "workday", parts[0], host
    return None


def ats_jobs(address, company):
    return _ats_jobs(provider(address), company)


@lru_cache(maxsize=256)
def _ats_jobs(board, company):
    kind, token, region = board
    token = url.quote(token, safe="")
    if kind == "greenhouse":
        base = "boards-api.eu.greenhouse.io" if region else "boards-api.greenhouse.io"
        data = get_json(f"https://{base}/v1/boards/{token}/jobs")
        result = [job(company, x["title"], x["absolute_url"], [x.get("location", {}).get("name")], source_ref=str(x["id"])) for x in rows(data, "jobs")]
    elif kind == "lever":
        base = "api.eu.lever.co" if region else "api.lever.co"
        result = []
        for offset in range(0, 10000, 100):
            data = get_json(f"https://{base}/v0/postings/{token}?mode=json&skip={offset}&limit=100")
            if not isinstance(data, list):
                raise ValueError("Invalid Lever response")
            result.extend(job(company, x["text"], x["hostedUrl"], [x.get("categories", {}).get("location")], source_ref=x["id"], employment=x.get("categories", {}).get("commitment", "")) for x in data)
            if len(data) < 100:
                break
            time.sleep(.3)
        else:
            raise ValueError("Lever pagination limit reached")
    elif kind == "ashby":
        data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
        result = [job(company, x["title"], x["jobUrl"], [x.get("location")] + [l.get("location") for l in x.get("secondaryLocations", [])], source_ref=x["jobUrl"], employment=x.get("employmentType", ""), remote=x.get("isRemote", False), posted_at=x.get("publishedAt", "")) for x in rows(data, "jobs") if x.get("isListed", True)]
    else:
        tenant = region.split(".")[0]
        endpoint = f"https://{region}/wday/cxs/{tenant}/{token}/jobs"
        result, seen = [], set()
        for offset in range(0, 5000, 20):
            data = get_json(endpoint, {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": "intern"})
            page = rows(data, "jobPostings")
            total = data.get("total")
            if not isinstance(total, int) or total < 0:
                raise ValueError("Invalid Workday total")
            for x in page:
                path = x["externalPath"]
                if path in seen:
                    raise ValueError("Workday returned a repeated page")
                seen.add(path)
                result.append(job(company, x["title"], f"https://{region}/en-US/{token}{path}", [x.get("locationsText")], source_ref=path))
            if len(seen) >= total:
                break
            if not page:
                raise ValueError("Incomplete Workday pagination")
            time.sleep(.3)
        else:
            raise ValueError("Workday pagination limit reached")
    return [x for x in result if INTERN.search(x["title"] + " " + x.get("employment", ""))], True, kind


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.scripts, self.text = [], [], []
        self.anchor, self.ld = None, None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "nav", "header", "footer"):
            self.hidden += 1
        if tag == "a" and a.get("href"):
            self.anchor = [a["href"], ""]
        if tag == "iframe" and a.get("src"):
            self.links.append((a["src"], ""))
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.ld = ""

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)
        if self.anchor is not None:
            self.anchor[1] += data + " "
        if self.ld is not None:
            self.ld += data

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer"):
            self.hidden = max(0, self.hidden - 1)
        if tag == "a" and self.anchor:
            self.links.append(tuple(self.anchor))
            self.anchor = None
        if tag == "script" and self.ld is not None:
            try:
                self.scripts.append(json.loads(self.ld))
            except ValueError:
                pass
            self.ld = None


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def page_jobs(address, company):
    raw, final = request(address)
    if provider(final):
        return ats_jobs(final, company)
    page = Page()
    page.feed(raw)
    # Only follow an ATS board actually linked by the company's supplied page.
    embedded_urls = re.findall(r'https?://[^\s"\'<>\\]+', html.unescape(raw).replace('\\/', '/'))
    linked = list(dict.fromkeys(url.urljoin(final, href) for href in [x[0] for x in page.links] + embedded_urls if provider(url.urljoin(final, href))))
    if linked:
        jobs, complete = [], True
        boards = set()
        for linked_url in linked[:8]:
            key = provider(linked_url)
            if key in boards:
                continue
            boards.add(key)
            found, full, _ = ats_jobs(linked_url, company)
            jobs.extend(found)
            complete &= full
        return jobs, complete and len(linked) <= 8, "linked ATS"
    result = []
    for value in page.scripts:
        for x in walk(value):
            types = x.get("@type", [])
            if types != "JobPosting" and not (isinstance(types, list) and "JobPosting" in types):
                continue
            title = x.get("title", "")
            if not INTERN.search(title):
                continue
            locations = []
            for item in walk(x.get("jobLocation", [])):
                if item.get("addressLocality"):
                    locations.append(", ".join(str(item[k]) for k in ("addressLocality", "addressRegion", "addressCountry") if item.get(k)))
            expiry = str(x.get("validThrough", ""))[:10]
            result.append(job(company, title, url.urljoin(final, x.get("url") or final), locations, active=not(expiry and expiry < stamp()[:10]), posted_at=x.get("datePosted", "")))
    if result:
        return result, False, "structured page (partial coverage)"
    # A link is a discovery lead, not a verified open requisition.
    for href, title in page.links:
        title = " ".join(title.split())
        target = url.urljoin(final, href)
        if INTERN.search(title) and re.search(r"/(jobs?/|positions?/|requisition/)|[?&](job|req)[^=]*=", target, re.I):
            try:
                result.append(job(company, title, target, verified=False))
            except ValueError:
                continue
    if result:
        return result, False, "posting links (unverified leads)"
    text = " ".join(" ".join(page.text).split())
    if len(text) < 120 or re.search(r"verify (?:that )?you are human|access denied|just a moment|enable javascript and cookies", text, re.I):
        raise ValueError("Page blocked or requires JavaScript; needs a site-specific adapter")
    # Partial page watches alert for review; they never assert that a new job exists.
    return [], False, {"name": "page watch", "fingerprint": digest(text)}


def collect(source):
    CONTEXT.deadline = time.monotonic() + 120
    try:
        if source["kind"] == "repo":
            data = get_json(source["url"])
            if not isinstance(data, list) or not data:
                raise ValueError("Repository feed is empty or invalid")
            result = []
            for x in data:
                if not isinstance(x, dict) or not x.get("id") or not isinstance(x.get("active"), bool):
                    raise ValueError("Repository schema changed")
                if not x.get("url"):
                    continue
                result.append(job(x["company_name"], x["title"], x["url"], x.get("locations", []), active=x["active"] and x.get("is_visible", True), source_ref=str(x["id"]), season=x.get("season", ""), sponsorship=x.get("sponsorship", "Other"), posted_at=x.get("date_posted", "")))
            return {"jobs": result, "complete": True, "method": "repository"}
        if provider(source["url"]):
            result, complete, method = ats_jobs(source["url"], source["company"])
        else:
            result, complete, method = page_jobs(source["url"], source["company"])
        if isinstance(method, dict):
            return {"jobs": result, "complete": False, "method": method["name"], "fingerprint": method["fingerprint"]}
        return {"jobs": result, "complete": complete, "method": method}
    except Exception as exc:
        return {"error": str(exc)[:240]}


def normalized_company(name):
    name = re.sub(r"\b(inc|llc|corp|corporation|ltd)\b\.?", "", name.lower())
    return re.sub(r"[^a-z0-9]", "", name)


def sources_for(config):
    sources = [{"id": "repo:" + digest(address), "kind": "repo", "company": "Community feed", "url": address} for address in config["feeds"]]
    for c in config["companies"]:
        if not c.get("enabled", True):
            continue
        for address in c.get("careers_urls", []):
            sources.append({"id": c["id"] + ":" + digest(address), "kind": "careers", "company": c["name"], "company_id": c["id"], "url": address})
    return sources


def reconcile(old, results, sources, config, now):
    data = json.loads(json.dumps(old))
    data.setdefault("jobs", {})
    data.setdefault("sources", {})
    data.setdefault("events", [])
    data.setdefault("notifications", [])
    before = {key: value["status"] for key, value in data["jobs"].items()}
    old_details = {key: {k: value.get(k) for k in ("title", "locations", "season", "sponsorship")} for key, value in data["jobs"].items()}
    changed_ids, event_eligible = set(), set()
    aliases = {normalized_company(n): c for c in config["companies"] for n in [c["name"], *c.get("aliases", [])]}
    known_urls = {x["url"]: key for key, x in data["jobs"].items()}
    refs = {(sid, obs.get("source_ref")): key for key, x in data["jobs"].items() for sid, obs in x["observations"].items() if obs.get("source_ref")}
    active_sources = {s["id"] for s in sources}
    for sid, info in data["sources"].items():
        info["enabled"] = sid in active_sources
    for source in sources:
        sid = source["id"]
        result = results[sid]
        previous = data["sources"].get(sid, {})
        meta = {**previous, **source, "enabled": True, "last_attempt": now}
        if result.get("error"):
            failures = previous.get("failures", 0) + (previous.get("last_attempt", "")[:10] != now[:10])
            meta.update(status="error", error=result["error"], failures=failures)
            data["sources"][sid] = meta
            if failures >= 3 and previous.get("failures", 0) < 3:
                data["notifications"].append({"id": digest(sid + now + "error"), "kind": "source_error", "company": source["company"], "message": result["error"], "at": now})
            continue
        baseline = bool(previous.get("last_success"))
        meta.update(status="ok" if result["complete"] else "partial", method=result["method"], last_success=now, failures=0, error="", count=len(result["jobs"]))
        if result.get("fingerprint"):
            meta.update(status="page_watch", fingerprint=result["fingerprint"])
            if previous.get("fingerprint") and previous["fingerprint"] != result["fingerprint"]:
                entry = {"id": digest(sid + now + result["fingerprint"]), "kind": "page_changed", "at": now, "company": source["company"], "company_id": source.get("company_id"), "url": source["url"]}
                data["events"].append(entry)
                data["notifications"].append(entry)
        seen = set()
        for x in result["jobs"]:
            key = refs.get((sid, x.get("source_ref"))) or known_urls.get(x["url"]) or digest(x["url"])
            if key in seen:
                continue
            seen.add(key)
            known_urls[x["url"]] = key
            record = data["jobs"].get(key, {"id": key, "first_seen": now, "observations": {}})
            matching = aliases.get(normalized_company(x["company"]))
            record.update({k: v for k, v in x.items() if k not in ("active", "source_ref", "verified")})
            record.update(company_id=matching["id"] if matching else None, priority=matching["priority"] if matching else "P4", last_seen=now)
            record["observations"][sid] = {"state": "open" if x["active"] else "closed", "last_seen": now, "last_check": now, "missing": 0, "source_ref": x.get("source_ref"), "verified": x.get("verified", True)}
            data["jobs"][key] = record
            changed_ids.add(key)
            if baseline:
                event_eligible.add(key)
        if result["complete"]:
            for key, record in data["jobs"].items():
                obs = record["observations"].get(sid)
                if not obs or key in seen:
                    continue
                if obs.get("last_check", "")[:10] != now[:10]:
                    obs["missing"] = obs.get("missing", 0) + 1
                obs["last_check"] = now
                if obs["missing"] >= 2:
                    obs["state"] = "closed"
                changed_ids.add(key)
                if baseline:
                    event_eligible.add(key)
        data["sources"][sid] = meta
    new_events = []
    for key in changed_ids:
        record = data["jobs"][key]
        observations = list(record["observations"].values())
        record["status"] = "open" if any(o["state"] == "open" for o in observations) else "closed"
        record["verified"] = any(o["state"] == "open" and o.get("verified", True) for o in observations)
        record["last_verified"] = max((o["last_seen"] for o in observations if o["state"] == "open" and o.get("verified", True)), default=None)
        event = "new" if key not in before and record["status"] == "open" else "reopened" if before.get(key) == "closed" and record["status"] == "open" else "closed" if before.get(key) == "open" and record["status"] == "closed" else None
        if not event and key in old_details and any(record.get(k) != v for k, v in old_details[key].items()):
            event = "changed"
        if event and key in event_eligible:
            entry = {"id": digest(key + event + now), "job_id": key, "kind": event, "at": now, "company": record["company"], "title": record["title"], "url": record["url"], "locations": record["locations"], "company_id": record["company_id"], "verified": record["verified"]}
            new_events.append(entry)
            if event in ("new", "reopened") and (record["company_id"] or not config.get("alerts_watchlist_only", True)):
                data["notifications"].append(entry)
    data["events"] = (data["events"] + sorted(new_events, key=lambda e: (e["at"], e["company"], e["title"]))) [-2000:]
    data.update(version=1, generated_at=now, companies=[{k: c.get(k) for k in ("id", "name", "priority", "careers_urls", "enabled")} for c in config["companies"]])
    return data


def save(data, target):
    target.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, ensure_ascii=False)
    temp = target / "monitor.json.tmp"
    temp.write_text(content + "\n", encoding="utf-8")
    temp.replace(target / "monitor.json")
    public = {k: v for k, v in data.items() if k != "notifications"}
    (target / "monitor-data.js").write_text("window.INTERN_MONITOR = " + json.dumps(public, ensure_ascii=True).replace("<", "\\u003c") + ";\n", encoding="utf-8")


def github_api(path, payload=None):
    token = os.environ["GH_TOKEN"]
    return json.loads(request("https://api.github.com/" + path, payload, {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})[0])


def notify(data, repo):
    pending = [x for x in data["notifications"] if not x.get("sent_at")]
    if not pending:
        print("No new notifications")
        return
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ValueError("Invalid GitHub repository name")
    # A stable marker prevents duplicate issues after a retry or failed receipt commit.
    existing = github_api(f"repos/{repo}/issues?state=all&per_page=100&sort=created&direction=desc")
    for item in pending:
        receipt = next((issue for issue in existing if f'<!-- intern-hunt-event:{item["id"]} -->' in (issue.get("body") or "")), None)
        if receipt:
            item.update(sent_at=stamp(), issue_url=receipt["html_url"])
    batch = [item for item in pending if not item.get("sent_at")][:100]
    if not batch:
        print("Recovered existing digest receipts")
        return
    marker = "<!-- intern-hunt:" + digest("|".join(x["id"] for x in batch)) + " -->"
    found = next((x for x in existing if marker in (x.get("body") or "")), None)
    if not found:
        lines = [marker, "Intern Hunt found these changes:", ""]
        for x in batch:
            lines.append(f'<!-- intern-hunt-event:{x["id"]} -->')
            # Source text cannot inject Markdown mentions or arbitrary links.
            title = re.sub(r"[\[\]<>`*_@\\]", "", x.get("title", ""))
            company = re.sub(r"[\[\]<>`*_@\\]", "", x["company"])
            if x["kind"] == "source_error":
                lines.append(f"- Needs attention: {company}. Three daily checks failed. See source coverage on the board.")
            elif x["kind"] == "page_changed":
                safe_link = x["url"].replace("(", "%28").replace(")", "%29")
                lines.append(f"- Careers page changed: **{company}** — [review the page]({safe_link}). This is a page change, not a confirmed new role.")
            else:
                label = x["kind"].capitalize() + (" (unverified lead)" if not x.get("verified", True) else "")
                safe_link = x["url"].replace("(", "%28").replace(")", "%29").replace("\n", "")
                lines.append(f"- {label}: **{company}** — [{title}]({safe_link})")
        lines.extend(["", "Open your board for application tracking and source freshness. These are observations from public sources; check the employer posting before applying."])
        found = github_api(f"repos/{repo}/issues", {"title": "Intern Hunt: " + str(len(batch)) + " updates · " + stamp()[:10], "body": "\n".join(lines)})
    for x in batch:
        x.update(sent_at=stamp(), issue_url=found["html_url"])
    print("Digest:", found["html_url"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "data/companies.json")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--repo-only", action="store_true")
    parser.add_argument("--limit", type=int, help="Check only the first N sources, for diagnostics")
    parser.add_argument("--notify", action="store_true", help="Send pending GitHub issue digests")
    args = parser.parse_args()
    path = args.data_dir / "monitor.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if args.notify:
        notify(old, os.environ["GITHUB_REPOSITORY"])
        save(old, args.data_dir)
        return
    config = json.loads(args.config.read_text(encoding="utf-8"))
    all_sources = sources_for(config)
    selected = [s for s in all_sources if not args.repo_only or s["kind"] == "repo"]
    if args.limit:
        selected = selected[:args.limit]
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(collect, s): s for s in selected}
        for future in concurrent.futures.as_completed(futures):
            source = futures[future]
            result = future.result()
            results[source["id"]] = result
            print(source["company"], ":", result.get("error") or f'{len(result["jobs"])} roles ({result["method"]})', flush=True)
    data = reconcile(old, results, selected, config, stamp())
    # A diagnostic subset must not disable sources that were simply not checked.
    for source in all_sources:
        if source["id"] in data["sources"]:
            data["sources"][source["id"]]["enabled"] = True
    save(data, args.data_dir)
    print(f'Saved {len(data["jobs"])} jobs; {sum(bool(x.get("error")) for x in results.values())}/{len(results)} sources need attention')
    if results and all(x.get("error") for x in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
