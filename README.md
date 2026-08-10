# seminar-monitor

Watches [Harvard First-Year Seminars](https://firstyearseminarprogram.college.harvard.edu/seminars/)
for changes to the **"Fall Seminars with Open Seats"** list (the semester-filter
dropdown's category, WordPress term ID 32) and emails `azweiback1618@gmail.com`
whenever a seminar is added to or removed from that list.

## How it works

- `check_seminars.py` — fetches the page, extracts seminars tagged with term 32
  from the server-rendered HTML, diffs against `state.json`, and emails on changes
  via Gmail SMTP. Stdlib only.
- `.github/workflows/monitor.yml` — runs the script roughly every 15 minutes
  (GitHub cron is best-effort, so expect some delay) and commits the updated
  `state.json` back to the repo.

## Secrets (repo → Settings → Secrets and variables → Actions)

- `GMAIL_ADDRESS` — the Gmail account to send from
- `GMAIL_APP_PASSWORD` — a [Gmail App Password](https://myaccount.google.com/apppasswords) for that account
- `EMAIL_TO` — recipient address (optional; defaults to `GMAIL_ADDRESS`)

## Operations

- **Test manually:** Actions tab → "Monitor open-seat seminars" → Run workflow
  (or `gh workflow run monitor.yml`).
- **Stop monitoring:** disable the workflow in the Actions tab, or delete the repo.
- **Note:** GitHub pauses scheduled workflows after ~60 days without repo activity;
  state-update commits usually keep it alive, but if you get a "scheduled workflow
  disabled" email, re-enable it in the Actions tab.

## Run locally

```sh
GMAIL_ADDRESS=you@gmail.com GMAIL_APP_PASSWORD=xxxx python3 check_seminars.py
```

Without the env vars set, it prints the email it would have sent instead of sending.
