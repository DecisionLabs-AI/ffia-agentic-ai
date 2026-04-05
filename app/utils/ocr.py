# =============================================================================
# FFIA — app/utils/ocr.py
# Mock OCR extraction for invoice images.
# Replace extract_invoice_data() body with real Claude Vision call in W3+.
# =============================================================================


def extract_invoice_data(uploaded_file: object) -> dict:
    """
    Extract structured data from an invoice image.

    Currently returns mock data for MVP demo.
    To wire real OCR: replace this body with a Claude Vision API call,
    passing the uploaded_file bytes as a base64-encoded image message.

    Args:
        uploaded_file: Streamlit UploadedFile object (image bytes available via .read())

    Returns:
        dict with keys: vendor, invoice_date (ISO str), invoice_no,
                        total_amount (float), items (list of dicts)
    """
    # Step 1: Mock extraction — returns realistic Bangchak fuel invoice data
    return {
        "vendor": "Bangchak",
        "invoice_date": "2026-04-05",
        "invoice_no": "INV-001",
        "total_amount": 2450.0,
        "items": [
            {"name": "Diesel Fuel", "qty": 50,  "unit_price": 44.24, "total": 2212.0},
            {"name": "Service Fee", "qty": 1,   "unit_price": 238.0, "total": 238.0},
        ],
    }
