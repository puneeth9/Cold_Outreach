# Cold Outreach Tracker

A local CLI tool that tracks cold outreach emails you've sent, detects replies via Gmail, and automatically classifies each reply as **Interested**, **Not Interested**, **Needs Follow-up**, or **Unclassified** using the Claude AI API.

---

## How it works

1. You send a cold email yourself (via Gmail or any email client)
2. You log it with `outreach-track add` — this records the outreach and its first outbound message
3. Run `outreach-track sync` periodically — it resolves Gmail thread IDs, fetches all messages in each thread, classifies inbound replies with Claude, and stores the full conversation
4. Use `outreach-track list` and `outreach-track show` to review your pipeline

The tool tracks full email threads, not just individual replies. Every message in a thread (your outbounds and their inbounds) is stored and shown together.

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
FOLLOW_UP_AFTER_DAYS_DEFAULT=5

GOOGLE_CLIENT_SECRET_FILE=./client_secret.json
GOOGLE_CREDENTIALS_FILE=./token.json

ANTHROPIC_API_KEY=sk-ant-...
```

`FOLLOW_UP_AFTER_DAYS_DEFAULT` controls how many days after your last outbound message the status changes from `awaiting_reply` to `follow_up_needed`. Default is 5. Can be overridden per outreach with `--follow-up-after-days`.

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
  --subject "Software Engineer role"
```

You'll be prompted to paste the email body interactively — type your text and enter `EOF` on a new line to finish. To read the body from a file instead:

```bash
outreach-track add \
  --to recruiter@company.com \
  --name "Jane Smith" \
  --subject "Software Engineer role" \
  --body-file ./email.txt
```

Optional flags:
- `--sent-at "2026-04-21T10:30:00"` — defaults to the current time if omitted
- `--follow-up-after-days 7` — overrides `FOLLOW_UP_AFTER_DAYS_DEFAULT` for this outreach only
- `--role "Engineering Lead"` — context for the classifier

The `add` command logs the outreach and records your initial email as the first outbound message in the thread. It does **not** send the email — you send from Gmail yourself.

---

### Check for replies

```bash
outreach-track sync
```

`sync` runs in two passes:

1. **Resolve unresolved outreaches** — for any outreach without a Gmail thread ID, searches your sent mail for a message matching the recipient email and subject line. Stores the thread ID on success.

2. **Sync active threads** — for each outreach with a thread ID, fetches all messages in the thread, determines which are new (not yet stored locally), classifies each inbound message with Claude, and stores the full conversation.

Run this whenever you want to check for new replies. Duplicate messages are skipped automatically via Gmail message ID deduplication.

---

### List all outreaches

```bash
outreach-track list
```

Displays a table with ID, recipient, company, status, and last activity date. Status is computed live from the thread — it is never stored in the database.

---

### View a full thread

```bash
outreach-track show <id>
```

Shows the full outreach detail and every message in the thread in chronological order:

```
→ [outbound]  Subject: Software Engineer role
  Hi Jane, I wanted to reach out...

← [inbound]   Subject: Re: Software Engineer role
  Classification: interested (0.92) — Recipient expressed clear interest and asked to schedule a call
  Thanks for reaching out! I'd love to chat...
```

---

### Edit an outreach record

```bash
outreach-track edit <id> --follow-up-after-days 7
outreach-track edit <id> --archived
```

Supported options: `--to`, `--name`, `--company`, `--role`, `--follow-up-after-days`, `--archived`.

---

### Re-classify a message

```bash
outreach-track classify <message_id>
```

Re-runs Claude classification on an existing inbound message. Message IDs are shown in the `outreach-track show` output. Only inbound messages can be classified — running this on an outbound message is an error.

---

### List all commands

```bash
outreach-track help
```

---

## Thread Status

Status is derived from the thread state at query time — it is never stored in the database.

| Status | Meaning |
|---|---|
| `draft` | Outreach logged but no messages recorded yet |
| `awaiting_reply` | Last message is outbound; follow-up threshold not yet reached |
| `follow_up_needed` | Last message is outbound; follow-up threshold has passed |
| `interested` | Last inbound message classified as interested |
| `not_interested` | Last inbound message classified as not interested |
| `needs_followup` | Last inbound reply is ambiguous or asks a question |
| `unclassified` | Last inbound message has not been classified (out-of-office, auto-reply, etc.) |
| `archived` | Outreach has been manually archived |

---

## Data Model

**`outreach`** — one row per cold outreach contact.

| Column | Type | Notes |
|---|---|---|
| `id` | int | Primary key |
| `recipient_email` | str | Normalised to lowercase |
| `recipient_name` | str? | Optional display name |
| `company` | str? | Optional company context |
| `role` | str? | Optional role context |
| `gmail_thread_id` | str? | Resolved on first `sync`; null until then |
| `follow_up_after_days` | int? | Per-outreach override; falls back to global default |
| `archived` | bool | Set by `edit --archived` |
| `created_at` | datetime | |

**`messages`** — one row per message in the thread.

| Column | Type | Notes |
|---|---|---|
| `id` | int | Primary key |
| `outreach_id` | int | Foreign key to `outreach` |
| `direction` | enum | `outbound` or `inbound` |
| `gmail_message_id` | str? | Unique; used for deduplication |
| `subject` | str | |
| `body` | str | Full decoded text |
| `sent_at` | datetime | From Gmail `internalDate` |
| `classification` | enum? | `interested`, `not_interested`, `needs_followup`, `unclassified` |
| `classification_confidence` | float? | 0.0–1.0 |
| `classification_reasoning` | str? | One sentence from Claude |
| `created_at` | datetime | |

---

## Running Tests

```bash
pytest
```

Tests cover all pure business logic. Gmail and Claude are mocked at the integration boundary.

---

## Project Structure

```
src/
├── config.py               # Pydantic settings — reads from .env
├── core/                   # Pure business logic — no I/O
│   ├── outreach_service.py
│   ├── message_service.py
│   ├── thread_diff.py
│   ├── status.py
│   └── classifier.py
├── integrations/           # All external I/O
│   ├── gmail_client.py
│   └── claude_client.py
├── db/                     # SQLAlchemy session + repository functions
│   ├── session.py
│   ├── outreach_repo.py
│   └── message_repo.py
├── models/                 # SQLAlchemy ORM models
│   ├── outreach.py
│   └── message.py
└── cli/
    └── main.py             # Typer CLI entry point
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
