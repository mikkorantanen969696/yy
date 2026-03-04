"""
CSV export helpers.
"""
from __future__ import annotations

import csv
import io
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_photo import OrderPhoto
from app.models.user import User
from app.services.users import username_with_at


async def _load_photos(session: AsyncSession) -> dict[int, dict[str, list[str]]]:
    """Load photos grouped by order and type."""
    result = await session.execute(select(OrderPhoto))
    photos = result.scalars().all()

    grouped: dict[int, dict[str, list[str]]] = {}
    for photo in photos:
        order_group = grouped.setdefault(photo.order_id, {"before": [], "after": []})
        if photo.type == "after":
            order_group["after"].append(photo.file_id)
        else:
            order_group["before"].append(photo.file_id)

    return grouped


async def _load_usernames(session: AsyncSession) -> dict[int, str]:
    """Load usernames by telegram id."""
    result = await session.execute(select(User.telegram_id, User.username))
    return {int(tid): username_with_at(username) for tid, username in result.all()}


def _to_csv(rows: Iterable[list[str]], header: list[str]) -> bytes:
    """Build CSV bytes in UTF-8."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


async def export_basic(session: AsyncSession) -> bytes:
    """Export basic CSV with key fields."""
    result = await session.execute(select(Order))
    orders = result.scalars().all()

    usernames = await _load_usernames(session)

    header = [
        "id",
        "city",
        "date",
        "time",
        "status",
        "manager_username",
        "master_username",
    ]

    rows = []
    for order in orders:
        rows.append(
            [
                str(order.id),
                order.city,
                order.date,
                order.time,
                order.status,
                usernames.get(int(order.manager_id), "-") if order.manager_id else "-",
                usernames.get(int(order.master_id), "-") if order.master_id else "-",
            ]
        )

    return _to_csv(rows, header)


async def export_basic_for_manager(session: AsyncSession, manager_id: int) -> bytes:
    """Export basic CSV only for manager-owned orders."""
    result = await session.execute(select(Order).where(Order.manager_id == manager_id))
    orders = result.scalars().all()

    usernames = await _load_usernames(session)

    header = [
        "id",
        "city",
        "date",
        "time",
        "status",
        "manager_username",
        "master_username",
    ]

    rows = []
    for order in orders:
        rows.append(
            [
                str(order.id),
                order.city,
                order.date,
                order.time,
                order.status,
                usernames.get(int(order.manager_id), "-") if order.manager_id else "-",
                usernames.get(int(order.master_id), "-") if order.master_id else "-",
            ]
        )

    return _to_csv(rows, header)


async def export_full(session: AsyncSession) -> bytes:
    """Export full CSV with all fields and photo ids."""
    result = await session.execute(select(Order))
    orders = result.scalars().all()
    photos = await _load_photos(session)
    usernames = await _load_usernames(session)

    header = [
        "id",
        "city",
        "address",
        "date",
        "time",
        "type",
        "equipment",
        "conditions",
        "comment",
        "client_contact",
        "manager_contact",
        "manager_username",
        "master_username",
        "status",
        "created_at",
        "photos_before",
        "photos_after",
    ]

    rows = []
    for order in orders:
        order_photos = photos.get(order.id, {"before": [], "after": []})
        rows.append(
            [
                str(order.id),
                order.city,
                order.address,
                order.date,
                order.time,
                order.type,
                order.equipment,
                order.conditions,
                order.comment,
                order.client_contact,
                order.manager_contact,
                usernames.get(int(order.manager_id), "-") if order.manager_id else "-",
                usernames.get(int(order.master_id), "-") if order.master_id else "-",
                order.status,
                order.created_at.isoformat() if order.created_at else "",
                ",".join(order_photos["before"]),
                ",".join(order_photos["after"]),
            ]
        )

    return _to_csv(rows, header)


async def export_full_for_manager(session: AsyncSession, manager_id: int) -> bytes:
    """Export full CSV only for manager-owned orders."""
    result = await session.execute(select(Order).where(Order.manager_id == manager_id))
    orders = result.scalars().all()
    photos = await _load_photos(session)
    usernames = await _load_usernames(session)

    header = [
        "id",
        "city",
        "address",
        "date",
        "time",
        "type",
        "equipment",
        "conditions",
        "comment",
        "client_contact",
        "manager_contact",
        "manager_username",
        "master_username",
        "status",
        "created_at",
        "photos_before",
        "photos_after",
    ]

    rows = []
    for order in orders:
        order_photos = photos.get(order.id, {"before": [], "after": []})
        rows.append(
            [
                str(order.id),
                order.city,
                order.address,
                order.date,
                order.time,
                order.type,
                order.equipment,
                order.conditions,
                order.comment,
                order.client_contact,
                order.manager_contact,
                usernames.get(int(order.manager_id), "-") if order.manager_id else "-",
                usernames.get(int(order.master_id), "-") if order.master_id else "-",
                order.status,
                order.created_at.isoformat() if order.created_at else "",
                ",".join(order_photos["before"]),
                ",".join(order_photos["after"]),
            ]
        )

    return _to_csv(rows, header)
