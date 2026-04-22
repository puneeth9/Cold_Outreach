from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.classifier import ClassificationResult
from src.core.reply_service import ReplyData
from src.models import Outreach, OutreachStatus, Reply


def save_reply(session: Session, data: ReplyData) -> Reply:
    record = Reply(
        gmail_message_id=data.gmail_message_id,
        outreach_id=data.outreach_id,
        received_at=data.received_at,
        body=data.body,
        classification=data.classification,
        classification_confidence=data.classification_confidence,
        classification_reasoning=data.classification_reasoning,
        classified_at=data.classified_at,
    )
    session.add(record)
    session.flush()
    return record


def mark_outreach_replied(session: Session, outreach_id: int) -> None:
    session.query(Outreach).filter(Outreach.id == outreach_id).update(
        {"status": OutreachStatus.replied}
    )


def get_outreach_by_id(session: Session, outreach_id: int) -> Outreach | None:
    return session.query(Outreach).filter(Outreach.id == outreach_id).first()


def get_awaiting_outreaches(session: Session) -> list[Outreach]:
    return (
        session.query(Outreach)
        .filter(Outreach.status == OutreachStatus.awaiting_reply)
        .order_by(Outreach.sent_at.asc())
        .all()
    )


def update_reply_classification(
    session: Session, reply_id: int, result: ClassificationResult
) -> None:
    session.query(Reply).filter(Reply.id == reply_id).update({
        "classification": result.classification,
        "classification_confidence": result.confidence,
        "classification_reasoning": result.reasoning,
        "classified_at": datetime.now(timezone.utc),
    })


def get_reply_by_id(session: Session, reply_id: int) -> Reply | None:
    return session.query(Reply).filter(Reply.id == reply_id).first()


def get_replies_for_outreach(session: Session, outreach_id: int) -> list[Reply]:
    return (
        session.query(Reply)
        .filter(Reply.outreach_id == outreach_id)
        .order_by(Reply.received_at.asc())
        .all()
    )
