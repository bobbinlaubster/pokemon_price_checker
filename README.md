# PriceChecker

This project tracks sealed Pokemon and One Piece product prices across multiple storefronts, stores history in SQLite, emails a daily summary, and includes a dashboard for browsing current offers.

## Fast workflow

Use the PowerShell helper scripts from the repo root:

- `./scripts/run-scrape.ps1 -MaxProducts 5`
  Runs a small scrape smoke test.
- `./scripts/run-dashboard.ps1`
  Opens the Streamlit dashboard.
- `./scripts/send-email.ps1`
  Sends the summary email using the current SQLite history.
- `./scripts/run-all.ps1 -MaxProducts 5 -OpenDashboard`
  Runs scrape, sends email, and optionally opens the dashboard.

## Main Python entrypoints

- `python price_checker.py`
  Runs the scraper, writes CSV/JSON/XLSX outputs, and updates `results/history.sqlite`.
- `python daily_email.py`
  Sends the daily pricing summary email from SQLite history.
- `streamlit run dashboard.py`
  Opens the dashboard showing current offers, price per pack, market price, and buy links.

## Output files

Each scraper run writes timestamped reports plus these stable files:

- `results/latest_snapshot.json`
- `results/latest_best_by_set.json`
- `results/history.sqlite`

## Optional market price support

If you set these environment variables, the dashboard will pull a current TCGplayer market baseline:

- `TCGPLAYER_PUBLIC_KEY`
- `TCGPLAYER_PRIVATE_KEY`

## Email environment variables

- `GMAIL_APP_PASSWORD`
- `EMAIL_SENDER`
- `EMAIL_RECIPIENT`
