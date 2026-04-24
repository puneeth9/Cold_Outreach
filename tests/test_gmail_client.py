"""Tests for GmailClient message-parsing helpers.

The Gmail API service is mocked at construction time so no real credentials
or network calls are needed. Only the pure parsing methods are covered here;
the live search/thread methods are exercised during manual smoke-testing.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.gmail_client import GmailClient


@pytest.fixture
def client():
    """Return a GmailClient with the Google API service fully mocked."""
    mock_service = MagicMock()
    with patch("src.integrations.gmail_client.Credentials.from_authorized_user_file"), \
         patch("src.integrations.gmail_client.build", return_value=mock_service):
        c = GmailClient.__new__(GmailClient)
        c._service = mock_service
        c._authenticated_email = None
    return c, mock_service


# --- get_from_email ---

def test_get_from_email_with_angle_brackets(client):
    c, _ = client
    msg = {"payload": {"headers": [{"name": "From", "value": "Alice <alice@example.com>"}]}}
    assert c.get_from_email(msg) == "alice@example.com"


def test_get_from_email_plain_address(client):
    c, _ = client
    msg = {"payload": {"headers": [{"name": "From", "value": "alice@example.com"}]}}
    assert c.get_from_email(msg) == "alice@example.com"


def test_get_from_email_lowercased(client):
    c, _ = client
    msg = {"payload": {"headers": [{"name": "From", "value": "Alice@Example.COM"}]}}
    assert c.get_from_email(msg) == "alice@example.com"


def test_get_from_email_missing_header_returns_none(client):
    c, _ = client
    msg = {"payload": {"headers": [{"name": "Subject", "value": "Hello"}]}}
    assert c.get_from_email(msg) is None


def test_get_from_email_empty_headers_returns_none(client):
    c, _ = client
    msg = {"payload": {"headers": []}}
    assert c.get_from_email(msg) is None


# --- get_subject ---

def test_get_subject_returns_value(client):
    c, _ = client
    msg = {"payload": {"headers": [{"name": "Subject", "value": "Hello World"}]}}
    assert c.get_subject(msg) == "Hello World"


def test_get_subject_strips_whitespace(client):
    c, _ = client
    msg = {"payload": {"headers": [{"name": "Subject", "value": "  Trimmed  "}]}}
    assert c.get_subject(msg) == "Trimmed"


def test_get_subject_case_insensitive_header_name(client):
    c, _ = client
    msg = {"payload": {"headers": [{"name": "SUBJECT", "value": "Case Test"}]}}
    assert c.get_subject(msg) == "Case Test"


def test_get_subject_missing_returns_no_subject(client):
    c, _ = client
    msg = {"payload": {"headers": []}}
    assert c.get_subject(msg) == "(no subject)"


# --- get_sent_at ---

def test_get_sent_at_returns_utc_datetime(client):
    c, _ = client
    # 1_000_000 ms = 1000 seconds past epoch
    msg = {"internalDate": "1000000"}
    result = c.get_sent_at(msg)
    assert result == datetime(1970, 1, 1, 0, 16, 40, tzinfo=timezone.utc)
    assert result.tzinfo == timezone.utc


def test_get_sent_at_zero_epoch(client):
    c, _ = client
    msg = {"internalDate": "0"}
    result = c.get_sent_at(msg)
    assert result == datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


# --- decode_body / _extract_text ---

def _b64(text: str) -> str:
    import base64
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def test_decode_body_text_plain_direct(client):
    c, _ = client
    msg = {
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": _b64("Hello plain text")},
            "parts": [],
        }
    }
    assert c.decode_body(msg) == "Hello plain text"


def test_decode_body_prefers_text_plain_part(client):
    c, _ = client
    msg = {
        "payload": {
            "mimeType": "multipart/alternative",
            "body": {},
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": _b64("Plain part")},
                    "parts": [],
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": _b64("<p>HTML part</p>")},
                    "parts": [],
                },
            ],
        }
    }
    assert c.decode_body(msg) == "Plain part"


def test_decode_body_empty_payload_returns_empty_string(client):
    c, _ = client
    msg = {"payload": {"mimeType": "multipart/mixed", "body": {}, "parts": []}}
    assert c.decode_body(msg) == ""


# --- get_thread_message_ids ---

def test_get_thread_message_ids_returns_ordered_ids(client):
    c, mock_service = client
    mock_service.users.return_value.threads.return_value.get.return_value.execute.return_value = {
        "messages": [{"id": "aaa"}, {"id": "bbb"}, {"id": "ccc"}]
    }
    assert c.get_thread_message_ids("thread_xyz") == ["aaa", "bbb", "ccc"]


def test_get_thread_message_ids_empty_thread(client):
    c, mock_service = client
    mock_service.users.return_value.threads.return_value.get.return_value.execute.return_value = {
        "messages": []
    }
    assert c.get_thread_message_ids("thread_xyz") == []


# --- search_sent_thread_id ---

def test_search_sent_thread_id_returns_thread_id(client):
    c, mock_service = client
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg1"}]
    }
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "threadId": "thread1"
    }
    result = c.search_sent_thread_id("bob@example.com", "Hello Bob")
    assert result == "thread1"


def test_search_sent_thread_id_not_found_returns_none(client):
    c, mock_service = client
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": []
    }
    result = c.search_sent_thread_id("bob@example.com", "Hello Bob")
    assert result is None


# --- get_authenticated_email ---

def test_get_authenticated_email_lowercases_and_caches(client):
    c, mock_service = client
    mock_service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": "Me@Example.COM"
    }
    first = c.get_authenticated_email()
    second = c.get_authenticated_email()

    assert first == "me@example.com"
    assert second == "me@example.com"
    # API must only be called once — second call uses cached value
    mock_service.users.return_value.getProfile.return_value.execute.assert_called_once()
