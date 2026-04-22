import base64
import email as email_lib
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _as_utc(dt: datetime) -> datetime:
    """Ensure a datetime is UTC-aware. SQLite returns naive datetimes stored as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class GmailClient:
    def __init__(self) -> None:
        creds = Credentials.from_authorized_user_file(settings.google_credentials_file, SCOPES)
        self._service = build("gmail", "v1", credentials=creds)

    def list_message_ids_from(self, sender_email: str, after: datetime) -> list[str]:
        """Return all message IDs of emails from sender_email received after `after`."""
        utc_after = _as_utc(after)
        # Gmail search requires YYYY/MM/DD format for after: operator
        date_str = utc_after.strftime("%Y/%m/%d")
        query = f"from:{sender_email} after:{date_str}"

        message_ids = []
        page_token = None

        while True:
            kwargs = {"userId": "me", "q": query}
            if page_token:
                kwargs["pageToken"] = page_token

            result = self._service.users().messages().list(**kwargs).execute()
            messages = result.get("messages", [])
            message_ids.extend(m["id"] for m in messages)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return message_ids

    def get_message(self, message_id: str) -> dict:
        return (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    def get_from_email(self, message: dict) -> str | None:
        headers = message.get("payload", {}).get("headers", [])
        for h in headers:
            if h["name"].lower() == "from":
                raw = h["value"]
                if "<" in raw and ">" in raw:
                    return raw.split("<")[1].rstrip(">").strip().lower()
                return raw.strip().lower()
        return None

    def get_received_at(self, message: dict) -> datetime:
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
