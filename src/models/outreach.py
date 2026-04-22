import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class OutreachStatus(str, enum.Enum):
    awaiting_reply = "awaiting_reply"
    replied = "replied"
    archived = "archived"


class Outreach(Base):
    __tablename__ = "outreach"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_email: Mapped[str] = mapped_column(String, nullable=False)
    recipient_name: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    role_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[OutreachStatus] = mapped_column(
        Enum(OutreachStatus, native_enum=False), nullable=False, default=OutreachStatus.awaiting_reply
    )

    replies: Mapped[list["Reply"]] = relationship("Reply", back_populates="outreach")  # noqa: F821

    __table_args__ = (Index("ix_outreach_recipient_email", "recipient_email"),)
