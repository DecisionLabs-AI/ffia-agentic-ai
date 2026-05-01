"""Dashboard service — one DB connection, five queries, no agent imports."""

from __future__ import annotations

import logging
from decimal import InvalidOperation
from typing import Any

import psycopg2.extras

logger = logging.getLogger(__name__)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, InvalidOperation):
        return None


def _empty_profile() -> dict[str, str | None]:
    return {"restaurant_name": None, "restaurant_type": None, "main_platform": None}


def _fetch_oil_price() -> dict[str, Any]:
    """Call the Bangchak oil price helper directly — no agent, no LangGraph."""
    try:
        from agent.tools.oil_price_tool import get_oil_price_from_bangchak
        result = get_oil_price_from_bangchak("hi diesel s")
        if "error" in result:
            logger.warning("Oil price fetch warning: %s", result["error"])
            return {"diesel": None, "source": "Bangchak", "updated_at": None}
        return {
            "diesel": float(result["price_per_liter"]),
            "source": "Bangchak",
            "updated_at": str(result.get("updated_at") or ""),
        }
    except Exception as exc:
        logger.warning("Oil price tool unavailable: %s", exc)
        return {"diesel": None, "source": "Bangchak", "updated_at": None}


def get_dashboard_summary(user_id: str | None = None) -> dict[str, Any]:
    """Return a business snapshot for the Next.js dashboard.

    Uses a single DB connection so all five queries share one TCP round-trip,
    avoiding the 10-second API timeout caused by five sequential connections.
    """
    uid = str(user_id or "").strip()
    if not uid:
        logger.warning("get_dashboard_summary called with no user_id")
        return {
            "oil_price": _fetch_oil_price(),
            "monthly_spend": None,
            "invoice_count": None,
            "items_tracked": None,
            "profile": _empty_profile(),
            "channel_mix": [],
            "top_spend_items": [],
            "error": "Missing user_id — please log in again.",
        }

    logger.info("get_dashboard_summary user_id=%s", uid)

    try:
        from data.db import get_connection  # type: ignore[import]

        with get_connection(uid) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

                # Step 1: Restaurant profile
                cur.execute(
                    """
                    SELECT restaurant_name, business_type, store_type
                    FROM public.restaurant_profiles
                    WHERE user_id = %s AND is_active = true
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (uid,),
                )
                profile_row = dict(cur.fetchone() or {})

                # Step 2: Invoices — recent, no calendar-month restriction
                # (matches get_recent_invoices semantics used by the invoices endpoint)
                cur.execute(
                    """
                    SELECT id, total_amount
                    FROM invoices
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    (uid,),
                )
                invoice_rows = [dict(r) for r in cur.fetchall()]

                # Step 3: Channel mix
                cur.execute(
                    """
                    SELECT platform AS channel,
                           revenue_share_pct,
                           platform_fee_pct,
                           is_active
                    FROM restaurant_channel_mix
                    WHERE user_id = %s
                    ORDER BY revenue_share_pct DESC
                    """,
                    (uid,),
                )
                channel_rows = [dict(r) for r in cur.fetchall()]

                # Step 4: Invoice-items count (all time, analytical — excluded items not counted)
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM invoice_items
                    WHERE user_id = %s
                      AND (excluded_from_analysis IS NOT TRUE)
                    """,
                    (uid,),
                )
                items_count = int((cur.fetchone() or {}).get("cnt") or 0)

                # Step 5: Top spend items — analytical only, excluded rows omitted
                cur.execute(
                    """
                    SELECT ii.name AS item_name, SUM(ii.total) AS amount
                    FROM invoice_items ii
                    WHERE ii.user_id = %s
                      AND (ii.excluded_from_analysis IS NOT TRUE)
                    GROUP BY ii.name
                    ORDER BY amount DESC
                    LIMIT 5
                    """,
                    (uid,),
                )
                top_items_rows = [dict(r) for r in cur.fetchall()]

    except Exception as exc:
        logger.exception("Dashboard DB query failed for user_id=%s: %s", uid, exc)
        return {
            "oil_price": _fetch_oil_price(),
            "monthly_spend": None,
            "invoice_count": None,
            "items_tracked": None,
            "profile": _empty_profile(),
            "channel_mix": [],
            "top_spend_items": [],
            "error": "ไม่สามารถโหลดข้อมูลได้ กรุณาลองใหม่อีกครั้ง",
        }

    # Build typed response dicts
    monthly_spend = sum(float(r.get("total_amount") or 0) for r in invoice_rows)

    channels = [
        {
            "channel": str(r.get("channel") or ""),
            "revenue_share_pct": float(r.get("revenue_share_pct") or 0),
            "platform_fee_pct": float(r.get("platform_fee_pct") or 0),
            "is_active": bool(r.get("is_active")),
        }
        for r in channel_rows
    ]

    profile: dict[str, str | None] = {
        "restaurant_name": profile_row.get("restaurant_name") or None,
        "restaurant_type": profile_row.get("business_type") or profile_row.get("restaurant_type") or None,
        "store_type": profile_row.get("store_type") or None,
        "main_platform": channels[0]["channel"] if channels else None,
    }

    top_items = [
        {
            "item_name": str(r.get("item_name") or ""),
            "amount": float(r.get("amount") or 0),
        }
        for r in top_items_rows
    ]

    logger.info(
        "Dashboard OK user_id=%s invoices=%d spend=%.2f channels=%d items=%d top=%d",
        uid, len(invoice_rows), monthly_spend, len(channels), items_count, len(top_items),
    )

    return {
        "oil_price": _fetch_oil_price(),
        "monthly_spend": monthly_spend,
        "invoice_count": len(invoice_rows),
        "items_tracked": items_count,
        "profile": profile,
        "channel_mix": channels,
        "top_spend_items": top_items,
        "error": None,
    }
