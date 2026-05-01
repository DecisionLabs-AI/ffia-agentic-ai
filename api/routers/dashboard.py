# =============================================================================
# FFIA — api/routers/dashboard.py
# Dashboard data endpoints: summary KPIs, invoice list, top items, oil price.
# All DB functions imported directly from data/db.py — no Streamlit involved.
# =============================================================================

# Step 1: Imports
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user_id
from api.schemas import DashboardSummary, InvoiceItem, InvoiceResponse, TopItem

router = APIRouter()


# Step 2: GET /dashboard/summary — invoice item count + latest invoice + diesel price
@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(user_id: str = Depends(get_current_user_id)):
    from data.db import count_invoice_items, get_latest_invoice  # type: ignore[import]

    try:
        item_count = count_invoice_items(user_id)
    except Exception:
        item_count = 0

    try:
        latest_raw = get_latest_invoice(user_id)
    except Exception:
        latest_raw = None
    latest = None
    if latest_raw:
        latest = InvoiceResponse(
            id=latest_raw["id"],
            vendor=latest_raw.get("vendor", ""),
            invoice_no=latest_raw.get("invoice_no", ""),
            invoice_date=str(latest_raw.get("invoice_date", "")),
            total_amount=float(latest_raw.get("total_amount", 0)),
            created_at=latest_raw.get("created_at"),
        )

    return DashboardSummary(
        invoice_item_count=item_count,
        latest_invoice=latest,
        diesel_price={},
    )


# Step 3: GET /dashboard/invoices — current-month invoice list
@router.get("/invoices", response_model=list[InvoiceResponse])
def dashboard_invoices(user_id: str = Depends(get_current_user_id)):
    from data.db import fetch_invoices_current_month  # type: ignore[import]

    rows = fetch_invoices_current_month(user_id)
    return [
        InvoiceResponse(
            id=r["id"],
            vendor=r.get("vendor", ""),
            invoice_no=r.get("invoice_no", ""),
            invoice_date=str(r.get("invoice_date", "")),
            total_amount=float(r.get("total_amount", 0)),
            created_at=r.get("created_at"),
        )
        for r in rows
    ]


# Step 4: GET /dashboard/top-items — top 5 ingredients by spend this month
@router.get("/top-items", response_model=list[TopItem])
def top_items(user_id: str = Depends(get_current_user_id), limit: int = 5):
    from data.db import get_connection  # type: ignore[import]
    import psycopg2.extras

    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ii.name, SUM(ii.total) AS total_spend
                FROM invoice_items ii
                JOIN invoices i ON i.id = ii.invoice_id
                WHERE ii.user_id = %s
                  AND (ii.excluded_from_analysis IS NOT TRUE)
                  AND DATE_TRUNC('month', i.invoice_date) = DATE_TRUNC('month', CURRENT_DATE)
                GROUP BY ii.name
                ORDER BY total_spend DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
    return [TopItem(name=r["name"], total_spend=float(r["total_spend"])) for r in rows]


# Step 5: GET /dashboard/channels — delivery channel mix
@router.get("/channels")
def dashboard_channels(user_id: str = Depends(get_current_user_id)):
    from data.db import get_connection  # type: ignore[import]
    import psycopg2.extras

    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT platform, revenue_share_pct, platform_fee_pct, is_active
                FROM restaurant_channel_mix
                WHERE user_id = %s AND is_active = true
                ORDER BY revenue_share_pct DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]
