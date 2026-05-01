# =============================================================================
# FFIA — api/routes/invoices.py
# Sandbox invoice endpoints — user_id passed as query/body param (no Bearer auth).
# Mirrors the same data/db.py functions used by the original Streamlit upload flow.
# Root cause: the sandbox login never issues a JWT, so Depends(get_current_user_id)
# always 401. These routes solve that without changing the auth or DB schema.
# =============================================================================

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)


# Step 1: Shared models ─────────────────────────────────────────────────────

class _Item(BaseModel):
    name: str
    qty: float
    unit_price: float
    total: float


class _SaveRequest(BaseModel):
    user_id: str
    vendor: str
    invoice_no: str
    invoice_date: str
    total_amount: float
    items: list[_Item] = Field(default_factory=list)


class _ExcludeRequest(BaseModel):
    user_id: str
    excluded: bool
    reason: str | None = None


# Step 2: Adapter — same interface extract_invoice_data() expects
class _FileAdapter:
    def __init__(self, raw_bytes: bytes, filename: str):
        self._bytes = raw_bytes
        self.name = filename

    def read(self) -> bytes:
        return self._bytes


# Step 3: GET /invoices/current-month?user_id=...
# Uses get_recent_invoices (no strict calendar-month filter) so invoices from
# the previous billing cycle are still visible — matches the Streamlit
# "Recent Saved Invoices" expander behaviour which the user sees on the old UI.
@router.get("/invoices/current-month")
def current_month_invoices(user_id: str):
    uid = str(user_id or "").strip()
    if not uid:
        return []
    import logging
    logger = logging.getLogger(__name__)
    try:
        from data.db import get_recent_invoices  # type: ignore[import]

        rows = get_recent_invoices(uid, limit=50)
        logger.info("GET /invoices/current-month user_id=%s → %d row(s)", uid, len(rows))
        return [
            {
                "id": r["id"],
                "vendor": r.get("vendor", ""),
                "invoice_no": r.get("invoice_no", ""),
                "invoice_date": str(r.get("invoice_date", "")),
                "total_amount": float(r.get("total_amount", 0)),
                "created_at": str(r.get("created_at") or ""),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.exception("current_month_invoices error: %s", exc)
        return []


# Step 4: GET /invoices/{invoice_id}/items?user_id=... ─────────────────────
@router.get("/invoices/{invoice_id}/items")
def invoice_items(invoice_id: int, user_id: str):
    uid = str(user_id or "").strip()
    if not uid:
        return []
    try:
        from data.db import fetch_invoice_items  # type: ignore[import]

        rows = fetch_invoice_items(invoice_id, uid)
        logger.info(
            "GET /invoices/%s/items user_id=%s -> %d row(s)",
            invoice_id,
            uid,
            len(rows),
        )
        return [
            {
                "item_id": r.get("item_id"),
                "item_name": r.get("item_name") or r.get("name", ""),
                # Keep the existing frontend shape while also returning item_name.
                "name": r.get("item_name") or r.get("name", ""),
                "qty": float(r.get("qty", 0)),
                "unit_price": float(r.get("unit_price", 0)),
                "total": float(r.get("total", 0)),
                "excluded_from_analysis": bool(r.get("excluded_from_analysis", False)),
                "excluded_reason": r.get("excluded_reason"),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.exception(
            "GET /invoices/%s/items user_id=%s failed: %s",
            invoice_id,
            uid,
            exc,
        )
        return []


# Step 5: POST /invoices/ocr-preview — OCR extraction only, no save ─────────
@router.post("/invoices/ocr-preview")
async def ocr_invoice_preview(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    try:
        from app.utils.ocr import extract_invoice_data  # type: ignore[import]

        raw_bytes = await file.read()
        adapter = _FileAdapter(raw_bytes, file.filename or "invoice.jpg")
        data = extract_invoice_data(adapter)
        return {
            "vendor": data.get("vendor", ""),
            "invoice_no": data.get("invoice_no", ""),
            "invoice_date": data.get("invoice_date", ""),
            "total_amount": float(data.get("total_amount", 0)),
            "items": [
                {
                    "name": i.get("name", ""),
                    "qty": float(i.get("qty", 0)),
                    "unit_price": float(i.get("unit_price", 0)),
                    "total": float(i.get("total", 0)),
                }
                for i in data.get("items", [])
            ],
            "ocr_error": data.get("_ocr_error", ""),
        }
    except Exception as exc:
        return {
            "vendor": "", "invoice_no": "", "invoice_date": "",
            "total_amount": 0.0, "items": [],
            "ocr_error": str(exc),
        }


# Step 6: POST /invoices/save — persist after user confirms review ───────────
@router.post("/invoices/save")
def save_invoice_endpoint(body: _SaveRequest):
    user_id = str(body.user_id or "").strip()
    if not user_id:
        return {"ok": False, "error": "Missing user_id", "invoice_id": None,
                "invoice_no": "", "item_count": 0, "total": 0.0}
    inv_no = str(body.invoice_no or "").strip()
    if not inv_no:
        return {"ok": False, "error": "Invoice number is required.", "invoice_id": None,
                "invoice_no": "", "item_count": 0, "total": 0.0}
    try:
        from data.db import invoice_exists, save_invoice  # type: ignore[import]

        if invoice_exists(user_id, inv_no):
            return {"ok": False, "error": f"Invoice {inv_no} already exists.",
                    "invoice_id": None, "invoice_no": inv_no, "item_count": 0, "total": 0.0}
        items_raw = [i.model_dump() for i in body.items]
        invoice_id = save_invoice(
            user_id=user_id,
            vendor=body.vendor,
            invoice_no=inv_no,
            invoice_date=body.invoice_date or "2000-01-01",
            total_amount=body.total_amount,
            items=items_raw,
        )
        return {
            "ok": True,
            "invoice_id": invoice_id,
            "invoice_no": inv_no,
            "item_count": len(items_raw),
            "total": body.total_amount,
            "error": "",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "invoice_id": None,
                "invoice_no": inv_no, "item_count": 0, "total": 0.0}


# Step 7a: PATCH /invoices/items/{item_id}/exclude — soft-exclude a line item.
# Must be declared before /invoices/{invoice_id} so "items" is not parsed as an id.
@router.patch("/invoices/items/{item_id}/exclude")
def toggle_exclusion_endpoint(item_id: int, body: _ExcludeRequest):
    uid = str(body.user_id or "").strip()
    if not uid:
        return {"ok": False, "error": "Missing user_id", "item": None}
    try:
        from data.db import toggle_item_exclusion  # type: ignore[import]

        updated = toggle_item_exclusion(item_id, uid, body.excluded, body.reason)
        if not updated:
            return {"ok": False, "error": "Item not found or access denied.", "item": None}
        return {
            "ok": True,
            "error": "",
            "item": {
                "item_id": updated.get("item_id"),
                "item_name": updated.get("item_name") or updated.get("name", ""),
                "name": updated.get("item_name") or updated.get("name", ""),
                "qty": float(updated.get("qty", 0)),
                "unit_price": float(updated.get("unit_price", 0)),
                "total": float(updated.get("total", 0)),
                "excluded_from_analysis": bool(updated.get("excluded_from_analysis", False)),
                "excluded_reason": updated.get("excluded_reason"),
            },
        }
    except Exception as exc:
        logger.exception(
            "PATCH /invoices/items/%s/exclude user_id=%s failed: %s",
            item_id,
            uid,
            exc,
        )
        return {"ok": False, "error": str(exc), "item": None}


# Step 7: DELETE /invoices/{invoice_id}?user_id=... ─────────────────────────
@router.delete("/invoices/{invoice_id}")
def delete_invoice_endpoint(invoice_id: int, user_id: str):
    if not str(user_id or "").strip():
        return {"ok": False, "error": "Missing user_id"}
    try:
        from data.db import delete_invoice  # type: ignore[import]

        deleted = delete_invoice(invoice_id, user_id)
        if not deleted:
            return {"ok": False, "error": "Invoice not found."}
        return {"ok": True, "error": ""}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
