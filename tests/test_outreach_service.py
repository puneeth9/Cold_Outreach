import pytest

from src.core.outreach_service import build_outreach, OutreachData
from src.db.outreach_repo import save_outreach, list_outreaches


def test_build_outreach_normalises_email():
    data = build_outreach(recipient_email="Alice@Example.COM")
    assert data.recipient_email == "alice@example.com"


def test_build_outreach_strips_optional_fields():
    data = build_outreach(
        recipient_email="bob@example.com",
        recipient_name="  Bob  ",
        company="  Acme  ",
        role="  Engineering  ",
    )
    assert data.recipient_name == "Bob"
    assert data.company == "Acme"
    assert data.role == "Engineering"


def test_build_outreach_optional_fields_default_none():
    data = build_outreach(recipient_email="a@b.com")
    assert data.recipient_name is None
    assert data.company is None
    assert data.role is None
    assert data.follow_up_after_days is None
    assert data.archived is False


@pytest.mark.parametrize("bad_email", ["", "notanemail", "@nodomain", "user@"])
def test_build_outreach_rejects_bad_email(bad_email):
    with pytest.raises(ValueError, match="Invalid recipient email"):
        build_outreach(recipient_email=bad_email)


def test_build_outreach_follow_up_after_days():
    data = build_outreach(recipient_email="a@b.com", follow_up_after_days=7)
    assert data.follow_up_after_days == 7


def test_save_and_list_round_trip(session):
    data = build_outreach(
        recipient_email="carol@example.com",
        recipient_name="Carol",
        company="Initech",
    )
    record = save_outreach(session, data)
    session.commit()

    assert record.id is not None
    results = list_outreaches(session)
    assert len(results) == 1
    assert results[0].recipient_email == "carol@example.com"
    assert results[0].archived is False
