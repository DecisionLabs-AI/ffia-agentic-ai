"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { getCurrentUser } from "@/lib/auth";
import { DashboardSnapshot, getDashboardSnapshot } from "@/lib/api";

function formatBaht(value: number | null | undefined) {
  if (value === null || value === undefined) return "ไม่มีข้อมูล";
  return `฿${value.toLocaleString("th-TH", { maximumFractionDigits: 0 })}`;
}

function MetricCard({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-3 text-2xl font-black text-slate-950">{value}</p>
      {note ? <p className="mt-2 text-xs text-slate-500">{note}</p> : null}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {[0, 1, 2, 3].map((item) => (
        <div key={item} className="h-32 animate-pulse rounded-2xl bg-white/80" />
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const user = getCurrentUser();
    if (!user) { window.location.href = "/login"; return; }

    const userId = user.user_id;
    if (process.env.NODE_ENV === "development") {
      console.log("[Dashboard] user_id:", userId);
      console.log("[Dashboard] endpoint:", `/dashboard-summary?user_id=${userId}`);
    }

    getDashboardSnapshot(userId)
      .then((data) => {
        if (process.env.NODE_ENV === "development") {
          console.log("[Dashboard] response:", {
            invoice_count: data.invoice_count,
            items_tracked: data.items_tracked,
            monthly_spend: data.monthly_spend,
            channels: data.channel_mix.length,
            profile: data.profile.restaurant_name,
            error: data.error,
          });
        }
        setSnapshot(data);
        if (data.error) setError(data.error);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "โหลดข้อมูลไม่สำเร็จ"))
      .finally(() => setLoading(false));
  }, []);

  const maxSpend = useMemo(() => {
    return Math.max(...(snapshot?.top_spend_items.map((item) => item.amount) ?? [0]), 1);
  }, [snapshot]);

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <div className="mb-6">
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-600">Business snapshot</p>
          <h1 className="mt-2 text-3xl font-black text-slate-950">แดชบอร์ดต้นทุนร้าน</h1>
          <p className="mt-2 text-sm text-slate-600">สรุปภาพรวมที่ช่วยตัดสินใจเรื่องราคา ต้นทุน และช่องทางขาย</p>
        </div>

        {loading ? <Skeleton /> : null}

        {error ? (
          <div className="mb-4 rounded-2xl border border-red-100 bg-red-50 p-4 text-sm font-medium text-red-700">
            {error}
          </div>
        ) : null}

        {!loading && !error && !snapshot ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-600 shadow-sm">
            ยังไม่มีข้อมูลแดชบอร์ดให้แสดง
          </div>
        ) : null}

        {snapshot ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="ราคาดีเซลล่าสุด"
                value={snapshot.oil_price.diesel ? `฿${snapshot.oil_price.diesel.toFixed(2)} / ลิตร` : "ไม่มีข้อมูล"}
                note={snapshot.oil_price.updated_at
                  ? `${snapshot.oil_price.source} อัปเดต ${snapshot.oil_price.updated_at}`
                  : (snapshot.oil_price.source ?? undefined)}
              />
              <MetricCard
                label="ค่าใช้จ่ายรวม"
                value={snapshot.monthly_spend !== null ? formatBaht(snapshot.monthly_spend) : "ไม่มีข้อมูล"}
              />
              <MetricCard
                label="จำนวนใบเสร็จ"
                value={snapshot.invoice_count !== null ? `${snapshot.invoice_count} ใบ` : "ไม่มีข้อมูล"}
              />
              <MetricCard
                label="วัตถุดิบที่ติดตาม"
                value={snapshot.items_tracked !== null ? `${snapshot.items_tracked} รายการ` : "ไม่มีข้อมูล"}
              />
            </div>

            <div className="mt-6 grid gap-5 lg:grid-cols-[0.85fr_1.15fr]">
              <section className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
                <h2 className="text-lg font-black text-slate-950">โปรไฟล์ร้าน</h2>
                <div className="mt-4 space-y-4 text-sm">
                  <div>
                    <p className="font-semibold text-slate-500">ชื่อร้าน</p>
                    <p className="mt-1 text-base font-bold text-slate-950">
                      {snapshot.profile.restaurant_name ?? "ยังไม่ได้ตั้งค่า"}
                    </p>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-500">ประเภทร้าน</p>
                    <p className="mt-1 text-slate-800">
                      {snapshot.profile.restaurant_type ?? "ไม่มีข้อมูล"}
                    </p>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-500">ช่องทางหลัก</p>
                    <p className="mt-1 text-slate-800">
                      {snapshot.profile.main_platform ?? "ยังไม่มีข้อมูลช่องทาง"}
                    </p>
                  </div>
                </div>
              </section>

              <section className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
                <h2 className="text-lg font-black text-slate-950">สัดส่วนช่องทางขาย</h2>
                {snapshot.channel_mix.length ? (
                  <div className="mt-4 space-y-4">
                    {snapshot.channel_mix.map((item) => (
                      <div key={item.channel}>
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-bold text-slate-800">{item.channel}</span>
                          <span className="text-slate-500">{item.revenue_share_pct.toFixed(0)}%</span>
                        </div>
                        <div className="mt-2 h-2 rounded-full bg-orange-100">
                          <div
                            className="h-2 rounded-full bg-orange-500"
                            style={{ width: `${Math.min(item.revenue_share_pct, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                    ยังไม่มีข้อมูลช่องทางขาย ตั้งค่าร้านก่อนเพื่อดูผลกระทบจาก GP และเดลิเวอรี่
                  </p>
                )}
              </section>
            </div>

            <section className="mt-6 rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-black text-slate-950">วัตถุดิบที่ใช้เงินมากที่สุด</h2>
              {snapshot.top_spend_items.length ? (
                <div className="mt-4 space-y-4">
                  {snapshot.top_spend_items.map((item) => (
                    <div key={item.item_name}>
                      <div className="flex items-center justify-between gap-4 text-sm">
                        <span className="font-bold text-slate-800">{item.item_name}</span>
                        <span className="shrink-0 font-semibold text-slate-600">{formatBaht(item.amount)}</span>
                      </div>
                      <div className="mt-2 h-2 rounded-full bg-slate-100">
                        <div
                          className="h-2 rounded-full bg-slate-800"
                          style={{ width: `${Math.max((item.amount / maxSpend) * 100, 4)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                  ยังไม่มีข้อมูลรายการต้นทุน อัปโหลดใบเสร็จเพื่อดูรายการวัตถุดิบที่ใช้เงินมากที่สุด
                </p>
              )}
            </section>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
