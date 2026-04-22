from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.core.status import compute_status
from src.models.message import Classification, Direction


def _make_outreach(archived=False, follow_up_after_days=None):
    o = MagicMock()
    o.archived = archived
    o.follow_up_after_days = follow_up_after_days
    return o


def _make_message(direction, classification=None, days_ago=3):
    m = MagicMock()
    m.direction = direction
    m.classification = classification
    m.sent_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return m


NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
DEFAULT_DAYS = 5


def test_archived_outreach():
    outreach = _make_outreach(archived=True)
    assert compute_status(outreach, [], DEFAULT_DAYS, now=NOW) == "archived"


def test_archived_beats_messages():
    outreach = _make_outreach(archived=True)
    msg = _make_message(Direction.inbound, Classification.interested)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "archived"


def test_no_messages_returns_draft():
    outreach = _make_outreach()
    assert compute_status(outreach, [], DEFAULT_DAYS, now=NOW) == "draft"


def test_last_inbound_interested():
    outreach = _make_outreach()
    msg = _make_message(Direction.inbound, Classification.interested)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "interested"


def test_last_inbound_not_interested():
    outreach = _make_outreach()
    msg = _make_message(Direction.inbound, Classification.not_interested)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "not_interested"


def test_last_inbound_needs_followup():
    outreach = _make_outreach()
    msg = _make_message(Direction.inbound, Classification.needs_followup)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "needs_followup"


def test_last_inbound_unclassified_enum():
    outreach = _make_outreach()
    msg = _make_message(Direction.inbound, Classification.unclassified)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "unclassified"


def test_last_inbound_no_classification_returns_unclassified():
    outreach = _make_outreach()
    msg = _make_message(Direction.inbound, classification=None)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "unclassified"


def test_last_outbound_under_threshold_awaiting_reply():
    outreach = _make_outreach()
    # sent 2 days ago, threshold 5 days → not yet due
    msg = MagicMock()
    msg.direction = Direction.outbound
    msg.sent_at = NOW - timedelta(days=2)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "awaiting_reply"


def test_last_outbound_exactly_at_threshold_follow_up_needed():
    outreach = _make_outreach()
    # sent exactly 5 days ago → crosses threshold (>= 5)
    msg = MagicMock()
    msg.direction = Direction.outbound
    msg.sent_at = NOW - timedelta(days=5)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "follow_up_needed"


def test_last_outbound_over_threshold_follow_up_needed():
    outreach = _make_outreach()
    msg = MagicMock()
    msg.direction = Direction.outbound
    msg.sent_at = NOW - timedelta(days=10)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "follow_up_needed"


def test_per_outreach_override_beats_global_default():
    # global default = 5, outreach override = 10
    outreach = _make_outreach(follow_up_after_days=10)
    msg = MagicMock()
    msg.direction = Direction.outbound
    msg.sent_at = NOW - timedelta(days=7)  # 7 days: past global (5) but not override (10)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "awaiting_reply"


def test_per_outreach_override_triggers_follow_up():
    outreach = _make_outreach(follow_up_after_days=10)
    msg = MagicMock()
    msg.direction = Direction.outbound
    msg.sent_at = NOW - timedelta(days=10)
    assert compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW) == "follow_up_needed"


def test_only_last_message_direction_matters():
    outreach = _make_outreach()
    inbound = _make_message(Direction.inbound, Classification.interested)
    # Thread ends with an outbound (user replied), recent
    outbound = MagicMock()
    outbound.direction = Direction.outbound
    outbound.sent_at = NOW - timedelta(days=1)
    assert compute_status(outreach, [inbound, outbound], DEFAULT_DAYS, now=NOW) == "awaiting_reply"


def test_naive_sent_at_handled_without_error():
    outreach = _make_outreach()
    msg = MagicMock()
    msg.direction = Direction.outbound
    msg.sent_at = (NOW - timedelta(days=1)).replace(tzinfo=None)  # naive datetime (SQLite artifact)
    result = compute_status(outreach, [msg], DEFAULT_DAYS, now=NOW)
    assert result in ("awaiting_reply", "follow_up_needed")
