import base64
import email as email_lib
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class GmailClient:
    def __init__(self) -> None:
        creds = Credentials.from_authorized_user_file(settings.google_credentials_file, SCOPES)
        self._service = build("gmail", "v1", credentials=creds)
        self._authenticated_email: str | None = None

    def get_authenticated_email(self) -> str:
        """Return the Gmail address of the authenticated user (cached after first call)."""
        if self._authenticated_email is None:
            profile = self._service.users().getProfile(userId="me").execute()
            self._authenticated_email = profile["emailAddress"].lower()
        return self._authenticated_email

    # --- Thread-based methods ---

    def search_sent_thread_id(self, to_email: str, subject: str) -> str | None:
        """Search Gmail sent mail for a thread matching to_email + exact subject.

        Returns the threadId of the most recent match, or None if not found.
        """
        query = f'to:{to_email} subject:"{subject}" in:sent'
        result = self._service.users().messages().list(userId="me", q=query).execute()
        messages = result.get("messages", [])
        if not messages:
            return None
        # Gmail returns most recent first; take the first match.
        msg = self._service.users().messages().get(
            userId="me", id=messages[0]["id"], format="minimal"
        ).execute()
        return msg.get("threadId")

    def get_thread_message_ids(self, thread_id: str) -> list[str]:
        """Return message IDs in the thread, ordered by internalDate ascending."""
        thread = self._service.users().threads().get(
            userId="me", id=thread_id, format="minimal"
        ).execute()
        messages = thread.get("messages", [])
        return [m["id"] for m in messages]

    def get_message(self, message_id: str) -> dict:
        return (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    # --- Message parsing helpers ---

    def get_from_email(self, message: dict) -> str | None:
        headers = message.get("payload", {}).get("headers", [])
        for h in headers:
            if h["name"].lower() == "from":
                raw = h["value"]
                if "<" in raw and ">" in raw:
                    return raw.split("<")[1].rstrip(">").strip().lower()
                return raw.strip().lower()
        return None

    def get_subject(self, message: dict) -> str:
        headers = message.get("payload", {}).get("headers", [])
        for h in headers:
            if h["name"].lower() == "subject":
                return h["value"].strip()
        return "(no subject)"

    def get_sent_at(self, message: dict) -> datetime:
        ts_ms = int(message.get("internalDate", 0))
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

    def decode_body(self, message: dict) -> str:
        payload = message.get("payload", {})
        return self._extract_text(payload)

    def _extract_text(self, payload: dict) -> str:
        mime_type = payload.get("mimeType", "")
        parts = payload.get("parts", [])

        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

        if mime_type == "text/html" and not parts:
            data = payload.get("body", {}).get("data", "")
            raw_html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            return email_lib.message_from_string(raw_html).get_payload() or raw_html

        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

        if parts:
            return self._extract_text(parts[0])

        return ""
