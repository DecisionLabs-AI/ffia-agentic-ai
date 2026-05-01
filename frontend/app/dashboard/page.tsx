"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { getCurrentUser } from "@/lib/auth";
import { DashboardSnapshot, getDashboardSnapshot } from "@/lib/api";

// ── Formatters ────────────────────────────────────────────────────────────────

function formatBaht(value: number | null | undefined) {
  if (value == null) return "—";
  return `฿${value.toLocaleString("th-TH", { maximumFractionDigits: 0 })}`;
}

const STORE_TYPE_LABELS: Record<string, string> = {
  ghost_kitchen: "Ghost Kitchen",
  dine_in: "ร้านนั่งทาน",
  delivery_only: "Delivery Only",
  cafe: "คาเฟ่",
  food_truck: "Food Truck",
};

const RESTAURANT_TYPE_LABELS: Record<string, string> = {
  restaurant: "ร้านอาหาร",
  cafe: "คาเฟ่",
  bakery: "เบเกอรี่",
  streetfood: "อาหารริมทาง",
};

// ── Sub-components ────────────────────────────────────────────────────────────

function Chip({
  children,
  variant = "orange",
}: {
  children: React.ReactNode;
  variant?: "orange" | "slate" | "emerald";
}) {
  const cls = {
    orange: "bg-orange-50 text-orange-700 border-orange-200",
    slate: "bg-slate-100 text-slate-500 border-slate-200",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
  }[variant];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${cls}`}
    >
      {children}
    </span>
  );
}

function KpiCard({
  eyebrow,
  value,
  sub,
  note,
  dim,
}: {
  eyebrow: string;
  value: string;
  sub?: string;
  note?: string;
  dim?: boolean;
}) {
  return (
    <div className="flex flex-col rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-slate-400">{eyebrow}</p>
      <p className={`mt-3 text-2xl font-black leading-none ${dim ? "text-slate-300" : "text-slate-950"}`}>
        {value}
      </p>
      {sub && <p className="mt-2 text-xs font-medium text-slate-500">{sub}</p>}
      {note && <p className="mt-1 text-[11px] text-slate-400">{note}</p>}
    </div>
  );
}

function KpiSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="h-32 animate-pulse rounded-2xl border border-orange-50 bg-white/80" />
      ))}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

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
            oil_diesel: data.oil_price.diesel,
            error: data.error,
          });
        }
        setSnapshot(data);
        if (data.error) setError(data.error);
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "โหลดข้อมูลไม่สำเร็จ")
      )
      .finally(() => setLoading(false));
  }, []);

  const maxSpend = useMemo(
    () => Math.max(...(snapshot?.top_spend_items.map((i) => i.amount) ?? [0]), 1),
    [snapshot]
  );

  const topChannel = useMemo(
    () => (snapshot?.channel_mix.length ? snapshot.channel_mix[0] : null),
    [snapshot]
  );

  const highestFeeChannel = useMemo(() => {
    if (!snapshot?.channel_mix.length) return null;
    return snapshot.channel_mix.reduce((best, ch) =>
      ch.platform_fee_pct > best.platform_fee_pct ? ch : best
    );
  }, [snapshot]);

  const { diesel, updated_at: oilDate, source: oilSource } = snapshot?.oil_price ?? {
    diesel: null,
    updated_at: null,
    source: "Bangchak",
  };

  const activeChannelCount = snapshot?.channel_mix.filter((c) => c.is_active).length ?? 0;

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl space-y-6">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-600">
            Cost Intelligence
          </p>
          <h1 className="mt-1 text-3xl font-black text-slate-950">แดชบอร์ดต้นทุนร้าน</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
            สรุปภาพรวมต้นทุน ช่องทางขาย และราคาน้ำมัน เพื่อช่วยตัดสินใจด้านราคาได้แม่นยำขึ้น
          </p>
          {!loading && snapshot && (
            <div className="mt-3 flex flex-wrap gap-2">
              {diesel != null ? (
                <Chip variant="emerald">⛽ Fuel API connected</Chip>
              ) : (
                <Chip variant="slate">⛽ Fuel data unavailable</Chip>
              )}
              {(snapshot.items_tracked ?? 0) > 0 && (
                <Chip variant="orange">{snapshot.items_tracked} รายการวัตถุดิบ</Chip>
              )}
              {(snapshot.invoice_count ?? 0) > 0 && (
                <Chip variant="orange">{snapshot.invoice_count} ใบเสร็จ</Chip>
              )}
            </div>
          )}
        </div>

        {/* ── Error banner ────────────────────────────────────────────────── */}
        {error && (
          <div className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
            {error}
          </div>
        )}

        {/* ── KPI Row ─────────────────────────────────────────────────────── */}
        {loading ? (
          <KpiSkeleton />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              eyebrow="ราคาดีเซลล่าสุด"
              value={diesel != null ? `฿${diesel.toFixed(2)} /L` : "ไม่มีข้อมูล"}
              sub={`Hi Diesel S · ${oilSource ?? "Bangchak"}`}
              note={oilDate ? `มีผล ${oilDate}` : "อาจกระทบต้นทุนขนส่ง"}
              dim={diesel == null}
            />
            <KpiCard
              eyebrow="ค่าใช้จ่ายรวม"
              value={snapshot?.monthly_spend != null ? formatBaht(snapshot.monthly_spend) : "—"}
              sub="จากใบเสร็จที่บันทึกล่าสุด"
              dim={snapshot?.monthly_spend == null}
            />
            <KpiCard
              eyebrow="จำนวนใบเสร็จ"
              value={snapshot?.invoice_count != null ? `${snapshot.invoice_count} ใบ` : "—"}
              sub="ใบเสร็จที่บันทึกแล้ว"
              dim={snapshot?.invoice_count == null}
            />
            <KpiCard
              eyebrow="วัตถุดิบที่ติดตาม"
              value={snapshot?.items_tracked != null ? `${snapshot.items_tracked} รายการ` : "—"}
              sub="รายการทั้งหมดในใบเสร็จ"
              dim={snapshot?.items_tracked == null}
            />
          </div>
        )}

        {/* ── Profile + Channel Mix ──────────────────────────────────────── */}
        {!loading && snapshot && (
          <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">

            {/* Business Profile */}
            <section className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-orange-600">
                Business Profile
              </p>
              <h2 className="mt-2 text-xl font-black text-slate-950">
                {snapshot.profile.restaurant_name ?? "ยังไม่ได้ตั้งชื่อร้าน"}
              </h2>

              <div className="mt-4 space-y-3 text-sm">
                {(
                  [
                    {
                      label: "ประเภทกิจการ",
                      value:
                        RESTAURANT_TYPE_LABELS[snapshot.profile.restaurant_type ?? ""] ??
                        snapshot.profile.restaurant_type,
                    },
                    {
                      label: "รูปแบบร้าน",
                      value:
                        STORE_TYPE_LABELS[snapshot.profile.store_type ?? ""] ??
                        snapshot.profile.store_type,
                    },
                    { label: "ช่องทางหลัก", value: snapshot.profile.main_platform },
                  ] as { label: string; value: string | null | undefined }[]
                ).map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between gap-3 border-b border-slate-50 pb-3 last:border-0 last:pb-0">
                    <span className="font-semibold text-slate-400">{label}</span>
                    <span className="text-right font-bold text-slate-900">{value ?? "—"}</span>
                  </div>
                ))}
              </div>

              {activeChannelCount > 0 && (
                <div className="mt-4 flex items-center justify-between rounded-xl bg-orange-50 px-4 py-2.5">
                  <span className="text-xs font-semibold text-slate-600">ช่องทางที่ใช้งานอยู่</span>
                  <span className="text-sm font-black text-orange-700">{activeChannelCount} ช่องทาง</span>
                </div>
              )}
            </section>

            {/* Channel Mix */}
            <section className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-orange-600">
                Channel Mix
              </p>
              <h2 className="mt-2 text-xl font-black text-slate-950">สัดส่วนช่องทางขาย</h2>

              {snapshot.channel_mix.length ? (
                <div className="mt-4 space-y-4">
                  {snapshot.channel_mix.map((ch) => (
                    <div key={ch.channel}>
                      <div className="flex items-center justify-between gap-2 text-sm">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="truncate font-bold text-slate-800">{ch.channel}</span>
                          {!ch.is_active && (
                            <span className="shrink-0 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                              ปิด
                            </span>
                          )}
                        </div>
                        <div className="flex shrink-0 items-center gap-2 text-xs">
                          <span className="font-bold text-orange-600">
                            Rev {ch.revenue_share_pct.toFixed(0)}%
                          </span>
                          <span className="text-slate-300">|</span>
                          <span className="font-semibold text-slate-500">
                            Fee {ch.platform_fee_pct.toFixed(0)}%
                          </span>
                        </div>
                      </div>
                      <div className="mt-2 flex gap-1">
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-orange-100">
                          <div
                            className="h-full rounded-full bg-orange-500 transition-all duration-300"
                            style={{ width: `${Math.min(ch.revenue_share_pct, 100)}%` }}
                          />
                        </div>
                        {ch.platform_fee_pct > 0 && (
                          <div
                            className="h-2 shrink-0 rounded-full bg-slate-300"
                            style={{ width: `${Math.max(ch.platform_fee_pct * 0.6, 4)}px` }}
                            title={`Fee ${ch.platform_fee_pct}%`}
                          />
                        )}
                      </div>
                    </div>
                  ))}

                  <div className="mt-1 flex items-center gap-4 pt-1 text-[11px] text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-4 rounded-full bg-orange-400" />
                      Revenue share
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-3 rounded-full bg-slate-300" />
                      Platform fee
                    </span>
                  </div>
                </div>
              ) : (
                <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                  ยังไม่มีข้อมูลช่องทางขาย ตั้งค่าร้านก่อนเพื่อดูผลกระทบจาก GP และเดลิเวอรี่
                </p>
              )}
            </section>
          </div>
        )}

        {/* ── Top Spend Items ─────────────────────────────────────────────── */}
        {!loading && snapshot && (
          <section className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-orange-600">
              Cost Analysis
            </p>
            <h2 className="mt-2 text-xl font-black text-slate-950">วัตถุดิบที่ใช้เงินมากที่สุด</h2>

            {snapshot.top_spend_items.length ? (
              <div className="mt-5 space-y-3">
                {snapshot.top_spend_items.map((item, i) => (
                  <div key={item.item_name} className="flex items-center gap-4">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-orange-100 text-[11px] font-black text-orange-600">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="truncate font-bold text-slate-800">{item.item_name}</span>
                        <span className="shrink-0 font-semibold text-slate-500">
                          {formatBaht(item.amount)}
                        </span>
                      </div>
                      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-orange-500 transition-all duration-300"
                          style={{ width: `${Math.max((item.amount / maxSpend) * 100, 4)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-xl bg-slate-50 px-5 py-6 text-center">
                <p className="text-sm font-semibold text-slate-600">
                  ยังไม่มีข้อมูลต้นทุนเพียงพอสำหรับการจัดอันดับวัตถุดิบ
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  อัปโหลดใบเสร็จเพิ่มเพื่อดูว่าวัตถุดิบใดใช้เงินมากที่สุด
                </p>
              </div>
            )}
          </section>
        )}

        {/* ── Quick Insights ──────────────────────────────────────────────── */}
        {!loading && snapshot && (topChannel || diesel != null) && (
          <section className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-orange-600">
              Quick Insights
            </p>
            <h2 className="mt-2 text-xl font-black text-slate-950">ข้อสังเกตจากข้อมูล</h2>
            <div className="mt-4 space-y-2">
              {topChannel && (
                <div className="flex items-start gap-3 rounded-xl border border-orange-100 bg-orange-50 px-4 py-3 text-sm">
                  <span className="shrink-0">📊</span>
                  <span className="text-slate-700">
                    <strong>ช่องทางที่พึ่งพามากที่สุด:</strong>{" "}
                    {topChannel.channel} (Rev {topChannel.revenue_share_pct.toFixed(0)}% ของรายได้)
                  </span>
                </div>
              )}
              {highestFeeChannel && highestFeeChannel.platform_fee_pct > 0 && (
                <div className="flex items-start gap-3 rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm">
                  <span className="shrink-0">⚠️</span>
                  <span className="text-slate-700">
                    <strong>ค่าคอมมิชชันสูงสุด:</strong>{" "}
                    {highestFeeChannel.channel} ({highestFeeChannel.platform_fee_pct.toFixed(0)}% ต่อออเดอร์)
                  </span>
                </div>
              )}
              {diesel != null && (
                <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
                  <span className="shrink-0">⛽</span>
                  <span className="text-slate-700">
                    <strong>ราคาดีเซล ฿{diesel.toFixed(2)}/L</strong>{" "}
                    อาจกระทบต้นทุนขนส่งและวัตถุดิบที่ต้องนำเข้า
                  </span>
                </div>
              )}
            </div>
          </section>
        )}

      </div>
    </AppShell>
  );
}
