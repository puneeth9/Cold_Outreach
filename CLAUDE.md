# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python CLI tool that tracks cold outreach emails the user has sent, detects replies via Gmail polling, and classifies each reply using the Claude API. CLI-first for v1; architecture is clean so v2 can add a webhook server or web UI without rewriting business logic.

## Tech stack

- Python 3.11+
- SQLite via SQLAlchemy ORM (native_enum=False for SQLite compatibility); Alembic for migrations
- Typer for the CLI; Rich for output formatting
- Pydantic Settings for config (`.env`-driven)
- `google-api-python-client` for Gmail (thread-based API)
- Anthropic SDK for classification — forced tool use (`tool_choice={"type": "tool", "name": "..."}`)
- pytest for tests

## Architectural principles

These are non-negotiable:

- **`core/` contains pure business logic. No I/O.** No network, no DB session access, no filesystem. Takes plain Python inputs, returns plain Python outputs. `core/` may import from `src.models` for enum/type references only — never for ORM queries.
- **`integrations/` isolates all external I/O.** Gmail API, Claude API. If it makes a network call, it lives here.
- **`cli/` is a transport layer.** Parses input, calls into `core/` and `db/`, formats output. No business logic.
- **`models/` defines ORM data contracts only.** No behavior beyond what SQLAlchemy needs.
- **`db/` holds session factory and repository functions.** `core/` never imports from `db/`.
- **Status is derived, never stored.** `compute_status()` in `core/status.py` is a pure function — call it in-memory at query time. There is no `status` column in the DB.

## Data model

**`outreach`** — one row per cold outreach contact.
- `id`, `recipient_email`, `recipient_name` (nullable), `company` (nullable), `role` (nullable)
- `gmail_thread_id` (nullable, unique) — resolved on first `sync`, null until then
- `follow_up_after_days` (nullable int) — per-outreach override; falls back to `FOLLOW_UP_AFTER_DAYS_DEFAULT` from config
- `archived` (bool, default False)
- `created_at`
- `messages` relationship → `Message` (cascade delete)

**`messages`** — one row per message in the thread (both sent and received).
- `id`, `outreach_id` (FK)
- `direction` (enum: `outbound` | `inbound`)
- `gmail_message_id` (nullable, unique) — used for deduplication
- `subject`, `body`, `sent_at`
- `classification` (nullable enum: `interested` | `not_interested` | `needs_followup` | `unclassified`)
- `classification_confidence` (float), `classification_reasoning` (text)
- `created_at`

## Key conventions

- **Gmail scope is `gmail.readonly` only.** Never request send scopes.
- **Thread-based sync:** resolve `gmail_thread_id` from sent mail search, then diff `thread.messages` against local `gmail_message_id` set to find new messages.
- **Direction detection:** if `from_email == authenticated_email` (from `users.getProfile`) → `outbound`, else `inbound`. `get_authenticated_email()` is cached on the client after the first call.
- **Classification is on inbound messages only.** The CLI `classify` command must error if the given message is outbound.
- **Classifier prompt shows the full thread** with the last inbound marked `← CLASSIFY THIS MESSAGE`. All four labels must be in the tool schema: `interested`, `not_interested`, `needs_followup`, `unclassified`.
- **`follow_up_after_days` threshold:** `outreach.follow_up_after_days or settings.follow_up_after_days_default`. Status is `follow_up_needed` when `(now - last_outbound.sent_at).days >= threshold`.

## Commands

```bash
# Setup
pip install -e .
alembic upgrade head
outreach-track auth              # one-time OAuth

# Daily use
outreach-track add --to ... --name ... --subject ...  [--body-file ...]
outreach-track list
outreach-track show <id>
outreach-track sync
outreach-track classify <message_id>
outreach-track edit <id> [--follow-up-after-days N] [--archived]
outreach-track help

# Dev
pytest                           # all tests
pytest tests/test_status.py -v   # single test file
```

## Testing approach

- `core/` modules get unit tests with no mocks needed (they're pure). Use `MagicMock` for ORM objects when testing pure functions.
- `integrations/` modules get tests with Gmail and Claude mocked at the client boundary (patch `anthropic.Anthropic`, not the method).
- `conftest.py` provides an in-memory SQLite `session` fixture — import both `src.models.outreach` and `src.models.message` to register all models with metadata.
- Don't test SQLAlchemy itself. Don't test Typer itself.
