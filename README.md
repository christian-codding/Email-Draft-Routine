# Email Draft Routine

Runs every morning at 7 AM PT via GitHub Actions. Scans your Gmail inbox for emails that need a personal reply, drafts a response in your voice using Claude, and saves it to Gmail Drafts — never sends anything.

---

## How It Works

1. GitHub Actions triggers the script each morning at 7 AM PT.
2. `routine.py` fetches inbox threads where the last message isn't from you.
3. For each thread that doesn't already have a draft, Claude reads the full conversation and writes a reply in your style.
4. The draft lands in Gmail Drafts. You review, edit, and send at your leisure.

---

## One-Time Setup

### 1. Get a Google Cloud OAuth Client

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → Create or select a project.
2. Enable the **Gmail API** for the project.
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth Client ID**.
4. Application type: **Desktop app**.
5. Download the JSON and save it as `credentials.json` in this repo root (it's gitignored).

### 2. Authorize Gmail Access Locally

```bash
pip install -r requirements.txt
python gmail_auth.py   # Opens a browser — sign in and approve
```

This creates `token.json`. Keep it safe; it's your access key.

### 3. Generate Your Writing Style Profile

With `credentials.json` and `token.json` in place, and your `ANTHROPIC_API_KEY` set:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python setup_style.py
```

This reads your last 6 months of sent email, asks Claude to analyze your style, and writes `writing_style.md`. Review the file and adjust anything that doesn't sound right, then commit it.

### 4. Add GitHub Secrets

In your repo → **Settings → Secrets and variables → Actions**, add three secrets:

| Secret name | Value |
|---|---|
| `GMAIL_CREDENTIALS_JSON` | Contents of `credentials.json` |
| `GMAIL_TOKEN_JSON` | Contents of `token.json` |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |

### 5. Push and You're Done

```bash
git add .
git commit -m "Initial setup"
git push
```

GitHub Actions will run at 7 AM PT every day. You can also trigger it manually from the **Actions** tab anytime.

---

## Files

| File | Purpose |
|---|---|
| `routine.py` | Main script — runs every morning |
| `gmail_auth.py` | Gmail OAuth helper |
| `setup_style.py` | One-time: builds `writing_style.md` from your sent mail |
| `writing_style.md` | Your writing style profile (commit this after generating) |
| `.github/workflows/morning_routine.yml` | Cron schedule and GitHub Actions config |

---

## Adjusting the Schedule

Edit the cron line in `.github/workflows/morning_routine.yml`:

```yaml
- cron: '0 15 * * *'   # 7am PST / 8am PDT
```

[Crontab Guru](https://crontab.guru) is handy for building cron expressions.

---

## Refreshing Gmail Access

Google OAuth refresh tokens don't expire unless you revoke access. If the routine starts failing with auth errors, re-run `python gmail_auth.py` locally and update the `GMAIL_TOKEN_JSON` secret with the new `token.json` contents.
