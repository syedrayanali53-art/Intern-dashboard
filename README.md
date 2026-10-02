# Intern Hunt Dashboard

A daily job monitor dashboard that tracks internship postings across 125+ companies with automated updates, application tracking, and multi-platform job board support.

**Live Demo:** https://syedrayanali53-art.github.io/Intern-dashboard/

## Quick Start

### Local Setup
```sh
python scripts/monitor.py
python -m http.server 8000
```
Open `http://localhost:8000/public/intern-hunt.html`

### GitHub Automation
1. Fork/clone to your repository (include `.github/workflows/`)
2. Enable GitHub Actions and Issues in Settings
3. Go to Actions → Daily internship monitor → Run workflow
4. Schedule runs at **12:17 UTC daily** (configurable)

## Features

- **Daily Checks** - Monitors Greenhouse, Lever, Ashby, and Workday job feeds
- **Smart Tracking** - Detects new, reopened, closed, and changed positions
- **Filtering** - Search, location filters (DC/MD/VA/Remote), and ignore roles
- **Persistent Storage** - Browser-based backup/restore system
- **Community Feed** - Imports [Summer2027-Internships](https://github.com/vanshb03/Summer2027-Internships)

## Project Structure

```
├── public/                    # Dashboard interface
│   ├── intern-hunt.html      # Main dashboard
│   ├── monitor-ui.js         # UI logic
│   └── monitor.css           # Styling
├── scripts/                   # Backend automation
│   ├── monitor.py            # Job checker
│   ├── test_*.py             # Unit tests
│   └── Update jobs.cmd       # Windows helper
├── data/                      # Configuration & history
│   ├── companies.json        # Monitored companies & URLs
│   └── monitor.json          # Job history (auto-generated)
├── docs/                      # Additional documentation
└── .github/workflows/         # GitHub Actions automation
```

## Configuration

Edit `data/companies.json` to:
- Add/remove companies
- Change priority levels
- Update careers page URLs
- Toggle monitoring on/off

Company IDs remain stable when renaming.

## Alerts

By default, alerts notify for:
- **New** positions at curated companies
- **Reopened** roles
- **Careers page changes**
- Source failures (3+ consecutive days)

Change filter settings in the dashboard to customize.

## Running Tests

```sh
python -m unittest discover -s scripts -p 'test_*.py' -v
```

## Data Persistence

- **Browser Storage** - Personal changes saved locally (survives browser restart)
- **GitHub Storage** - `data/monitor.json` tracks all job history
- **Backup** - Use dashboard's "Back up tracking" feature when switching devices/browsers

## Notes

- No installation required beyond Python 3.11+
- Job data updates via GitHub Actions or manual runs
- All job URLs normalized; duplicate sources are combined
- Application status never overwritten by automated updates

---

For detailed setup and troubleshooting, see [SETUP.md](docs/SETUP.md) | [Workflow Guide](docs/WORKFLOW.md)
