"""
Analytics and metrics helpers.
"""
from __future__ import annotations

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


async def average_response_time_minutes(session: AsyncSession) -> float:
    """Average response time in minutes based on responses table."""
    result = await session.execute(select(func.avg(Response.id)))

    # Placeholder: response_time tracking will be implemented later.
    # Return 0.0 for now to avoid misleading data.
    _ = result.scalar()
    return 0.0


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
