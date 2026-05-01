"use client";

// Thin wrapper — Upload Cost Data is step 4 inside Business Setup wizard.
// This route exists for direct deep-link access but is not in the sidebar nav.
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import InvoiceUploadStep from "@/components/setup/InvoiceUploadStep";
import { getCurrentUser } from "@/lib/auth";

export default function UploadPage() {
  const [userId, setUserId] = useState("");

  useEffect(() => {
    const user = getCurrentUser();
    if (!user) { window.location.href = "/login"; return; }
    setUserId(user.user_id);
  }, []);

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-600">
          Upload Cost Data
        </p>
        <h1 className="mt-1 text-3xl font-black text-slate-950">
          Invoice Upload &amp; Cost Data
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          Upload invoice images, review extracted details, save invoices, and
          inspect current-month invoice items.
        </p>

        {userId && (
          <div className="mt-6 rounded-2xl border border-orange-100 bg-white p-6 shadow-sm">
            <InvoiceUploadStep
              userId={userId}
              onNext={() => { window.location.href = "/setup"; }}
              onBack={() => window.history.back()}
              onCancel={() => { window.location.href = "/"; }}
            />
          </div>
        )}
      </div>
    </AppShell>
  );
}
