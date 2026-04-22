# Cold Outreach Tracker

## What this is

A Python tool that tracks cold outreach emails the user has sent, detects replies via Gmail push notifications, and classifies each reply (Interested / Not Interested / Needs Follow-up) using the Claude API. CLI-first for v1; architecture must stay clean so v2 can add a Chrome extension or web UI without rewriting business logic.

## Tech stack

- Python 3.11+
- SQLite via SQLAlchemy ORM; Alembic for migrations
- FastAPI for the webhook server
- Typer for the CLI
- Pydantic Settings for config (`.env`-driven)
- `google-api-python-client` for Gmail; Google Cloud Pub/Sub for push notifications
- Anthropic SDK for classification (use `claude-sonnet-4-6` or latest available)
- pytest for tests

## Architectural principles

These are non-negotiable. Violating them defeats the point of v1.

- **`core/` contains pure business logic. No I/O.** No network, no DB session access, no filesystem. Takes inputs, returns outputs. This is what makes v2 (Chrome extension, web UI) cheap.
- **`integrations/` isolates all external I/O.** Gmail, Claude API, Pub/Sub. If it talks to the network, it lives here.
- **`webhook/` and `cli/` are transport layers.** They parse input, call into `core/`, format output. No business logic.
- **`models/` defines the data contracts.** SQLAlchemy models only; no behavior beyond what the ORM needs.
- **`db/` holds session factory and context managers.** `core/` never imports from it.

When adding new code, decide which of these five buckets it belongs in before writing it. If it fits in two, the design is wrong.

## File structure

```
cold-outreach-tracker/
├── alembic/versions/              # DB migrations
├── src/
│   ├── config.py                  # Pydantic settings
│   ├── models/                    # SQLAlchemy models (base, outreach, reply)
│   ├── core/                      # Pure logic: matcher, classifier, outreach_service
│   ├── integrations/              # Gmail client, Gmail Pub/Sub, Claude client
│   ├── webhook/                   # FastAPI app + Pub/Sub push handler
│   ├── cli/                       # Typer entry point
│   └── db/                        # SQLAlchemy session management
├── tests/                         # pytest; mock Gmail and Claude at integration boundary
└── scripts/
    ├── setup_pubsub.py            # One-time GCP setup
    └── renew_gmail_watch.py       # Cron-able; Gmail watch expires every 7 days
```

## Data model

**`outreach`** — one row per sent cold email.
- `id`, `recipient_email` (indexed), `recipient_name`, `company` (nullable), `role_context` (nullable, freeform), `subject`, `body` (full text — needed for classifier context), `sent_at`, `created_at`, `status` (`awaiting_reply` | `replied` | `archived`).

**`replies`** — one row per detected reply.
- `id`, `outreach_id` (FK), `gmail_message_id` (unique, indexed — used for idempotency), `received_at`, `body`, `classification` (`interested` | `not_interested` | `needs_followup` | `unclassified`), `classification_confidence` (float 0–1), `classification_reasoning` (text), `classified_at` (nullable).

## Conventions and constraints

- **Gmail scope is `gmail.readonly` only.** Do not request send scopes. Ever.
- **`gmail_message_id` is unique.** Pub/Sub is at-least-once; rely on the unique constraint for idempotency, don't invent deduplication logic.
- **Matcher rule:** match by exact `from_email` against `outreach.recipient_email` where `status = awaiting_reply`. If multiple match, pick the most recent. If none match, drop the email silently — do not classify unmatched mail.
- **Classifier returns strict JSON** with `{classification, confidence, reasoning}`. Use Claude's structured output. Reasoning is 1 line, for debuggability.
- **Webhook validates the Pub/Sub JWT.** Unsigned or invalid requests → 401.
- **Secrets live in `.env`**, which is gitignored. OAuth refresh token goes in a gitignored credentials file.

## Non-goals for v1

Do not build these even if they seem helpful:

- AI-drafted follow-up emails
- Reminder / nudge system
- Web UI or Chrome extension
- Analytics or dashboards
- Multi-account support
- Any email-sending capability

If a task seems to drift toward one of these, stop and flag it.

## Commands

```bash
# Setup
pip install -e .
alembic upgrade head
outreach-track auth                         # one-time OAuth
python scripts/setup_pubsub.py              # one-time GCP Pub/Sub setup

# Daily use
outreach-track add --to ... --name ... --subject ... --body-file ...
outreach-track list [--status replied]
outreach-track show <id>
outreach-track sync                         # manual fallback: polls Gmail API directly, no Pub/Sub

# Dev
uvicorn src.webhook.server:app --reload     # webhook server
ngrok http 8000                             # expose for Pub/Sub push
pytest                                      # tests

# Ops
python scripts/renew_gmail_watch.py         # cron daily; watch expires every 7 days
```

## Testing approach

- `core/` modules get unit tests with no mocks needed (they're pure).
- `integrations/` modules get tests with Gmail and Claude mocked at the client boundary.
- Webhook handler gets a test that posts a fake Pub/Sub payload and asserts the full match → classify → persist chain runs.
- Don't test SQLAlchemy itself. Don't test FastAPI itself.