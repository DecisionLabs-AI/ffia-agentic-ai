from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg2.extras
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class BusinessSetupProfile(BaseModel):
    restaurant_name: str = ""
    business_type: str = "restaurant"
    food_types: list[str] = Field(default_factory=list)
    store_type: str = "ghost_kitchen"
    seat_range: str = "0"
    currency: str = "THB"
    target_margin_pct: float = 30.0
    warning_margin_pct: float = 25.0
    risk_margin_pct: float = 20.0


class BusinessSetupChannel(BaseModel):
    platform: str
    revenue_share_pct: float = 0.0
    platform_fee_pct: float = 0.0
    is_active: bool = True


class BusinessSetupSaveRequest(BaseModel):
    user_id: str
    profile: BusinessSetupProfile
    channel_mix: list[BusinessSetupChannel] = Field(default_factory=list)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize_profile(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {key: _json_safe(value) for key, value in profile.items()}


def _fetch_channel_mix(user_id: str) -> list[dict[str, Any]]:
    from data.db import get_connection

    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT platform, revenue_share_pct, platform_fee_pct, is_active
                FROM restaurant_channel_mix
                WHERE user_id = %s
                ORDER BY platform
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "platform": str(row.get("platform") or ""),
            "revenue_share_pct": float(row.get("revenue_share_pct") or 0),
            "platform_fee_pct": float(row.get("platform_fee_pct") or 0),
            "is_active": bool(row.get("is_active")),
        }
        for row in rows
    ]


@router.get("/business-setup")
def get_business_setup(user_id: str):
    if not str(user_id or "").strip():
        return {"profile": None, "channel_mix": [], "error": "Missing user_id"}

    try:
        from data.db import fetch_latest_restaurant_profile

        profile = fetch_latest_restaurant_profile(user_id)
        channel_mix = _fetch_channel_mix(user_id)
        return {
            "profile": _serialize_profile(profile),
            "channel_mix": channel_mix,
            "error": None,
        }
    except Exception:
        return {
            "profile": None,
            "channel_mix": [],
            "error": "Unable to load business setup data.",
        }


@router.post("/business-setup")
def save_business_setup(body: BusinessSetupSaveRequest):
    user_id = str(body.user_id or "").strip()
    if not user_id:
        return {"ok": False, "error": "Missing user_id"}

    try:
        from data.db import upsert_channel_mix, upsert_restaurant_profile

        upsert_restaurant_profile(
            user_id=user_id,
            restaurant_name=body.profile.restaurant_name,
            business_type=body.profile.business_type,
            food_types=body.profile.food_types,
            store_type=body.profile.store_type,
            seat_range=body.profile.seat_range,
            currency=body.profile.currency,
            target_margin_pct=body.profile.target_margin_pct,
            warning_margin_pct=body.profile.warning_margin_pct,
            risk_margin_pct=body.profile.risk_margin_pct,
        )

        channels = {
            channel.platform: {
                "label": channel.platform,
                "revenue_share_pct": channel.revenue_share_pct,
                "gp_pct": channel.platform_fee_pct,
                "enabled": channel.is_active,
            }
            for channel in body.channel_mix
            if channel.platform.strip()
        }
        if channels:
            upsert_channel_mix(user_id, channels)

        return {"ok": True, "error": None}
    except Exception:
        return {"ok": False, "error": "Unable to save business setup data."}
