# =============================================================================
# FFIA — api/routers/upload.py
# Invoice upload (OCR) and CRUD endpoints.
# extract_invoice_data() expects an object with .read() and .name attributes.
# FastAPI UploadFile is adapted via _UploadFileAdapter before passing to OCR.
# =============================================================================

# Step 1: Imports
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.deps import get_current_user_id
from api.schemas import (
    InvoiceItem,
    InvoiceResponse,
    InvoiceSaveRequest,
    OCRInvoiceResponse,
    SavedInvoiceResponse,
)

router = APIRouter()


# Step 2: Adapter — bridges FastAPI UploadFile to the interface extract_invoice_data() expects
class _UploadFileAdapter:
    def __init__(self, raw_bytes: bytes, filename: str):
        self._bytes = raw_bytes
        self.name = filename

    def read(self) -> bytes:
        return self._bytes


# Step 3: POST /upload/invoice — OCR the image, persist, return structured invoice
@router.post("/invoice", response_model=OCRInvoiceResponse)
async def upload_invoice(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    from app.utils.ocr import extract_invoice_data  # type: ignore[import]
    from data.db import invoice_exists, save_invoice  # type: ignore[import]

    # Step 3a: Read file bytes and run OCR
    raw_bytes = await file.read()
    adapter = _UploadFileAdapter(raw_bytes, file.filename or "invoice.jpg")
    invoice_data = extract_invoice_data(adapter)

    ocr_error = invoice_data.get("_ocr_error", "")
    items_raw = invoice_data.get("items", [])
    items = [InvoiceItem(**i) for i in items_raw]

    # Step 3b: Persist to database (skip duplicates)
    saved_id = None
    invoice_no = invoice_data.get("invoice_no", "")
    if invoice_no and not invoice_exists(user_id, invoice_no):
        saved_id = save_invoice(
            user_id=user_id,
            vendor=invoice_data.get("vendor", ""),
            invoice_no=invoice_no,
            invoice_date=invoice_data.get("invoice_date") or "2000-01-01",
            total_amount=float(invoice_data.get("total_amount", 0)),
            items=items_raw,
        )

    return OCRInvoiceResponse(
        vendor=invoice_data.get("vendor", ""),
        invoice_no=invoice_no,
        invoice_date=invoice_data.get("invoice_date", ""),
        total_amount=float(invoice_data.get("total_amount", 0)),
        items=items,
        saved_invoice_id=saved_id,
        ocr_error=ocr_error,
    )


# Step 4: GET /upload/invoices — list recent invoices for the user
@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(
    limit: int = 10,
    user_id: str = Depends(get_current_user_id),
):
    from data.db import get_recent_invoices  # type: ignore[import]

    rows = get_recent_invoices(user_id, limit=limit)
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


# Step 5: GET /upload/invoice/{id}/items — line items for a specific invoice
@router.get("/invoice/{invoice_id}/items", response_model=list[InvoiceItem])
def invoice_items(
    invoice_id: int,
    user_id: str = Depends(get_current_user_id),
):
    from data.db import fetch_invoice_items  # type: ignore[import]

    rows = fetch_invoice_items(invoice_id, user_id)
    return [
        InvoiceItem(
            # db.py aliases `name AS item_name` — handle both key names
            item_id=r.get("item_id"),
            item_name=r.get("item_name") or r.get("name", ""),
            name=r.get("item_name") or r.get("name", ""),
            qty=float(r.get("qty", 0)),
            unit_price=float(r.get("unit_price", 0)),
            total=float(r.get("total", 0)),
            excluded_from_analysis=bool(r.get("excluded_from_analysis", False)),
            excluded_reason=r.get("excluded_reason"),
        )
        for r in rows
    ]


# Step 6: DELETE /upload/invoice/{id}
@router.delete("/invoice/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: int,
    user_id: str = Depends(get_current_user_id),
):
    from data.db import delete_invoice as _delete  # type: ignore[import]

    deleted = _delete(invoice_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Invoice not found")


# Step 7: POST /upload/invoice/ocr-preview — OCR extraction only, no database write
@router.post("/invoice/ocr-preview", response_model=OCRInvoiceResponse)
async def ocr_invoice_preview(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    from app.utils.ocr import extract_invoice_data  # type: ignore[import]

    raw_bytes = await file.read()
    adapter = _UploadFileAdapter(raw_bytes, file.filename or "invoice.jpg")
    invoice_data = extract_invoice_data(adapter)
    items = [InvoiceItem(**i) for i in invoice_data.get("items", [])]
    return OCRInvoiceResponse(
        vendor=invoice_data.get("vendor", ""),
        invoice_no=invoice_data.get("invoice_no", ""),
        invoice_date=invoice_data.get("invoice_date", ""),
        total_amount=float(invoice_data.get("total_amount", 0)),
        items=items,
        saved_invoice_id=None,
        ocr_error=invoice_data.get("_ocr_error", ""),
    )


# Step 8: POST /upload/invoice/save — persist the user-reviewed invoice data
@router.post("/invoice/save", response_model=SavedInvoiceResponse)
def save_reviewed_invoice(
    payload: InvoiceSaveRequest,
    user_id: str = Depends(get_current_user_id),
):
    from data.db import invoice_exists, save_invoice  # type: ignore[import]

    inv_no = (payload.invoice_no or "").strip()
    if not inv_no:
        return SavedInvoiceResponse(ok=False, error="Invoice number is required.")
    if invoice_exists(user_id, inv_no):
        return SavedInvoiceResponse(
            ok=False,
            error=f"Invoice {inv_no} already exists.",
            invoice_no=inv_no,
        )
    items_raw = [i.model_dump() for i in payload.items]
    invoice_id = save_invoice(
        user_id=user_id,
        vendor=payload.vendor,
        invoice_no=inv_no,
        invoice_date=payload.invoice_date or "2000-01-01",
        total_amount=payload.total_amount,
        items=items_raw,
    )
    return SavedInvoiceResponse(
        ok=True,
        invoice_id=invoice_id,
        invoice_no=inv_no,
        item_count=len(items_raw),
        total=payload.total_amount,
    )


# Step 9: GET /upload/invoices/current-month — invoices for the current calendar month
@router.get("/invoices/current-month", response_model=list[InvoiceResponse])
def current_month_invoices(
    user_id: str = Depends(get_current_user_id),
):
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
