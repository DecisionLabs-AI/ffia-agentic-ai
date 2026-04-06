# =============================================================================
# FFIA — app/utils/ocr.py
# Real OCR extraction using Gemini 2.5 Flash Vision.
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
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv()

# Step 2: Logger — writes to stderr so Streamlit shows it in the terminal
logging.basicConfig(
    level=logging.DEBUG,
    format="[OCR] %(levelname)s — %(message)s",
    stream=sys.stderr,
)
_log = logging.getLogger("ffia.ocr")

# Step 3: Gemini Vision model — same key as the agent
_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.0,        # Deterministic extraction
    max_output_tokens=1024,
)

# Step 4: Extraction prompt — tells Gemini exactly what schema to return
_EXTRACTION_PROMPT = """
You are an invoice data extraction assistant. Extract ALL data from this invoice image
and return it as a single valid JSON object with EXACTLY these keys:

{
  "vendor": "string — supplier or company name",
  "invoice_no": "string — invoice or receipt number",
  "invoice_date": "string — date in YYYY-MM-DD format",
  "total_amount": number — total amount as a float (no currency symbols),
  "items": [
    {
      "name": "string — item or product name",
      "qty": number — quantity as float,
      "unit_price": number — unit price as float,
      "total": number — line total as float
    }
  ]
}

Rules:
- Return ONLY the JSON object. No markdown fences, no explanation text.
- All number values must be plain numbers (e.g. 29.94 not "29.94" or "฿29.94").
- If a field is not visible on the invoice, use sensible defaults:
  vendor → "Unknown", invoice_no → "N/A", invoice_date → today,
  total_amount → 0.0, items → [].
- Strip all currency symbols and thousand-separator commas from numbers.
- For dates: convert any format (DD/MM/YYYY, MM-DD-YYYY, etc.) to YYYY-MM-DD.
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
    Falls back to today if unparseable.
    """
    if not val:
        return date.today().isoformat()
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
    _log.warning("Could not parse date '%s', using today", s)
    return date.today().isoformat()


def _normalize(raw: dict) -> dict:
    """
    Normalize raw OCR dict → validated FFIA invoice schema.
    Ensures all types are correct and no string artifacts remain.
    """
    # Step N1: Normalize header fields
    normalized = {
        "vendor":       _safe_str(raw.get("vendor"),       "Unknown"),
        "invoice_no":   _safe_str(raw.get("invoice_no"),   "N/A"),
        "invoice_date": _safe_date(raw.get("invoice_date")),
        "total_amount": _safe_float(raw.get("total_amount"), 0.0),
        "items":        [],
    }

    # Step N2: Normalize each line item
    for item in raw.get("items") or []:
        normalized["items"].append({
            "name":       _safe_str(item.get("name"),       "—"),
            "qty":        _safe_float(item.get("qty"),       1.0),
            "unit_price": _safe_float(item.get("unit_price"), 0.0),
            "total":      _safe_float(item.get("total"),      0.0),
        })

    return normalized


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
        response = _llm.invoke([message])
        raw_text = response.content
        if isinstance(raw_text, list):
            raw_text = " ".join(
                block.get("text", "") for block in raw_text
                if isinstance(block, dict) and block.get("type") == "text"
            )
        raw_text = raw_text.strip()
    except Exception as e:
        _log.error("Gemini Vision call failed: %s", e)
        raise

    # Step 5e: Log raw OCR text for debugging
    _log.debug("=== RAW OCR RESPONSE ===\n%s\n========================", raw_text)

    # Step 5f: Strip markdown fences if Gemini wrapped the JSON
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    # Step 5g: Parse JSON
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        _log.error("JSON parse failed: %s\nRaw text was:\n%s", e, cleaned)
        raise ValueError(f"OCR response was not valid JSON: {e}\n\nRaw response:\n{raw_text}")

    # Step 5h: Log parsed JSON before normalization
    _log.debug("=== PARSED JSON ===\n%s\n===================",
               json.dumps(parsed, ensure_ascii=False, indent=2))

    # Step 5i: Normalize — enforce types, strip artifacts, fix dates
    result = _normalize(parsed)

    # Step 5j: Log final normalized output (what the UI will render)
    _log.debug("=== NORMALIZED OUTPUT ===\n%s\n=========================",
               json.dumps(result, ensure_ascii=False, indent=2, default=str))

    return result
