# Cold Outreach Tracker

A local CLI tool that tracks cold outreach emails you've sent, detects replies via Gmail, and automatically classifies each reply as **Interested**, **Not Interested**, **Needs Follow-up**, or **Unclassified** using the Claude AI API.

---

## How it works

1. You send a cold email yourself (via Gmail or any email client)
2. You log it with `outreach-track add`
3. Run `outreach-track sync` periodically — it polls Gmail for replies and classifies them automatically
4. Use `outreach-track list` and `outreach-track show` to review your pipeline

---

## Requirements

- Python 3.11+
- A Google account (Gmail)
- A Google Cloud project with the Gmail API enabled
- An [Anthropic API key](https://console.anthropic.com) for reply classification

---

## Installation

```bash
git clone https://github.com/puneeth9/Cold_Outreach.git
cd Cold_Outreach
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=sqlite:///./outreach.db

GOOGLE_CLIENT_SECRET_FILE=./client_secret.json
GOOGLE_CREDENTIALS_FILE=./token.json

ANTHROPIC_API_KEY=sk-ant-...
```

---

## Google Cloud Setup (one-time)

You need a GCP project with the Gmail API enabled and an OAuth client credentials file.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project (or select an existing one)
3. Go to **APIs & Services → Library** → search for **Gmail API** → Enable it
4. Go to **APIs & Services → OAuth consent screen**
   - User type: **External**
   - Fill in app name and your email
   - Under **Audience**, add your Gmail address as a test user
5. Go to **APIs & Services → Credentials → + Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Desktop app**
   - Click **Create** → **Download JSON**
6. Save the downloaded file as `client_secret.json` in the project root

---

## Database Setup

```bash
alembic upgrade head
```

---

## Gmail Authentication (one-time)

```bash
outreach-track auth
```

This opens a browser window. Sign in with your Gmail account and approve access. A `token.json` file is saved automatically — you won't need to run this again unless the token is deleted or revoked.

---

## Daily Usage

### Log a sent outreach email

```bash
outreach-track add \
  --to recruiter@company.com \
  --name "Jane Smith" \
  --company "Acme Corp" \
  --subject "Software Engineer role" \
  --sent-at "2026-04-21T10:30:00"
```

If you omit `--body-file`, you'll be prompted to paste the email body interactively — type your text and enter `EOF` on a new line to finish.

To read the body from a file:

```bash
outreach-track add \
  --to recruiter@company.com \
  --name "Jane Smith" \
  --subject "Software Engineer role" \
  --body-file ./email.txt
```

`--sent-at` defaults to the current time if omitted.

---

### Check for replies

```bash
outreach-track sync
```

For each outreach with status `awaiting_reply`, this polls Gmail for messages from that recipient and:
- Records any replies found
- Classifies each reply using Claude
- Updates the outreach status to `replied`

Run this whenever you want to check for new replies. Duplicate replies are handled automatically via Gmail message ID deduplication.

---

### List all outreaches

```bash
outreach-track list
```

Filter by status:

```bash
outreach-track list --status awaiting_reply
outreach-track list --status replied
outreach-track list --status archived
```

---

### View a single outreach and its replies

```bash
outreach-track show <id>
```

Shows the full outreach detail, body, and a table of all replies with their classification, confidence score, and reasoning.

---

### Edit an outreach record

```bash
outreach-track edit <id> --to corrected@email.com
outreach-track edit <id> --status archived
outreach-track edit <id> --name "Jane Doe" --company "New Corp"
```

Any combination of fields can be updated. Supported options: `--to`, `--name`, `--subject`, `--company`, `--role`, `--status`, `--sent-at`.

---

### Re-classify a reply

```bash
outreach-track classify <reply_id>
```

Re-runs Claude classification on an existing reply. Useful if a reply was recorded before the classifier was set up, or if you want to re-evaluate with an updated prompt.

Reply IDs are shown in the `outreach-track show` output.

---

## Reply Classifications

| Classification | Meaning |
|---|---|
| `interested` | Recipient wants to continue the conversation or take action |
| `not_interested` | Recipient declined or is not open to further contact |
| `needs_followup` | Reply is ambiguous, asks a question, or requires a response |
| `unclassified` | Out-of-office, auto-reply, or no actionable signal |

---

## Running Tests

```bash
pytest
```

Tests cover pure business logic (no API calls). Gmail and Claude are mocked at the integration boundary.

---

## Project Structure

```
src/
├── config.py           # Pydantic settings — reads from .env
├── core/               # Pure business logic — no I/O
│   ├── outreach_service.py
│   ├── matcher.py
│   ├── reply_service.py
│   └── classifier.py
├── integrations/       # All external I/O
│   ├── gmail_client.py
│   └── claude_client.py
├── db/                 # SQLAlchemy session + repository functions
│   ├── session.py
│   ├── outreach_repo.py
│   └── reply_repo.py
├── models/             # SQLAlchemy ORM models
│   ├── outreach.py
│   └── reply.py
└── cli/
    └── main.py         # Typer CLI entry point
```

---

## Security Notes

- `client_secret.json` and `token.json` are gitignored — never commit them
- The tool uses `gmail.readonly` scope only — it cannot send emails
- All secrets live in `.env`, which is also gitignored

---

## What's Coming in v2

v2 is designed to be additive — the v1 architecture keeps all business logic in `core/` with no I/O, so these features can be layered on without rewriting the foundation.

### Real-time reply detection via Gmail Push Notifications
Instead of manually running `sync`, v2 will set up a Gmail → Google Cloud Pub/Sub → webhook pipeline. Replies will be detected and classified within seconds of arriving, with no polling required.

### Automatic `sync` scheduling
A cron-based renewal system for the Gmail watch subscription (expires every 7 days) and scheduled sync runs, so the tool stays up to date passively.

### `classify-all` command
Batch re-classification of all replies currently marked `unclassified` — useful after updating the prompt or switching Claude models.

### Send emails directly from the CLI
v2 will add an optional `gmail.send` OAuth scope, allowing `outreach-track add` to send the email to the recipient and log it in one step — no need to switch to Gmail first. This will include a draft-and-confirm flow to prevent accidental sends.
