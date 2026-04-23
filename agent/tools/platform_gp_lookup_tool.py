# =============================================================================
# FFIA — Platform GP Lookup Helper Tool
# Resolves platform gp_pct from user channel mix first, then platform_fee fallback.
# =============================================================================

import json
import os

import psycopg2
from dotenv import load_dotenv
from langchain_core.tools import tool

from agent.tools.postgres_tool import get_postgres_tool_user_id

load_dotenv()


def _get_database_url() -> str | None:
    """Read DATABASE_URL at runtime so env updates are picked up safely."""
    return os.getenv("DATABASE_URL")


def _normalize_platform_name(platform_name: str | None) -> str | None:
    """Normalize optional platform input to a trimmed string or None."""
    normalized = str(platform_name or "").strip()
    return normalized or None


def _lookup_user_channel_gp(
    conn,
    user_id: str,
    platform_name: str | None = None,
) -> tuple[str, float, float | None] | None:
    """
    Return (platform, platform_fee_pct, revenue_share_pct) from restaurant_channel_mix.
    Uses exact user scope and active channels only.
    """
    sql = """
        SELECT platform, platform_fee_pct, revenue_share_pct
        FROM restaurant_channel_mix
        WHERE user_id = %s
          AND is_active = true
    """
    params: list[object] = [user_id]
    if platform_name:
        sql += " AND LOWER(platform) ILIKE LOWER(%s)"
        params.append(f"%{platform_name}%")
    sql += " ORDER BY revenue_share_pct DESC LIMIT 1"

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
    if not row:
        return None
    return (str(row[0]), float(row[1]), float(row[2]) if row[2] is not None else None)


def _lookup_global_platform_fee(
    conn,
    platform_name: str,
) -> tuple[str, float] | None:
    """Return (platform, fee_percent) from platform_fee by exact case-insensitive match."""
    sql = """
        SELECT platform, fee_percent
        FROM platform_fee
        WHERE LOWER(platform) = LOWER(%s)
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (platform_name,))
        row = cur.fetchone()
    if not row:
        return None
    return (str(row[0]), float(row[1]))


def resolve_platform_gp_pct(platform_name: str | None = None) -> dict:
    """
    Resolve gp_pct deterministically using FFIA lookup order.

    Order:
    1) restaurant_channel_mix (tenant-scoped, primary)
    2) platform_fee (global fallback; only when platform_name is known)
    3) unresolved -> caller must ask user for gp_pct
    """
    current_user_id = get_postgres_tool_user_id()
    if not current_user_id:
        return {
            "status": "error",
            "needs_user_input": False,
            "message": "No authenticated user context is bound.",
        }

    database_url = _get_database_url()
    if not database_url:
        return {
            "status": "error",
            "needs_user_input": False,
            "message": "DATABASE_URL is not set.",
        }

    normalized_platform = _normalize_platform_name(platform_name)

    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_user_id', %s, false)",
                    (current_user_id,),
                )

            channel_row = _lookup_user_channel_gp(
                conn=conn,
                user_id=current_user_id,
                platform_name=normalized_platform,
            )
            if channel_row and channel_row[1] is not None:
                platform, platform_fee_pct, revenue_share_pct = channel_row
                return {
                    "status": "resolved",
                    "needs_user_input": False,
                    "source": "restaurant_channel_mix",
                    "platform": platform,
                    "revenue_share_pct": revenue_share_pct,
                    "gp_pct": round(platform_fee_pct / 100.0, 6),
                }

            if normalized_platform:
                fee_row = _lookup_global_platform_fee(conn, normalized_platform)
                if fee_row and fee_row[1] is not None:
                    platform, fee_percent = fee_row
                    return {
                        "status": "resolved",
                        "needs_user_input": False,
                        "source": "platform_fee",
                        "platform": platform,
                        "gp_pct": round(fee_percent / 100.0, 6),
                    }

    except Exception as exc:
        return {
            "status": "error",
            "needs_user_input": False,
            "message": f"PostgreSQL error: {exc}",
        }

    return {
        "status": "missing",
        "needs_user_input": True,
        "missing_input": "gp_pct",
        "message": "No GP value found in restaurant_channel_mix or platform_fee.",
    }


@tool
def platform_gp_lookup_tool(platform_name: str = "") -> str:
    """
    Resolve platform gp_pct using deterministic lookup rules.

    Primary source: restaurant_channel_mix (current user, is_active=true, highest revenue share).
    Fallback source: platform_fee (exact platform match).
    Returns JSON with status, source, platform, and gp_pct.
    """
    result = resolve_platform_gp_pct(platform_name or None)
    return json.dumps(result, ensure_ascii=False)

