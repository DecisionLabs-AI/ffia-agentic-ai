"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import {
  getCurrentMonthInvoices,
  getInvoiceItemsForUpload,
  toggleInvoiceItemExclusion,
  InvoiceItem,
  InvoiceResponse,
} from "@/lib/api";
import { getCurrentUser } from "@/lib/auth";

function thb(value: number) {
  return value.toLocaleString("th-TH", { minimumFractionDigits: 2 });
}

function invoiceLabel(invoice: InvoiceResponse) {
  const vendor = invoice.vendor ? ` — ${invoice.vendor}` : "";
  const date = invoice.invoice_date ? ` (${invoice.invoice_date})` : "";
  return `${invoice.invoice_no}${vendor}${date}`;
}

export default function CostDataPage() {
  const [userId, setUserId] = useState("");
  const [invoices, setInvoices] = useState<InvoiceResponse[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [lineItems, setLineItems] = useState<InvoiceItem[]>([]);
  const [invoicesLoading, setInvoicesLoading] = useState(true);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [error, setError] = useState("");
  const [excludingId, setExcludingId] = useState<number | null>(null);

  useEffect(() => {
    const user = getCurrentUser();
    if (!user) {
      window.location.href = "/login";
      return;
    }
    setUserId(user.user_id);

    setInvoicesLoading(true);
    setError("");
    getCurrentMonthInvoices(user.user_id)
      .then((rows) => {
        setInvoices(rows);
        setSelectedId(rows.length ? rows[0].id : null);
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Unable to load invoices.")
      )
      .finally(() => setInvoicesLoading(false));
  }, []);

  useEffect(() => {
    if (!userId || selectedId === null) {
      setLineItems([]);
      return;
    }

    let cancelled = false;
    setItemsLoading(true);
    setError("");
    getInvoiceItemsForUpload(selectedId, userId)
      .then((rows) => {
        if (!cancelled) setLineItems(rows);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLineItems([]);
          setError(err instanceof Error ? err.message : "Unable to load line items.");
        }
      })
      .finally(() => {
        if (!cancelled) setItemsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId, userId]);

  const selectedInvoice = useMemo(
    () => invoices.find((invoice) => invoice.id === selectedId) ?? null,
    [invoices, selectedId],
  );

  async function handleToggleExclusion(itemId: number, currentlyExcluded: boolean) {
    if (!userId) return;
    setExcludingId(itemId);
    setError("");
    const nextExcluded = !currentlyExcluded;

    setLineItems((current) =>
      current.map((item) =>
        item.item_id === itemId
          ? {
              ...item,
              excluded_from_analysis: nextExcluded,
              excluded_reason: nextExcluded ? item.excluded_reason ?? null : null,
            }
          : item,
      ),
    );

    try {
      const updated = await toggleInvoiceItemExclusion(itemId, userId, nextExcluded);
      setLineItems((current) =>
        current.map((item) =>
          item.item_id === itemId
            ? {
                ...item,
                ...updated,
                name: updated.name || updated.item_name || item.name,
              }
            : item,
        ),
      );
    } catch (err) {
      setLineItems((current) =>
        current.map((item) =>
          item.item_id === itemId
            ? {
                ...item,
                excluded_from_analysis: currentlyExcluded,
                excluded_reason: currentlyExcluded ? item.excluded_reason ?? null : null,
              }
            : item,
        ),
      );
      setError(err instanceof Error ? err.message : "Unable to update line item.");
    } finally {
      setExcludingId(null);
    }
  }

  function handleUploadMore() {
    window.location.href = "/setup?step=4";
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-600">
              Cost Data
            </p>
            <h1 className="mt-1 text-3xl font-black text-slate-950">
              Cost Data / ข้อมูลต้นทุน
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Review invoice line items and exclude non-business items from analysis.
            </p>
          </div>
          <button
            type="button"
            onClick={handleUploadMore}
            className="rounded-xl bg-orange-600 px-5 py-3 text-sm font-black text-white shadow-sm transition hover:bg-orange-700"
          >
            อัปโหลดใบเสร็จเพิ่ม
          </button>
        </header>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
            {error}
          </div>
        )}

        <section className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
          <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
                Invoice
              </span>
              <select
                value={selectedId ?? ""}
                disabled={invoicesLoading || invoices.length === 0}
                onChange={(event) => setSelectedId(Number(event.target.value))}
                className="mt-2 w-full rounded-xl border border-orange-100 bg-white px-3 py-2.5 text-sm font-semibold text-slate-800 outline-none transition focus:border-orange-300 focus:ring-4 focus:ring-orange-100 disabled:bg-slate-50 disabled:text-slate-400"
              >
                {invoicesLoading ? (
                  <option value="">Loading invoices...</option>
                ) : invoices.length === 0 ? (
                  <option value="">No saved invoices</option>
                ) : (
                  invoices.map((invoice) => (
                    <option key={invoice.id} value={invoice.id}>
                      {invoiceLabel(invoice)}
                    </option>
                  ))
                )}
              </select>
            </label>

            {selectedInvoice && (
              <div className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-2.5 text-sm">
                <p className="font-black text-slate-900">{selectedInvoice.invoice_no}</p>
                <p className="mt-0.5 text-xs font-semibold text-slate-500">
                  {selectedInvoice.vendor || "Unknown vendor"} · ฿{thb(selectedInvoice.total_amount)}
                </p>
              </div>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-orange-600">
                Line Items
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-500">
                {selectedInvoice ? selectedInvoice.invoice_no : "Select an invoice"}
              </p>
            </div>
            <span className="rounded-full bg-orange-50 px-3 py-1 text-xs font-bold text-orange-700">
              {lineItems.length} items
            </span>
          </div>

          {itemsLoading ? (
            <p className="animate-pulse text-sm font-semibold text-slate-400">กำลังโหลด...</p>
          ) : lineItems.length === 0 ? (
            <p className="text-sm text-slate-400">No line items found for this invoice.</p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-100">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50">
                    <th className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wide text-slate-500">
                      Item Name
                    </th>
                    <th className="px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">
                      Qty
                    </th>
                    <th className="px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">
                      Unit Price
                    </th>
                    <th className="px-3 py-2 text-right text-xs font-bold uppercase tracking-wide text-slate-500">
                      Total
                    </th>
                    <th className="px-3 py-2 text-center text-xs font-bold uppercase tracking-wide text-slate-500">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {lineItems.map((item, index) => {
                    const isExcluded = item.excluded_from_analysis ?? false;
                    return (
                      <tr
                        key={item.item_id ?? index}
                        className={`border-b border-slate-50 last:border-0 ${
                          isExcluded ? "bg-slate-50/60 text-slate-400" : ""
                        }`}
                      >
                        <td
                          className={`px-3 py-2 font-semibold ${
                            isExcluded ? "text-slate-400" : "text-slate-800"
                          }`}
                        >
                          <span>{item.name}</span>
                          {isExcluded && (
                            <span className="ml-2 inline-flex rounded-full bg-slate-200 px-2 py-0.5 text-[0.65rem] font-bold text-slate-600">
                              ไม่นับแล้ว
                            </span>
                          )}
                        </td>
                        <td className={`px-3 py-2 text-right ${isExcluded ? "text-slate-400" : "text-slate-600"}`}>
                          {item.qty}
                        </td>
                        <td className={`px-3 py-2 text-right ${isExcluded ? "text-slate-400" : "text-slate-600"}`}>
                          {thb(item.unit_price)}
                        </td>
                        <td className={`px-3 py-2 text-right font-semibold ${isExcluded ? "text-slate-400" : "text-slate-800"}`}>
                          {thb(item.total)}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {item.item_id != null && (
                            <button
                              type="button"
                              disabled={excludingId === item.item_id}
                              onClick={() => handleToggleExclusion(item.item_id!, isExcluded)}
                              className={`rounded-lg border px-2.5 py-1 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                                isExcluded
                                  ? "border-emerald-200 bg-white text-emerald-700 hover:bg-emerald-50"
                                  : "border-amber-200 bg-white text-amber-700 hover:bg-amber-50"
                              }`}
                            >
                              {excludingId === item.item_id
                                ? "..."
                                : isExcluded
                                  ? "นับกลับเข้าไป"
                                  : "ไม่นับในต้นทุน"}
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
