"""
Analytics and metrics helpers.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.response import Response
from app.utils.constants import ORDER_STATUSES


async def count_orders(session: AsyncSession) -> int:
    """Total orders count."""
    result = await session.execute(select(func.count(Order.id)))
    return int(result.scalar() or 0)


async def count_by_status(session: AsyncSession) -> dict[str, int]:
    """Count orders grouped by status."""
    result = await session.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    )
    rows = result.all()
    out = {status: int(count) for status, count in rows}

    # Ensure all known statuses exist in the output.
    for key in ORDER_STATUSES.values():
        out.setdefault(key, 0)

    return out


async def count_by_city(session: AsyncSession) -> dict[str, int]:
    """Count orders grouped by city."""
    result = await session.execute(
        select(Order.city, func.count(Order.id))
        .group_by(Order.city)
        .order_by(func.count(Order.id).desc())
    )
    return {(city or "-"): int(count) for city, count in result.all()}


async def average_response_time_minutes(session: AsyncSession) -> float:
    """Average response time in minutes based on responses table."""
    first_responses_sq = (
        select(
            Response.order_id.label("order_id"),
            func.min(Response.response_time).label("first_response_time"),
        )
        .group_by(Response.order_id)
        .subquery()
    )

    result = await session.execute(
        select(Order.created_at, first_responses_sq.c.first_response_time).join(
            first_responses_sq,
            first_responses_sq.c.order_id == Order.id,
        )
    )

    deltas: list[float] = []
    for created_at, first_response_time in result.all():
        if isinstance(created_at, datetime) and isinstance(first_response_time, datetime):
            delta = (first_response_time - created_at).total_seconds() / 60.0
            if delta >= 0:
                deltas.append(delta)

    if not deltas:
        return 0.0
    return sum(deltas) / len(deltas)


async def taken_in_work_percent(session: AsyncSession) -> float:
    """Percent of orders that were taken into work."""
    total_result = await session.execute(select(func.count(Order.id)))
    total = int(total_result.scalar() or 0)
    if total == 0:
        return 0.0

    taken_statuses = (
        ORDER_STATUSES["assigned"],
        ORDER_STATUSES["in_progress"],
        ORDER_STATUSES["completed"],
    )
    taken_result = await session.execute(
        select(func.count(Order.id)).where(Order.status.in_(taken_statuses))
    )
    taken = int(taken_result.scalar() or 0)
    return (taken * 100.0) / total


async def top_masters(session: AsyncSession, limit: int = 5) -> list[tuple[int, int]]:
    """Top masters by number of assigned orders."""
    result = await session.execute(
        select(Order.master_id, func.count(Order.id))
        .where(Order.master_id.isnot(None))
        .group_by(Order.master_id)
        .order_by(func.count(Order.id).desc())
        .limit(limit)
    )
    return [(int(mid), int(cnt)) for mid, cnt in result.all() if mid]


async def top_managers(session: AsyncSession, limit: int = 5) -> list[tuple[int, int]]:
    """Top managers by number of created orders."""
    result = await session.execute(
        select(Order.manager_id, func.count(Order.id))
        .where(Order.manager_id.isnot(None))
        .group_by(Order.manager_id)
        .order_by(func.count(Order.id).desc())
        .limit(limit)
    )
    return [(int(mid), int(cnt)) for mid, cnt in result.all() if mid]

