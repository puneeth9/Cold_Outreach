import pytest
from datetime import datetime, timezone

from src.core.outreach_service import build_outreach, OutreachData
from src.db.outreach_repo import save_outreach, list_outreach
from src.models.outreach import OutreachStatus


# --- pure core tests (no DB) ---

def test_build_outreach_sets_defaults():
    data = build_outreach(
        recipient_email="Alice@Example.COM",
        recipient_name="Alice",
        subject="Hello",
        body="Body text",
    )
    assert data.recipient_email == "alice@example.com"  # normalised to lowercase
    assert data.status == OutreachStatus.awaiting_reply
    assert data.company is None
    assert data.role_context is None
    assert isinstance(data.sent_at, datetime)


def test_build_outreach_accepts_optional_fields():
    data = build_outreach(
        recipient_email="bob@example.com",
        recipient_name="Bob",
        subject="Intro",
        body="Hi Bob",
        company="Acme",
        role_context="Engineering lead",
    )
    assert data.company == "Acme"
    assert data.role_context == "Engineering lead"


@pytest.mark.parametrize("bad_email", ["", "notanemail", "@nodomain"])
def test_build_outreach_rejects_bad_email(bad_email):
    with pytest.raises(ValueError, match="Invalid recipient email"):
        build_outreach(recipient_email=bad_email, recipient_name="X", subject="S", body="B")


def test_build_outreach_rejects_empty_fields():
    with pytest.raises(ValueError):
        build_outreach(recipient_email="a@b.com", recipient_name="", subject="S", body="B")
    with pytest.raises(ValueError):
        build_outreach(recipient_email="a@b.com", recipient_name="A", subject="", body="B")
    with pytest.raises(ValueError):
        build_outreach(recipient_email="a@b.com", recipient_name="A", subject="S", body="   ")


# --- round-trip tests (core → repo → DB) ---

def test_create_and_list_round_trip(session):
    data = build_outreach(
        recipient_email="carol@example.com",
        recipient_name="Carol",
        subject="Opportunity",
        body="Reaching out about...",
        company="Initech",
    )
    record = save_outreach(session, data)
    session.commit()

    assert record.id is not None
    results = list_outreach(session)
    assert len(results) == 1
    assert results[0].recipient_email == "carol@example.com"
    assert results[0].status == OutreachStatus.awaiting_reply


def test_list_filters_by_status(session):
    for email, status in [
        ("a@x.com", OutreachStatus.awaiting_reply),
        ("b@x.com", OutreachStatus.replied),
        ("c@x.com", OutreachStatus.archived),
    ]:
        data = build_outreach(recipient_email=email, recipient_name="N", subject="S", body="B")
        data.status = status
        save_outreach(session, data)
    session.commit()

    assert len(list_outreach(session, status_filter="replied")) == 1
    assert len(list_outreach(session, status_filter="awaiting_reply")) == 1
    assert len(list_outreach(session)) == 3


def test_list_returns_most_recent_first(session):
    t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2024, 6, 1, tzinfo=timezone.utc)

    for email, sent_at in [("old@x.com", t1), ("new@x.com", t2)]:
        data = build_outreach(recipient_email=email, recipient_name="N", subject="S", body="B", sent_at=sent_at)
        save_outreach(session, data)
    session.commit()

    results = list_outreach(session)
    assert results[0].recipient_email == "new@x.com"
