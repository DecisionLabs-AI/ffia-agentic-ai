"use client";

// Step 1: Upload Cost Data — mirrors Streamlit _render_upload_invoice_section().
// Reusable: embedded as step 4 inside Business Setup wizard.
// userId comes from parent (already authenticated), so no auth check here.
// Flow: select file → auto-OCR → review/edit header → Save → refresh invoice list.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  deleteInvoice,
  getCurrentMonthInvoices,
  getInvoiceItemsForUpload,
  getInvoiceItemsForUploadUrl,
  ocrInvoicePreview,
  saveInvoiceFromOCR,
  InvoiceItem,
  InvoiceResponse,
  InvoiceSavePayload,
  OCRPreviewResponse,
} from "@/lib/api";

const INVOICE_ADVISOR_PROMPT = "จากใบเสร็จล่าสุด ช่วยวิเคราะห์วัตถุดิบที่กระทบต้นทุนมากที่สุด";

interface Props {
  userId: string;
  onNext: () => void;
  onBack: () => void;
  onCancel: () => void;
}

export default function InvoiceUploadStep({ userId, onNext, onBack, onCancel }: Props) {
  // Step 2: Upload & OCR state
  const [file, setFile]             = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrData, setOcrData]       = useState<OCRPreviewResponse | null>(null);
  const [ocrError, setOcrError]     = useState("");

  // Step 3: Editable review form (header fields populated from OCR, user may adjust)
  const [vendor, setVendor]             = useState("");
  const [invoiceNo, setInvoiceNo]       = useState("");
  const [invoiceDate, setInvoiceDate]   = useState("");
  const [totalAmount, setTotalAmount]   = useState(0);

  // Step 4: Invoice save state
  const [saving, setSaving]       = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveOk, setSaveOk]       = useState(false);
  const [savedNo, setSavedNo]     = useState("");

  // Step 5: Current-month invoice list state
  const [invoices, setInvoices]         = useState<InvoiceResponse[]>([]);
  const [listLoading, setListLoading]   = useState(false);
  const [listError, setListError]       = useState("");
  const [selectedId, setSelectedId]     = useState<number | null>(null);
  const [lineItems, setLineItems]       = useState<InvoiceItem[]>([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting]         = useState(false);
  const [deleteError, setDeleteError]   = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  function inputNumberValue(value: number) {
    return Number.isFinite(value) ? String(value) : "";
  }

  function parseNumberInput(value: string) {
    if (value.trim() === "") return Number.NaN;
    return Number(value);
  }

  function updateOcrItems(updater: (items: InvoiceItem[]) => InvoiceItem[]) {
    setOcrData((prev) => {
      if (!prev) return prev;
      return { ...prev, items: updater(prev.items) };
    });
  }

  function updateLineItemName(index: number, name: string) {
    updateOcrItems((items) =>
      items.map((item, idx) =>
        idx === index ? { ...item, name, item_name: name } : item,
      ),
    );
    setSaveError("");
  }

  function updateLineItemNumber(index: number, field: "qty" | "unit_price" | "total", value: string) {
    const nextValue = parseNumberInput(value);
    updateOcrItems((items) =>
      items.map((item, idx) => {
        if (idx !== index) return item;
        const updated = { ...item, [field]: nextValue };
        if (field === "qty" || field === "unit_price") {
          updated.total = Number.isFinite(updated.qty) && Number.isFinite(updated.unit_price)
            ? Number((updated.qty * updated.unit_price).toFixed(2))
            : Number.NaN;
        }
        return updated;
      }),
    );
    setSaveError("");
  }

  function formatLineItemNumber(index: number, field: "unit_price" | "total") {
    updateOcrItems((items) =>
      items.map((item, idx) =>
        idx === index && Number.isFinite(item[field])
          ? { ...item, [field]: Number(item[field].toFixed(2)) }
          : item,
      ),
    );
  }

  function addLineItem() {
    updateOcrItems((items) => [...items, { name: "", item_name: "", qty: 0, unit_price: 0, total: 0 }]);
    setSaveError("");
  }

  function deleteLineItem(index: number) {
    updateOcrItems((items) => items.filter((_, idx) => idx !== index));
    setSaveError("");
  }

  function clearLineItem(index: number) {
    updateOcrItems((items) =>
      items.map((item, idx) =>
        idx === index ? { ...item, name: "", item_name: "", qty: 0, unit_price: 0, total: 0 } : item,
      ),
    );
    setSaveError("");
  }

  function validateBeforeSave(data: OCRPreviewResponse) {
    if (!invoiceNo.trim()) return "Invoice number is required.";
    if (!Number.isFinite(totalAmount) || totalAmount < 0) return "Total amount must be a number greater than or equal to 0.";
    if (data.items.length === 0) return "At least one line item is required.";

    for (const [index, item] of data.items.entries()) {
      const rowLabel = `Line item ${index + 1}`;
      if (!String(item.name || item.item_name || "").trim()) return `${rowLabel}: item name cannot be empty.`;
      if (!Number.isFinite(item.qty) || item.qty < 0) return `${rowLabel}: qty must be a number greater than or equal to 0.`;
      if (!Number.isFinite(item.unit_price) || item.unit_price < 0) return `${rowLabel}: unit price must be a number greater than or equal to 0.`;
      if (!Number.isFinite(item.total) || item.total < 0) return `${rowLabel}: total must be a number greater than or equal to 0.`;
    }

    return "";
  }

  // Step 6: Load invoice list when userId becomes available
  useEffect(() => {
    if (!userId) return;
    loadInvoices();
  }, [userId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Step 7: Fetch line items whenever selected invoice changes
  useEffect(() => {
    if (selectedId === null || !userId) { setLineItems([]); return; }
    const selectedInvoice = invoices.find((inv) => inv.id === selectedId);
    let cancelled = false;
    setItemsLoading(true);
    setLineItems([]);
    if (process.env.NODE_ENV === "development") {
      console.log("[InvoiceUploadStep] fetch invoice items", {
        selected_invoice_id: selectedId,
        selected_invoice_no: selectedInvoice?.invoice_no ?? "",
        user_id: userId,
        endpoint_url: getInvoiceItemsForUploadUrl(selectedId, userId),
      });
    }
    getInvoiceItemsForUpload(selectedId, userId)
      .then((data) => { if (!cancelled) setLineItems(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setItemsLoading(false); });
    return () => { cancelled = true; };
  }, [selectedId, userId, invoices]);

  async function loadInvoices() {
    setListLoading(true);
    setListError("");
    if (process.env.NODE_ENV === "development") {
      console.log("[InvoiceUploadStep] loadInvoices user_id:", userId);
    }
    try {
      const data = await getCurrentMonthInvoices(userId);
      if (process.env.NODE_ENV === "development") {
        console.log("[InvoiceUploadStep] invoices returned:", data.length);
      }
      setInvoices(data);
      setSelectedId((prev) => {
        if (data.some((inv) => inv.id === prev)) return prev;
        return data.length > 0 ? data[0].id : null;
      });
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Unable to load invoices.");
    } finally {
      setListLoading(false);
    }
  }

  // Step 8: File selected → create preview URL + auto-trigger OCR
  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setOcrData(null);
    setOcrError("");
    setSaveOk(false);
    setSaveError("");
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
    runOcr(f);
  }

  async function runOcr(f: File) {
    setOcrLoading(true);
    setOcrError("");
    try {
      const result = await ocrInvoicePreview(f, userId);
      setOcrData(result);
      setVendor(result.vendor);
      setInvoiceNo(result.invoice_no);
      setInvoiceDate(result.invoice_date || "");
      setTotalAmount(result.total_amount);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "OCR failed";
      if (msg.toLowerCase().includes("timeout") || msg.toLowerCase().includes("timed out")) {
        setOcrError("OCR ใช้เวลานานเกินไป ลองอัปโหลดใหม่อีกครั้ง");
      } else {
        setOcrError(msg);
      }
    } finally {
      setOcrLoading(false);
    }
  }

  function handleClear() {
    setFile(null);
    setPreviewUrl("");
    setOcrData(null);
    setOcrError("");
    setSaveOk(false);
    setSaveError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // Step 9: Save after review
  async function handleSave() {
    if (!ocrData) return;
    const validationError = validateBeforeSave(ocrData);
    if (validationError) {
      setSaveError(validationError);
      setSaveOk(false);
      return;
    }

    setSaving(true);
    setSaveError("");
    setSaveOk(false);
    try {
      const payload: InvoiceSavePayload = {
        vendor: vendor.trim(),
        invoice_no: invoiceNo.trim(),
        invoice_date: invoiceDate,
        total_amount: totalAmount,
        items: ocrData.items.map((item) => ({
          ...item,
          name: String(item.name || item.item_name || "").trim(),
          item_name: String(item.name || item.item_name || "").trim(),
          qty: Number(item.qty),
          unit_price: Number(item.unit_price),
          total: Number(item.total),
        })),
      };
      const result = await saveInvoiceFromOCR(userId, payload);
      if (!result.ok) {
        setSaveError(result.error || "Unable to save invoice.");
        return;
      }
      setSaveOk(true);
      setSavedNo(result.invoice_no);
      handleClear();
      await loadInvoices();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Unable to save invoice.");
    } finally {
      setSaving(false);
    }
  }

  // Step 10: Two-step delete — confirm then delete
  async function handleDelete(id: number) {
    setDeleting(true);
    setDeleteError("");
    try {
      await deleteInvoice(id, userId);
      setConfirmDeleteId(null);
      if (selectedId === id) { setSelectedId(null); setLineItems([]); }
      await loadInvoices();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setDeleting(false);
    }
  }

  function thb(n: number) {
    return n.toLocaleString("th-TH", { minimumFractionDigits: 2 });
  }

  return (
    <div>
      {/* Step 11: Step heading (matches other wizard steps) */}
      <p className="text-lg font-black text-slate-900">Upload Cost Data</p>
      <p className="mt-1 text-sm text-slate-500">
        Upload invoice images, review extracted details, save invoices, and inspect
        current-month invoice items.
      </p>
      <div className="mt-3">
        <Link
          href="/cost-data"
          className="inline-flex items-center rounded-lg border border-orange-200 bg-white px-3 py-1.5 text-xs font-bold text-orange-700 transition hover:bg-orange-50"
        >
          จัดการรายการต้นทุน
        </Link>
      </div>

      {/* Step 12: Invoice save success banner */}
      {saveOk && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
          <span>
            ✓ Invoice <strong>{savedNo}</strong> saved successfully.
          </span>
          <Link
            href={`/chat?prompt=${encodeURIComponent(INVOICE_ADVISOR_PROMPT)}`}
            className="rounded-lg border border-emerald-300 bg-white px-3 py-1.5 text-xs font-black text-emerald-700 transition hover:bg-emerald-50"
          >
            ให้ FFIA วิเคราะห์ใบเสร็จนี้ →
          </Link>
        </div>
      )}

      {/* ─── Step 1: Upload Invoice Image ──────────────────────────────────── */}
      <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-5">
        <p className="text-sm font-bold text-slate-700">Step 1: Upload Invoice Image</p>
        <p className="mt-0.5 text-xs text-slate-500">Supported formats: JPG, JPEG, PNG</p>

        {/* File drop-zone */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click(); }}
          className="mt-3 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-orange-200 bg-white px-4 py-7 text-center transition-colors hover:bg-orange-50"
        >
          <svg className="mb-2 h-7 w-7 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          <p className="text-sm font-bold text-orange-700">
            {file ? file.name : "Click to choose an invoice image"}
          </p>
          <p className="mt-0.5 text-xs text-slate-400">JPG, JPEG, PNG</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>

        {/* Step 2: Image preview */}
        {previewUrl && (
          <div className="mt-4">
            <p className="mb-1.5 text-xs font-bold uppercase tracking-wide text-slate-500">
              Step 2: Preview
            </p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={previewUrl}
              alt="Invoice preview"
              className="max-h-72 max-w-full rounded-xl border border-slate-200 object-contain"
            />
          </div>
        )}

        {/* OCR loading */}
        {ocrLoading && (
          <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-700">
            <span className="animate-pulse">กำลังวิเคราะห์ใบเสร็จ... (อาจใช้เวลา 15–30 วินาที)</span>
          </div>
        )}

        {/* OCR error */}
        {ocrError && !ocrLoading && (
          <div className="mt-3 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
            <span>{ocrError}</span>
            <button type="button" onClick={handleClear}
              className="ml-4 flex-shrink-0 rounded-lg border border-red-300 bg-white px-3 py-1 text-xs font-bold text-red-700 hover:bg-red-50">
              Clear
            </button>
          </div>
        )}
      </div>

      {/* ─── Steps 3 & 4: Review + Save ──────────────────────────────────────── */}
      {ocrData && !ocrLoading && (
        <div className="mt-4 rounded-xl border border-orange-100 bg-white p-5">
          <p className="text-sm font-bold text-slate-700">Step 3: Review &amp; Edit Extracted Data</p>
          <p className="mt-0.5 text-xs text-slate-500">
            Please review and adjust extracted data before saving.
          </p>

          {ocrData.ocr_error && (
            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-800">
              ⚠ OCR output could not be parsed cleanly. Review and correct the fields below.
            </div>
          )}

          {/* Editable header fields */}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wide text-slate-500">Vendor</label>
              <input type="text" value={vendor} onChange={(e) => { setVendor(e.target.value); setSaveError(""); }}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100" />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wide text-slate-500">
                Invoice No <span className="text-orange-500">*</span>
              </label>
              <input type="text" value={invoiceNo} onChange={(e) => { setInvoiceNo(e.target.value); setSaveError(""); }}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100" />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wide text-slate-500">Invoice Date</label>
              <input type="date" value={invoiceDate} onChange={(e) => { setInvoiceDate(e.target.value); setSaveError(""); }}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100" />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wide text-slate-500">Total Amount (฿)</label>
              <input type="number" step="0.01" min={0} value={inputNumberValue(totalAmount)}
                onChange={(e) => { setTotalAmount(parseNumberInput(e.target.value)); setSaveError(""); }}
                onBlur={() => { if (Number.isFinite(totalAmount)) setTotalAmount(Number(totalAmount.toFixed(2))); }}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100" />
            </div>
          </div>

          {/* Editable line items table */}
          <div className="mt-4">
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Line Items</p>
              <button type="button" onClick={addLineItem}
                className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-1.5 text-xs font-bold text-orange-700 hover:bg-orange-100">
                Add line item
              </button>
            </div>
            <div className="overflow-x-auto rounded-xl border border-slate-100">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50">
                    <th className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wide text-slate-500">Item Name</th>
                    <th className="w-24 px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">Qty</th>
                    <th className="w-32 px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">Unit Price</th>
                    <th className="w-32 px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">Total</th>
                    <th className="w-32 px-3 py-2 text-center text-xs font-bold uppercase tracking-wide text-slate-500">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {ocrData.items.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-3 py-4 text-center text-sm font-semibold text-slate-400">
                        No line items yet. Add at least one item before saving.
                      </td>
                    </tr>
                  ) : (
                    ocrData.items.map((item, idx) => (
                      <tr key={idx} className="border-b border-slate-50 last:border-0">
                        <td className="px-3 py-2">
                          <input
                            type="text"
                            value={item.name || item.item_name || ""}
                            onChange={(e) => updateLineItemName(idx, e.target.value)}
                            className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-sm font-semibold text-slate-800 outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            value={inputNumberValue(item.qty)}
                            onChange={(e) => updateLineItemNumber(idx, "qty", e.target.value)}
                            className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-right text-sm text-slate-600 outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            value={inputNumberValue(item.unit_price)}
                            onChange={(e) => updateLineItemNumber(idx, "unit_price", e.target.value)}
                            onBlur={() => formatLineItemNumber(idx, "unit_price")}
                            className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-right text-sm text-slate-600 outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            value={inputNumberValue(item.total)}
                            onChange={(e) => updateLineItemNumber(idx, "total", e.target.value)}
                            onBlur={() => formatLineItemNumber(idx, "total")}
                            className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-right text-sm font-semibold text-slate-800 outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center justify-center gap-1.5">
                            <button type="button" onClick={() => clearLineItem(idx)}
                              className="rounded-lg border border-slate-200 px-2 py-1 text-xs font-bold text-slate-500 hover:bg-slate-50">
                              Clear
                            </button>
                            <button type="button" onClick={() => deleteLineItem(idx)}
                              className="rounded-lg border border-red-200 px-2 py-1 text-xs font-bold text-red-600 hover:bg-red-50">
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              {ocrData.items.length} line item{ocrData.items.length !== 1 ? "s" : ""} ready to save
            </p>
          </div>

          {saveError && (
            <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-semibold text-red-700">
              {saveError}
            </div>
          )}

          {/* Step 4 save / cancel */}
          <div className="mt-4 border-t border-slate-100 pt-4">
            <p className="mb-3 text-sm font-bold text-slate-700">Step 4: Save Invoice</p>
            <div className="flex gap-2">
              <button type="button" onClick={handleSave} disabled={saving}
                className="rounded-xl bg-orange-600 px-5 py-2 text-sm font-black text-white transition hover:bg-orange-700 disabled:cursor-not-allowed disabled:opacity-40">
                {saving ? "กำลังบันทึก..." : "Save Invoice to Database"}
              </button>
              <button type="button" onClick={handleClear} disabled={saving}
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                Cancel / Clear
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Uploaded Invoices (Current Month) ───────────────────────────────── */}
      <div className="mt-5 rounded-xl border border-orange-100 bg-white p-5">
        <p className="text-sm font-bold text-slate-900">Uploaded Invoices (Recent)</p>

        {listLoading ? (
          <p className="mt-3 animate-pulse text-sm font-semibold text-slate-500">กำลังโหลด...</p>
        ) : listError ? (
          <div className="mt-3 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-semibold text-red-700">
            <span>{listError}</span>
            <button type="button" onClick={loadInvoices}
              className="ml-4 flex-shrink-0 rounded-lg border border-red-300 bg-white px-3 py-1 text-xs font-bold text-red-700 hover:bg-red-50">
              Retry
            </button>
          </div>
        ) : invoices.length === 0 ? (
          <p className="mt-3 text-sm font-semibold text-slate-400">
            ยังไม่มีใบเสร็จที่บันทึกในเดือนนี้
          </p>
        ) : (
          <>
            {deleteError && (
              <div className="mb-3 mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-semibold text-red-700">
                {deleteError}
              </div>
            )}

            {/* Invoice table — columns match Streamlit _render_monthly_invoices_section */}
            <div className="mt-3 overflow-x-auto rounded-xl border border-slate-100">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50">
                    <th className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wide text-slate-500">Date</th>
                    <th className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wide text-slate-500">Vendor</th>
                    <th className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wide text-slate-500">Invoice No</th>
                    <th className="px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">Total (THB)</th>
                    <th className="px-3 py-2 text-center text-xs font-bold uppercase tracking-wide text-slate-500">Del</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="border-b border-slate-50 last:border-0">
                      <td className="px-3 py-2 text-slate-600">{inv.invoice_date}</td>
                      <td className="px-3 py-2 font-semibold text-slate-800">{inv.vendor}</td>
                      <td className="px-3 py-2 text-slate-600">{inv.invoice_no}</td>
                      <td className="px-3 py-2 text-right font-semibold text-slate-800">{thb(inv.total_amount)}</td>
                      <td className="px-3 py-2 text-center">
                        {/* Two-step confirm matches Streamlit confirm dialog */}
                        {confirmDeleteId === inv.id ? (
                          <div className="flex items-center justify-center gap-1">
                            <button type="button" onClick={() => handleDelete(inv.id)} disabled={deleting}
                              className="rounded-lg bg-red-600 px-2 py-0.5 text-xs font-bold text-white hover:bg-red-700 disabled:opacity-40">
                              {deleting ? "..." : "ลบ"}
                            </button>
                            <button type="button"
                              onClick={() => { setConfirmDeleteId(null); setDeleteError(""); }}
                              className="rounded-lg border border-slate-200 px-2 py-0.5 text-xs font-bold text-slate-600 hover:bg-slate-50">
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button type="button"
                            onClick={() => { setConfirmDeleteId(inv.id); setDeleteError(""); }}
                            className="rounded-lg border border-red-200 px-2 py-0.5 text-xs font-bold text-red-600 hover:bg-red-50">
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Invoice selector dropdown — label format matches Streamlit selectbox */}
            <div className="mt-4">
              <label className="block text-sm font-bold text-slate-700">
                Select an invoice to view items
              </label>
              <select value={selectedId ?? ""}
                onChange={(e) => setSelectedId(Number(e.target.value))}
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100">
                {invoices.map((inv) => (
                  <option key={inv.id} value={inv.id}>
                    {inv.invoice_no} — {inv.vendor} ({inv.invoice_date})
                  </option>
                ))}
              </select>
            </div>

            {/* Line items for selected invoice */}
            {selectedId !== null && (
              <div className="mt-4">
                <p className="mb-1.5 text-xs font-bold uppercase tracking-wide text-slate-500">
                  Line Items — {invoices.find((i) => i.id === selectedId)?.invoice_no ?? ""}
                </p>
                {itemsLoading ? (
                  <p className="animate-pulse text-sm font-semibold text-slate-400">กำลังโหลด...</p>
                ) : lineItems.length === 0 ? (
                  <p className="text-sm text-slate-400">No line items found for this invoice.</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-100">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-100 bg-slate-50">
                          <th className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wide text-slate-500">Item Name</th>
                          <th className="px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">Qty</th>
                          <th className="px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">Unit Price</th>
                          <th className="px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lineItems.map((item, idx) => (
                          <tr key={item.item_id ?? idx} className="border-b border-slate-50 last:border-0">
                            <td className="px-3 py-2 font-semibold text-slate-800">{item.name}</td>
                            <td className="px-3 py-2 text-right text-slate-600">{item.qty}</td>
                            <td className="px-3 py-2 text-right text-slate-600">{thb(item.unit_price)}</td>
                            <td className="px-3 py-2 text-right font-semibold text-slate-800">{thb(item.total)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* ─── Navigation buttons (same style as other wizard steps) ──────────── */}
      <div className="mt-6 flex items-center justify-between">
        <div className="flex gap-2">
          <button type="button" onClick={onCancel}
            className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-600 hover:bg-slate-50">
            Cancel
          </button>
          <button type="button" onClick={onBack}
            className="rounded-xl border border-orange-200 px-4 py-2.5 text-sm font-bold text-orange-700 hover:bg-orange-50">
            ← Back
          </button>
        </div>
        <button type="button" onClick={onNext}
          className="rounded-xl bg-orange-600 px-6 py-2.5 text-sm font-black text-white transition hover:bg-orange-700">
          Continue to Review →
        </button>
      </div>
    </div>
  );
}
