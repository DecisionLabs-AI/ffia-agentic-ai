from collections.abc import Callable
from datetime import date

import pandas as pd
import streamlit as st

from app.components.layout import _render_page_hero, _render_section_header
from app.utils.upload_cache import build_uploaded_file_cache_key
from data.db import (
    delete_invoice,
    fetch_invoice_items,
    fetch_invoices_current_month,
    get_recent_invoices,
    invoice_exists,
    save_invoice,
)


def _safe_invoice_date(value: object) -> date:
    """Return a valid date for the form even if OCR left the field blank."""
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return date.today()


def _build_items_df(items: object) -> pd.DataFrame:
    """Keep the line-item editor usable even when OCR returns no rows."""
    return pd.DataFrame(items or [], columns=["name", "qty", "unit_price", "total"])


# Step 6: Monthly invoices section — always visible below the upload flow
def _render_monthly_invoices_section(current_user: dict) -> None:
    """Render the current-month invoice list and item detail view."""
    st.subheader("Uploaded Invoices (Current Month)")

    # Step 6a: Fetch this month's invoices for the authenticated user
    try:
        invoices = fetch_invoices_current_month(current_user["user_id"])
    except Exception as _e:
        st.error(f"Could not load invoices: {_e}")
        return

    if not invoices:
        st.info("No invoices uploaded this month.")
        return

    # Step 6b: Display invoice rows with per-row delete button
    _hdr1, _hdr2, _hdr3, _hdr4, _hdr5 = st.columns([2, 3, 2, 2, 1])
    _hdr1.markdown("**Date**")
    _hdr2.markdown("**Vendor**")
    _hdr3.markdown("**Invoice No**")
    _hdr4.markdown("**Total (THB)**")
    _hdr5.markdown("**Del**")

    for _row in invoices:
        _inv_id   = _row["id"]
        _inv_no   = _row["invoice_no"]
        _vendor   = _row["vendor"]
        _inv_date = _row["invoice_date"]
        _total    = _row["total_amount"]
        _ck       = f"confirm_del_{_inv_id}"

        _c1, _c2, _c3, _c4, _c5 = st.columns([2, 3, 2, 2, 1])
        _c1.write(str(_inv_date))
        _c2.write(_vendor)
        _c3.write(_inv_no)
        _c4.write(f"{_total:,.2f}")

        if _c5.button("Delete", key=f"del_{_inv_id}", type="secondary"):
            st.session_state[_ck] = True

        if st.session_state.get(_ck):
            st.warning(f"Delete invoice {_inv_no} from {_vendor} ({_inv_date})?")
            st.markdown(
                f"""
                <style>
                [data-testid*="confirm_{_inv_id}"] > button {{
                    background-color: #dc2626 !important;
                    border-color: #dc2626 !important;
                    color: #ffffff !important;
                }}
                [data-testid*="confirm_{_inv_id}"] > button:hover {{
                    background-color: #b91c1c !important;
                    border-color: #b91c1c !important;
                    color: #ffffff !important;
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )
            _cc1, _cc2 = st.columns(2)
            if _cc1.button("Confirm", key=f"confirm_{_inv_id}", type="primary"):
                delete_invoice(_inv_id, current_user["user_id"])
                st.session_state.pop(_ck)
                st.success("ลบแล้ว")
                st.rerun()
            if _cc2.button("Cancel", key=f"cancel_{_inv_id}", type="secondary"):
                st.session_state.pop(_ck)
                st.rerun()

    st.divider()
    # Step 6c: Invoice selectbox — label combines invoice_no, vendor, date for clarity
    _options = {
        f"{r['invoice_no']} — {r['vendor']} ({r['invoice_date']})": r["id"]
        for r in invoices
    }
    _selected_label = st.selectbox("Select an invoice to view items", list(_options.keys()))
    _selected_id = _options[_selected_label]

    # Step 6d: Fetch and display line items for the selected invoice
    try:
        _items = fetch_invoice_items(_selected_id, current_user["user_id"])
    except Exception as _e:
        st.error(f"Could not load items: {_e}")
        return

    if not _items:
        st.caption("No line items found for this invoice.")
        return

    st.markdown(f"**Line Items — {_selected_label}**")
    st.dataframe(
        pd.DataFrame(_items)[["item_name", "qty", "unit_price", "total"]],
        use_container_width=True,
        hide_index=True,
    )


# Step 7: Shared invoice upload section — reused in Upload + Business Setup pages
def _render_upload_invoice_section(
    current_user: dict,
    section_title: str,
    section_description: str,
    get_extract_invoice_data: Callable[[], Callable],
    get_run_agent: Callable[[], Callable],
) -> None:
    """Render invoice upload/review flow and current-month invoice section."""
    with st.container(border=True):
        _render_section_header(
            section_title,
            section_description,
        )

        # Step 5a: Upload
        st.subheader("Step 1: Upload Invoice Image")
        st.caption("Supported formats: JPG, JPEG, PNG")
        uploaded = st.file_uploader(
            "Choose invoice image",
            type=["png", "jpg", "jpeg"],
            label_visibility="collapsed",
        )

        if not uploaded:
            st.info("Upload an invoice image above to begin.")
        else:
            # Step 5b: Preview
            st.subheader("Step 2: Preview")
            st.image(uploaded, width=480)

            # Step 5c: Extract — run once per file, cache in session state
            st.subheader("Step 3: Review & Edit Extracted Data")
            st.caption("Please review and adjust extracted data before analysis.")

            _cache_key = build_uploaded_file_cache_key(uploaded)
            if _cache_key not in st.session_state:
                with st.spinner("Extracting data from image..."):
                    st.session_state[_cache_key] = get_extract_invoice_data()(uploaded)
            data = st.session_state[_cache_key]
            _ocr_error = data.get("_ocr_error", "")
            _raw_ocr = data.get("_ocr_raw_response", "")
            _cleaned_ocr = data.get("_ocr_cleaned_response", "")

            if _ocr_error:
                st.warning(
                    "OCR output could not be parsed cleanly. You can still review and edit the "
                    "invoice below, and the raw OCR response is shown for debugging."
                )

            with st.expander("OCR Debug Output", expanded=bool(_ocr_error)):
                if _ocr_error:
                    st.caption(_ocr_error)
                st.text_area("Raw OCR response", value=_raw_ocr, height=180, disabled=True)
                st.text_area(
                    "Cleaned response before JSON parse",
                    value=_cleaned_ocr,
                    height=180,
                    disabled=True,
                )

            # Step 5d: Header fields — two columns
            _col_a, _col_b = st.columns(2)
            with _col_a:
                vendor  = st.text_input("Vendor",     value=data["vendor"])
                inv_no  = st.text_input("Invoice No", value=data["invoice_no"])
            with _col_b:
                inv_date = st.date_input(
                    "Invoice Date",
                    value=_safe_invoice_date(data.get("invoice_date")),
                )
                total = st.number_input(
                    "Total Amount (฿)",
                    value=float(data["total_amount"]),
                    step=0.01,
                    format="%.2f",
                )

            # Step 5e: Line items — editable table
            st.markdown("**Line Items**")
            items_df = _build_items_df(data.get("items"))
            edited_df = st.data_editor(
                items_df,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "name":       st.column_config.TextColumn("Item Name"),
                    "qty":        st.column_config.NumberColumn("Qty", step=1),
                    "unit_price": st.column_config.NumberColumn("Unit Price (฿)", format="%.2f"),
                    "total":      st.column_config.NumberColumn("Total (฿)", format="%.2f"),
                },
            )

            st.divider()

            # Step 5f: Save to database button
            st.subheader("Step 4: Save Invoice")
            _col_save, _ = st.columns([1, 3])
            with _col_save:
                if st.button("Save Invoice to Database", type="primary", use_container_width=True):
                    try:
                        _invoice_no = str(inv_no).strip()
                        if invoice_exists(current_user["user_id"], _invoice_no):
                            st.warning("⚠️ This invoice already exists")
                        else:
                            _inv_id = save_invoice(
                                user_id=current_user["user_id"],
                                vendor=vendor,
                                invoice_no=_invoice_no,
                                invoice_date=inv_date,
                                total_amount=total,
                                items=edited_df.to_dict(orient="records"),
                            )
                            st.success(f"Invoice **{_invoice_no}** saved (ID: {_inv_id})")
                    except Exception as _e:
                        st.error(f"Failed to save: {_e}")

            # Step 5g: Recent saved invoices
            with st.expander("Recent Saved Invoices", expanded=False):
                try:
                    _recent = get_recent_invoices(current_user["user_id"])
                    if _recent:
                        st.dataframe(pd.DataFrame(_recent), use_container_width=True)
                    else:
                        st.caption("No invoices saved yet.")
                except Exception as _e:
                    st.error(f"Could not load invoices: {_e}")

            st.divider()

            # Step 5h: Analyze button
            st.subheader("Step 5: Analyze with FFIA")
            _has_data = len(edited_df) > 0
            if st.button("Analyze with FFIA", disabled=not _has_data):
                _prompt = (
                    "Analyze this invoice for fuel-related cost impact and provide cost optimization "
                    "recommendations for a restaurant.\n\n"
                    f"Vendor: {vendor}\n"
                    f"Invoice No: {inv_no}\n"
                    f"Date: {inv_date}\n"
                    f"Total: ฿{total:,.2f}\n\n"
                    f"Line items:\n{edited_df.to_string(index=False)}"
                )
                with st.spinner("FFIA is analyzing..."):
                    _result = get_run_agent()(_prompt, current_user_id=current_user["user_id"])

                # Step 5i: FFIA Insight
                st.subheader("FFIA Insight")
                st.markdown(_result.get("output", "No response from agent."))

                _steps = _result.get("intermediate_steps", [])
                if _steps:
                    with st.expander("Agent Reasoning Trace (click to expand)", expanded=False):
                        for _i, (_tool_name, _obs) in enumerate(_steps, 1):
                            st.markdown(f"**Step {_i} — Action:** `{_tool_name}`")
                            if _obs:
                                st.markdown(f"**Observation:** {str(_obs)[:500]}")
                            st.divider()

    # Step 5j: Monthly invoice list — always visible, below the upload flow
    st.write("")
    with st.container(border=True):
        _render_monthly_invoices_section(current_user)


# Step 7a: Data Upload page renderer — OCR → editable form → FFIA analysis
def _render_upload_page(
    current_user: dict,
    get_extract_invoice_data: Callable[[], Callable],
    get_run_agent: Callable[[], Callable],
):
    """Render the Data Upload page: upload image → preview → extract → edit → analyze."""
    _render_page_hero(
        "Data Upload — Invoice Image OCR",
        "Upload a fuel or supplier invoice image to extract cost data, "
        "review it, and run FFIA analysis.",
        eyebrow="Invoice Intelligence",
    )
    _render_upload_invoice_section(
        current_user,
        section_title="Upload & Review",
        section_description="Extract invoice details, validate the OCR output, then save or analyze the invoice.",
        get_extract_invoice_data=get_extract_invoice_data,
        get_run_agent=get_run_agent,
    )
