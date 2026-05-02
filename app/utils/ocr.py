# =============================================================================
# FFIA — app/utils/ocr.py
# Real OCR extraction using Gemini 2.5 Flash Vision (via Vertex AI).
# Sends the uploaded invoice image to Gemini, receives structured JSON,
# normalizes it, and returns the canonical FFIA invoice dict.
# =============================================================================

# Step 1: Imports
import os
import re
import sys
import json
import base64
import logging
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_vertexai import ChatVertexAI
from google.oauth2 import service_account
from langchain_core.messages import HumanMessage

load_dotenv()

# Step 2: Logger — writes to stderr so Streamlit shows it in the terminal
logging.basicConfig(
    level=logging.DEBUG,
    format="[OCR] %(levelname)s — %(message)s",
    stream=sys.stderr,
)
_log = logging.getLogger("ffia.ocr")

# Step 3: Lazy Gemini Vision singleton — created on first OCR call, not at import time
_llm = None

def _get_llm():
    """Return the Gemini Vision model (Vertex AI), constructing it once on first call."""
    global _llm
    if _llm is None:
        # Step 3a: Load credentials from JSON string (Streamlit Cloud) or fall back to ADC
        _creds_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
        _credentials = None
        if _creds_json:
            _creds_dict = json.loads(_creds_json)
            _credentials = service_account.Credentials.from_service_account_info(
                _creds_dict,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        # Step 3b: Build LLM — model/location from env (reuses FFIA_AGENT_MODEL; no
        # separate FFIA_OCR_MODEL is introduced yet — both agent and OCR use the same model).
        _llm = ChatVertexAI(
            model=os.getenv("FFIA_AGENT_MODEL", "gemini-2.5-flash"),
            project=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("VERTEX_LOCATION", "asia-southeast1"),
            credentials=_credentials,
            temperature=0.0,        # Deterministic extraction
            max_output_tokens=8192, # Long receipts (19+ items with Thai names) need headroom
        )
    return _llm

# Step 4: Extraction prompt — proven structure that produces correct JSON for Thai receipts.
# Uses line_items/item_name schema (matched by _normalize via dual-key fallback).
_EXTRACTION_PROMPT = """
Extract structured invoice data from this receipt image.

STRICT RULES:
- Output ONLY valid JSON (no markdown, no explanation, no code fences)
- JSON must always be complete and valid — never truncate
- If unsure about any field, use null (never break the JSON structure)
- All number values must be plain numbers (e.g. 29.94 not "29.94" or "฿29.94")
- Strip all currency symbols and thousand-separator commas from numbers
- For dates: convert any format (DD/MM/YYYY, MM-DD-YYYY, etc.) to YYYY-MM-DD

Extract these fields:
- vendor
- invoice_no
- invoice_date
- total_amount
- line_items (max 20 items)

For each line item:
- item_name  (Thai or English product name)
- qty        (default = 1 if unclear)
- unit_price (if missing, estimate from total ÷ qty)
- total

IGNORE:
- product codes (numbers in brackets like [8851639001348])
- VAT breakdown lines
- QR codes
- footer text
- membership / loyalty point info

If OCR is noisy:
- prioritize readable Thai and English item names
- skip rows where the name is fully corrupted or unreadable

If a field is not visible, use these defaults:
  vendor → "", invoice_no → "", invoice_date → "",
  total_amount → 0, line_items → []

Return ONLY this JSON structure:
{
  "vendor": "...",
  "invoice_no": "...",
  "invoice_date": "...",
  "total_amount": 0,
  "line_items": [
    {
      "item_name": "...",
      "qty": 1,
      "unit_price": 0,
      "total": 0
    }
  ]
}
"""


def _safe_float(val, default: float = 0.0) -> float:
    """Convert val to float — strips currency symbols, commas, whitespace."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = re.sub(r"[฿$,\s]", "", val)
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def _safe_str(val, default: str = "") -> str:
    """Return stripped string or default."""
    if val is None:
        return default
    return str(val).strip() or default


def _safe_date(val) -> str:
    """
    Normalize date to ISO string (YYYY-MM-DD).
    Accepts: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, MM/DD/YYYY.
    Returns an empty string if missing or unparseable.
    """
    if not val:
        return ""
    s = str(val).strip()
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    # MM/DD/YYYY fallback
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if m:
        mo, d, y = m.groups()
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    _log.warning("Could not parse date '%s', leaving blank", s)
    return ""


def _normalize(raw: dict) -> dict:
    """
    Normalize raw OCR dict → validated FFIA invoice schema.
    Ensures all types are correct and no string artifacts remain.
    """
    # Step N1: Normalize header fields
    normalized = {
        "vendor":       _safe_str(raw.get("vendor"),       ""),
        "invoice_no":   _safe_str(raw.get("invoice_no"),   ""),
        "invoice_date": _safe_date(raw.get("invoice_date")),
        "total_amount": _safe_float(raw.get("total_amount"), 0.0),
        "items":        [],
    }

    # Step N2: Normalize each line item.
    # Try line_items first (new prompt schema), fall back to items (legacy schema).
    # Try item_name first (new prompt), fall back to name (legacy).
    raw_items = raw.get("line_items") or raw.get("items") or []
    for item in raw_items:
        normalized["items"].append({
            "name":       _safe_str(item.get("item_name") or item.get("name"), ""),
            "qty":        _safe_float(item.get("qty"),        1.0),
            "unit_price": _safe_float(item.get("unit_price"), 0.0),
            "total":      _safe_float(item.get("total"),       0.0),
        })

    return normalized


def _empty_invoice_data(
    raw_response: str = "",
    cleaned_response: str = "",
    error: str = "",
) -> dict:
    """Return a safe fallback payload the UI can still render and edit."""
    return {
        "vendor": "",
        "invoice_no": "",
        "invoice_date": "",
        "total_amount": 0.0,
        "items": [],
        "_ocr_raw_response": raw_response,
        "_ocr_cleaned_response": cleaned_response,
        "_ocr_error": error,
    }


def _coerce_response_text(content: object) -> str:
    """Flatten Gemini response content into a plain text string."""
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
    return str(content or "").strip()


def _strip_json_wrappers(text: str) -> str:
    """Remove common model wrappers like ```json fences or a leading json tag."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    cleaned = re.sub(r"^json\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def extract_invoice_data(uploaded_file: object) -> dict:
    """
    Extract structured data from an invoice image using Gemini Vision.

    Args:
        uploaded_file: Streamlit UploadedFile object (.name, .read() available)

    Returns:
        dict with keys: vendor, invoice_date (ISO str), invoice_no,
                        total_amount (float), items (list of dicts)
    """
    # Step 5a: Read image bytes and encode to base64
    raw_bytes = uploaded_file.read()
    b64_image = base64.standard_b64encode(raw_bytes).decode("utf-8")

    # Step 5b: Detect MIME type from file extension
    ext = Path(uploaded_file.name).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    mime_type = mime_map.get(ext, "image/jpeg")

    llm = _get_llm()
    _log.debug("Model config — model: %s, max_output_tokens: %s",
               getattr(llm, "model", "unknown"),
               getattr(llm, "max_output_tokens", "unknown"))
    _log.debug("Sending image to Gemini Vision — file: %s, size: %d bytes, mime: %s",
               uploaded_file.name, len(raw_bytes), mime_type)

    # Step 5c: Build multimodal message (image + extraction prompt)
    message = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
        },
        {
            "type": "text",
            "text": _EXTRACTION_PROMPT,
        },
    ])

    # Step 5d: Call Gemini Vision
    try:
        response = llm.invoke([message])
        raw_text = _coerce_response_text(response.content)
    except Exception as e:
        _log.error("Gemini Vision call failed: %s", e)
        return _empty_invoice_data(error=f"Gemini Vision call failed: {e}")

    # Step 5e: Log raw OCR text for debugging
    _log.debug("=== RAW OCR RESPONSE ===\n%s\n========================", raw_text)

    # Step 5f: Strip markdown fences if Gemini wrapped the JSON
    cleaned = _strip_json_wrappers(raw_text)
    _log.debug("=== CLEANED OCR RESPONSE ===\n%s\n===========================", cleaned)

    # Step 5g: Parse JSON
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        _log.error("JSON parse failed: %s\nRaw text was:\n%s", e, cleaned)
        return _empty_invoice_data(
            raw_response=raw_text,
            cleaned_response=cleaned,
            error=f"OCR response was not valid JSON: {e}",
        )

    if not isinstance(parsed, dict):
        _log.error("JSON parse produced non-object payload: %r", parsed)
        return _empty_invoice_data(
            raw_response=raw_text,
            cleaned_response=cleaned,
            error="OCR response JSON root was not an object.",
        )

    # Step 5h: Log parsed JSON before normalization
    _log.debug("=== PARSED JSON ===\n%s\n===================",
               json.dumps(parsed, ensure_ascii=False, indent=2))

    # Step 5i: Normalize — enforce types, strip artifacts, fix dates
    result = _normalize(parsed)
    result["_ocr_raw_response"] = raw_text
    result["_ocr_cleaned_response"] = cleaned
    result["_ocr_error"] = ""

    # Step 5j: Log final normalized output (what the UI will render)
    _log.debug("=== NORMALIZED OUTPUT ===\n%s\n=========================",
               json.dumps(result, ensure_ascii=False, indent=2, default=str))

    return result
