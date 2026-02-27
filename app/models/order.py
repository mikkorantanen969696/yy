"""
Order model representing cleaning jobs.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Order(Base):
    """Order entity with basic fields and status."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String(64))
    address: Mapped[str] = mapped_column(String(256))
    date: Mapped[str] = mapped_column(String(32))
    time: Mapped[str] = mapped_column(String(32))
    type: Mapped[str] = mapped_column(String(64))
    equipment: Mapped[str] = mapped_column(String(64))
    conditions: Mapped[str] = mapped_column(String(128))
    comment: Mapped[str] = mapped_column(String(512))
    client_contact: Mapped[str] = mapped_column(String(128))
    manager_contact: Mapped[str] = mapped_column(String(128), default="")

    # Telegram IDs are used across handlers/services, so FK must match users.telegram_id.
    manager_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    master_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))

    status: Mapped[str] = mapped_column(String(32), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
