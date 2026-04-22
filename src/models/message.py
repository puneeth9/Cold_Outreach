import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Direction(str, enum.Enum):
    outbound = "outbound"
    inbound = "inbound"


# Classification labels for inbound messages.
# Note: 'needs_followup' here is a per-message classification label (Claude's assessment
# of a single reply). It is distinct from 'follow_up_needed', which is a derived thread
# status meaning the last outbound message has exceeded the follow-up threshold with no
# reply yet. Keep both — they represent different things at different levels.
class Classification(str, enum.Enum):
    interested = "interested"
    not_interested = "not_interested"
    needs_followup = "needs_followup"
    unclassified = "unclassified"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    outreach_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("outreach.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[Direction] = mapped_column(
        Enum(Direction, native_enum=False), nullable=False
    )
    # Null for the first outbound message created by `add` before Gmail sync resolves it.
    # Unique constraint allows multiple NULLs (SQLite treats NULLs as distinct).
    gmail_message_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Null for outbound messages and unclassified inbound; set on first ingest for inbound.
    classification: Mapped[Classification | None] = mapped_column(
        Enum(Classification, native_enum=False), nullable=True
    )
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    outreach: Mapped["Outreach"] = relationship("Outreach", back_populates="messages")  # noqa: F821

    __table_args__ = (Index("ix_messages_gmail_message_id", "gmail_message_id"),)
