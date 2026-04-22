from datetime import datetime, timezone

import pytest

from src.core.matcher import find_matching_outreach
from src.models.outreach import Outreach, OutreachStatus


def make_outreach(email: str, status: OutreachStatus, sent_at: datetime) -> Outreach:
    o = Outreach()
    o.id = 1
    o.recipient_email = email
    o.status = status
    o.sent_at = sent_at
    return o


T1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
T2 = datetime(2024, 6, 1, tzinfo=timezone.utc)


def test_no_match_returns_none():
    outreach = make_outreach("alice@example.com", OutreachStatus.awaiting_reply, T1)
    assert find_matching_outreach("other@example.com", [outreach]) is None


def test_exact_email_match():
    outreach = make_outreach("alice@example.com", OutreachStatus.awaiting_reply, T1)
    assert find_matching_outreach("alice@example.com", [outreach]) is outreach


def test_case_insensitive_match():
    outreach = make_outreach("alice@example.com", OutreachStatus.awaiting_reply, T1)
    assert find_matching_outreach("ALICE@EXAMPLE.COM", [outreach]) is outreach


def test_non_awaiting_reply_status_is_ignored():
    for status in [OutreachStatus.replied, OutreachStatus.archived]:
        outreach = make_outreach("alice@example.com", status, T1)
        assert find_matching_outreach("alice@example.com", [outreach]) is None


def test_multiple_matches_returns_most_recent():
    old = make_outreach("alice@example.com", OutreachStatus.awaiting_reply, T1)
    old.id = 1
    new = make_outreach("alice@example.com", OutreachStatus.awaiting_reply, T2)
    new.id = 2
    result = find_matching_outreach("alice@example.com", [old, new])
    assert result is new


def test_empty_list_returns_none():
    assert find_matching_outreach("alice@example.com", []) is None
