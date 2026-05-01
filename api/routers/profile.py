# =============================================================================
# FFIA — api/routers/profile.py
# Restaurant profile and delivery channel mix endpoints.
# =============================================================================

# Step 1: Imports
from fastapi import APIRouter, Depends

from api.deps import get_current_user_id
from api.schemas import ChannelResponse, ProfileUpsertRequest

router = APIRouter()


# Step 2: GET /profile — fetch latest restaurant profile
@router.get("/")
def get_profile(user_id: str = Depends(get_current_user_id)):
    from data.db import fetch_latest_restaurant_profile  # type: ignore[import]

    profile = fetch_latest_restaurant_profile(user_id)
    if profile is None:
        return {}
    # Step 2a: Serialize — convert non-JSON-safe types (datetime, Decimal)
    return {
        k: (str(v) if hasattr(v, "isoformat") else v)
        for k, v in profile.items()
    }


# Step 3: POST /profile — upsert restaurant profile + optional channels
@router.post("/")
def upsert_profile(
    body: ProfileUpsertRequest,
    user_id: str = Depends(get_current_user_id),
):
    from data.db import upsert_restaurant_profile, upsert_channel_mix  # type: ignore[import]

    upsert_restaurant_profile(
        user_id=user_id,
        restaurant_name=body.restaurant_name,
        business_type=body.business_type,
        food_types=body.food_types,
        store_type=body.store_type,
        seat_range=body.seat_range,
        currency=body.currency,
        target_margin_pct=body.target_margin_pct,
        warning_margin_pct=body.warning_margin_pct,
        risk_margin_pct=body.risk_margin_pct,
    )

    if body.channels:
        channels_dict = {k: v.model_dump() for k, v in body.channels.items()}
        upsert_channel_mix(user_id, channels_dict)

    return {"ok": True}


# Step 4: GET /profile/channels — delivery platform mix
@router.get("/channels", response_model=list[ChannelResponse])
def get_channels(user_id: str = Depends(get_current_user_id)):
    from data.db import get_connection  # type: ignore[import]
    import psycopg2.extras

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
    return [dict(r) for r in rows]


# Step 5: POST /profile/channels — upsert channel mix standalone
@router.post("/channels")
def upsert_channels(
    channels: dict,
    user_id: str = Depends(get_current_user_id),
):
    from data.db import upsert_channel_mix  # type: ignore[import]

    upsert_channel_mix(user_id, channels)
    return {"ok": True}
