// Step 4: AI Risk Profile — summary card, capability tags, alert cards, save
import Link from "next/link";
import type { BusinessSetupChannel, BusinessSetupProfile } from "@/lib/api";

// Step 4a: LPG-intensive food types (from profile.py)
const LPG_FOOD_TYPES = new Set(["rice_curry", "stir_fry", "spicy_soup", "isaan", "chicken_rice"]);

const FOOD_TYPE_COGS_BASE: Record<string, number> = {
  rice_curry: 0.375, noodle: 0.355, porridge: 0.355, chicken_rice: 0.375,
  spicy_soup: 0.375, stir_fry: 0.375, isaan: 0.375, spicy_salad: 0.355,
  healthy: 0.300, vegan: 0.300, meal_prep: 0.300,
};

// Step 4b: Margin computation (mirrors ChannelMixStep — used for Step 4 preview)
function computeNetMargin(channels: BusinessSetupChannel[], profile: BusinessSetupProfile): number {
  const active = channels.filter((c) => c.is_active);
  const totalRev = active.reduce((s, c) => s + c.revenue_share_pct, 0);
  const blendedGp = totalRev <= 0 ? 0
    : active.reduce((s, c) => s + (c.revenue_share_pct / totalRev) * (c.platform_fee_pct / 100), 0);
  const bases = profile.food_types.map((ft) => FOOD_TYPE_COGS_BASE[ft] ?? 0.375);
  const foodCost  = bases.length ? bases.reduce((a, b) => a + b, 0) / bases.length : 0.375;
  const fixedCost = profile.store_type === "ghost_kitchen" ? 0.15
    : profile.store_type === "hybrid_small"  ? 0.20
    : profile.seat_range === "31_plus"       ? 0.28 : 0.25;
  return Math.round((1 - blendedGp - foodCost - fixedCost) * 1000) / 10;
}

// Step 4c: Derive AI profile summary line
function buildAiSummary(profile: BusinessSetupProfile, channels: BusinessSetupChannel[]): string {
  const storeLabels: Record<string, string> = {
    ghost_kitchen: "Ghost Kitchen", hybrid_small: "Hybrid Small Restaurant", full_restaurant: "Full-Service Restaurant",
  };
  const store = storeLabels[profile.store_type] ?? "Restaurant";
  const lpgCount = profile.food_types.filter((ft) => LPG_FOOD_TYPES.has(ft)).length;
  const menuTrait = profile.food_types.length > 0 && lpgCount >= profile.food_types.length / 2
    ? "fuel-sensitive menu" : "varied menu";
  const deliveryRev = channels.filter((c) => c.is_active && ["Grab Food","LINE MAN","Shopee Food"].includes(c.platform))
    .reduce((s, c) => s + c.revenue_share_pct, 0);
  const channelTrait = deliveryRev >= 70 ? "high GP dependency"
    : deliveryRev >= 40 ? "mixed channel revenue" : "strong direct sales";
  return `${store} with ${channelTrait} and ${menuTrait}`;
}

// Step 4d: Fuel sensitivity insight
function buildFuelInsight(profile: BusinessSetupProfile, nm: number): string {
  const total = Math.max(profile.food_types.length, 1);
  const lpgRatio = profile.food_types.filter((ft) => LPG_FOOD_TYPES.has(ft)).length / total;
  if (lpgRatio >= 0.6) {
    const suffix = nm < 18 ? " Act now — margin is already near the threshold." : "";
    return `A ฿5/L diesel increase could reduce your margin by ~3–5%. High fuel sensitivity — most of your menu relies on LPG cooking.${suffix}`;
  }
  if (lpgRatio >= 0.3) {
    const suffix = nm < 18 ? " Act now — margin is already near the threshold." : "";
    return `A ฿5/L diesel increase could reduce your margin by ~1–3%. Moderate fuel sensitivity — some LPG-intensive dishes on your menu.${suffix}`;
  }
  return "Diesel price has limited direct impact on your current menu mix.";
}

// Step 4e: Capability tags
function deriveCapabilityTags(profile: BusinessSetupProfile, channels: BusinessSetupChannel[]): { label: string; color: string; bg: string; border: string }[] {
  const tags: { label: string; color: string; bg: string; border: string }[] = [];
  const deliveryRev = channels.filter((c) => c.is_active && ["Grab Food","LINE MAN","Shopee Food"].includes(c.platform))
    .reduce((s, c) => s + c.revenue_share_pct, 0);
  const walkinRev = channels.find((c) => c.platform === "Walk-in / Self-pickup")?.revenue_share_pct ?? 0;
  if (profile.food_types.some((ft) => LPG_FOOD_TYPES.has(ft)))
    tags.push({ label: "LPG Defense",     color: "#5a87c9", bg: "rgba(89,135,201,0.10)",  border: "rgba(189,210,236,0.50)" });
  if (deliveryRev >= 60)
    tags.push({ label: "GP Optimizer",    color: "#c28747", bg: "rgba(255,190,90,0.10)",  border: "rgba(236,208,169,0.50)" });
  if (walkinRev < 20)
    tags.push({ label: "Channel Mix Fix", color: "#c16f6f", bg: "rgba(220,80,80,0.08)",   border: "rgba(237,197,197,0.55)" });
  return tags;
}

// Step 4f: Risk level badge
function deriveRiskLevel(nm: number) {
  if (nm > 25) return { label: "Healthy",  icon: "✓", color: "#3d9068", bg: "rgba(90,175,132,0.10)",  border: "rgba(90,175,132,0.38)"  };
  if (nm >= 15) return { label: "Warning",  icon: "⚠", color: "#c28747", bg: "rgba(255,190,90,0.10)",  border: "rgba(236,208,169,0.55)" };
  return           { label: "Critical", icon: "✕", color: "#c16f6f", bg: "rgba(220,80,80,0.08)",   border: "rgba(237,197,197,0.60)" };
}

// Step 4g: Derive top delivery platform
function topDeliveryPlatform(channels: BusinessSetupChannel[]): { label: string; revShare: number; fee: number } {
  const delivery = channels.filter((c) => c.is_active && ["Grab Food","LINE MAN","Shopee Food"].includes(c.platform));
  if (!delivery.length) return { label: "delivery platform", revShare: 0, fee: 30 };
  return delivery.reduce((best, c) =>
    c.revenue_share_pct > best.revShare
      ? { label: c.platform, revShare: c.revenue_share_pct, fee: c.platform_fee_pct }
      : best,
    { label: delivery[0].platform, revShare: delivery[0].revenue_share_pct, fee: delivery[0].platform_fee_pct }
  );
}

// Step 4h: Generate 3 alert cards (critical / warning / opportunity)
function generateAlertCards(nm: number, profile: BusinessSetupProfile, channels: BusinessSetupChannel[]) {
  const deliveryRev = channels.filter((c) => c.is_active && ["Grab Food","LINE MAN","Shopee Food"].includes(c.platform))
    .reduce((s, c) => s + c.revenue_share_pct, 0);
  const walkinRev = channels.find((c) => c.platform === "Walk-in / Self-pickup")?.revenue_share_pct ?? 0;
  const hasLpg    = profile.food_types.some((ft) => LPG_FOOD_TYPES.has(ft));
  const top       = topDeliveryPlatform(channels);

  // Critical
  let critical;
  if (nm < 15) {
    const gpRecover = Math.round(top.fee * 10 / 100 * 10) / 10;
    critical = { type: "critical" as const, title: "Margin at Risk",
      problem: `Estimated net margin is ${nm.toFixed(1)}% — below the 15% safety threshold.`,
      reason:  "Platform GP fees and food cost are compressing profitability simultaneously.",
      action:  `Shift 10% from ${top.label} to Walk-in — at ${top.fee.toFixed(0)}% commission this recovers ~${gpRecover.toFixed(1)}% margin. (Scenario 3)` };
  } else if (deliveryRev >= 80) {
    const shiftTarget = Math.max(15, Math.round(deliveryRev - 65));
    const gpRecover   = Math.round(top.fee * shiftTarget / 100 * 10) / 10;
    critical = { type: "critical" as const, title: "Over-reliance on Delivery",
      problem: `${deliveryRev.toFixed(0)}% of your revenue flows through high-commission platforms.`,
      reason:  "Platform GP fees consume margin before ingredient costs are even counted.",
      action:  `Shift ${shiftTarget}% from ${top.label} to Walk-in — recovering ~${gpRecover.toFixed(1)}% of revenue currently lost to commission.` };
  } else {
    critical = { type: "critical" as const, title: "No Critical Risk Detected",
      problem: "Your current setup has no critical margin threats.",
      reason:  "Margin, channel mix, and cost structure are within acceptable ranges.",
      action:  "Continue monitoring diesel price and ingredient costs weekly via FFIA." };
  }

  // Warning
  let warning;
  if (hasLpg && nm < 20) {
    const lpgCount   = profile.food_types.filter((ft) => LPG_FOOD_TYPES.has(ft)).length;
    const repricePct = nm >= 17 ? 5 : 10;
    warning = { type: "warning" as const, title: "LPG Cost Exposure",
      problem: `Your menu has ${lpgCount} LPG-intensive dish type(s) and margin is ${nm.toFixed(1)}% — approaching pressure territory.`,
      reason:  "Stir fry, rice curry, and spicy soup are directly exposed to diesel price swings.",
      action:  `Reprice your top LPG items by ${repricePct}–${repricePct + 5}%, or bundle them with a low-COGS side to absorb cost increases. (Scenario 2)` };
  } else if (deliveryRev >= 60) {
    const overTarget = Math.max(10, Math.round(deliveryRev - 60));
    const feeRecover = Math.round(top.fee * overTarget / 100 * 10) / 10;
    warning = { type: "warning" as const, title: "GP Fee Pressure",
      problem: `Delivery platforms account for ${deliveryRev.toFixed(0)}% of revenue (target: below 60%).`,
      reason:  `${top.label} charges ${top.fee.toFixed(0)}% commission — reducing effective margin on every order.`,
      action:  `Promote self-pickup to shift ${overTarget}% off ${top.label} — this could recover ~${feeRecover.toFixed(1)}% in GP fees per month.` };
  } else {
    warning = { type: "warning" as const, title: "Monitor Ingredient Cost",
      problem: "Food cost is the largest variable affecting your margin.",
      reason:  "Market price swings for key ingredients can erode profitability quickly.",
      action:  "Review your top 5 ingredient prices monthly against Ministry of Commerce benchmarks." };
  }

  // Opportunity
  let opportunity;
  if (walkinRev < 20) {
    const shiftTo = Math.min(10, Math.max(5, Math.round(20 - walkinRev)));
    const gpSave  = Math.round(top.fee * shiftTo / 100 * 10) / 10;
    opportunity = { type: "opportunity" as const, title: "Self-Pickup Opportunity",
      problem: `Walk-in / Self-pickup is only ${walkinRev.toFixed(0)}% of revenue (potential: 20%+).`,
      reason:  "Direct orders have 0% platform fee — the highest margin per order available.",
      action:  `Offer a self-pickup discount to shift ${shiftTo}% from ${top.label} — saving ~${gpSave.toFixed(1)}% in GP fees on those orders.` };
  } else if (nm > 25 && profile.store_type !== "ghost_kitchen") {
    opportunity = { type: "opportunity" as const, title: "Margin Room to Grow",
      problem: `Healthy margin of ${nm.toFixed(1)}% gives room for a strategic promotion.`,
      reason:  "A margin buffer above 25% allows selective discounting without risk.",
      action:  "Run a flash sale on your 2–3 lowest-COGS items to drive order volume." };
  } else {
    opportunity = { type: "opportunity" as const, title: "Optimise Procurement Cycle",
      problem: "Frequent small purchases increase per-unit logistics cost.",
      reason:  "Daily procurement adds fuel and delivery surcharges to ingredient cost.",
      action:  "Switch to every-other-day procurement to reduce logistics overhead by ~10%." };
  }

  return [critical, warning, opportunity];
}

const ALERT_STYLES = {
  critical:    { typeLabel: "✕ Critical",    color: "#c16f6f", bg: "rgba(220,80,80,0.06)",    border: "rgba(237,197,197,0.7)", borderW: "2px"   },
  warning:     { typeLabel: "⚠ Warning",     color: "#c28747", bg: "rgba(255,190,90,0.07)",   border: "rgba(236,208,169,0.7)", borderW: "1.5px" },
  opportunity: { typeLabel: "✓ Opportunity", color: "#3d9068", bg: "rgba(90,175,132,0.07)",   border: "rgba(90,175,132,0.45)", borderW: "1px"   },
};

const ADVISOR_PROMPT = "จากโปรไฟล์ร้านและความเสี่ยงที่วิเคราะห์ไว้ ช่วยแนะนำ 3 สิ่งที่ควรแก้ก่อนเพื่อรักษากำไร";

interface Props {
  profile: BusinessSetupProfile;
  channels: BusinessSetupChannel[];
  onSave: () => void;
  onBack: () => void;
  saving: boolean;
  saved: boolean;
}

export default function RiskProfileStep({ profile, channels, onSave, onBack, saving, saved }: Props) {
  const nm      = computeNetMargin(channels, profile);
  const summary = buildAiSummary(profile, channels);
  const insight = buildFuelInsight(profile, nm);
  const risk    = deriveRiskLevel(nm);
  const tags    = deriveCapabilityTags(profile, channels);
  const alerts  = generateAlertCards(nm, profile, channels);

  const canSave = profile.restaurant_name.trim().length > 0 && profile.food_types.length > 0;

  return (
    <div>
      {/* Step 4i: Heading */}
      <p className="text-lg font-black text-slate-900">AI Risk Profile</p>
      <p className="mt-1 text-sm text-slate-500">
        Generated from your store setup, food types, and revenue channel mix.
      </p>

      {/* Step 4j: AI summary card */}
      <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          {/* Left: restaurant name + summary + fuel insight + capability tags */}
          <div className="flex-1 min-w-0">
            <p className="text-base font-black text-slate-900">
              {profile.restaurant_name || "Your Restaurant"}
            </p>
            <p className="mt-0.5 text-sm text-slate-500">{summary}</p>

            {/* Fuel insight badge */}
            <div className="mt-2 rounded-xl border border-blue-100 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 leading-snug">
              💡 {insight}
            </div>

            {/* Capability tags */}
            {tags.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {tags.map((tag) => (
                  <span
                    key={tag.label}
                    className="rounded-full px-2.5 py-0.5 text-[0.7rem] font-bold"
                    style={{ color: tag.color, background: tag.bg, border: `1px solid ${tag.border}` }}
                  >
                    {tag.label}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Right: risk level badge */}
          <div
            className="flex-shrink-0 rounded-2xl p-3 text-center min-w-[80px]"
            style={{ background: risk.bg, border: `1px solid ${risk.border}` }}
          >
            <p className="text-2xl font-black" style={{ color: risk.color }}>{risk.icon}</p>
            <p className="mt-0.5 text-[0.65rem] font-bold uppercase tracking-wider" style={{ color: risk.color }}>
              {risk.label}
            </p>
            <p className="mt-0.5 text-[0.6rem] text-slate-500">Est. {nm.toFixed(1)}% margin</p>
          </div>
        </div>
      </div>

      {/* Step 4k: Alert cards section header */}
      <div className="mt-5">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
          Risk & Opportunity Alerts
        </p>
        <p className="mt-0.5 text-xs text-slate-400">
          FFIA identified these based on your profile. Review and approve to save.
        </p>
      </div>

      {/* Step 4l: 3 alert cards */}
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {alerts.map((alert) => {
          const style = ALERT_STYLES[alert.type];
          return (
            <div
              key={alert.type}
              className="rounded-2xl p-4"
              style={{
                background: style.bg,
                border: `${style.borderW} solid ${style.border}`,
              }}
            >
              <p className="text-[0.65rem] font-bold uppercase tracking-wider" style={{ color: style.color }}>
                {style.typeLabel}
              </p>
              <p className="mt-1.5 text-sm font-black text-slate-900 leading-snug">{alert.title}</p>
              <p className="mt-2 text-xs text-slate-700 leading-relaxed">
                <strong>Problem:</strong> {alert.problem}
              </p>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                <strong>Why:</strong> {alert.reason}
              </p>
              <p className="mt-1 text-xs text-slate-700 leading-relaxed">
                <strong>Action:</strong> {alert.action}
              </p>
            </div>
          );
        })}
      </div>

      {/* Step 4m: Warning if required fields missing */}
      {!canSave && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-800">
          Some required fields are missing — please go back and complete Steps 1 and 2.
        </div>
      )}

      {/* Step 4n: Navigation */}
      <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-xl border border-orange-200 px-4 py-2.5 text-sm font-bold text-orange-700 hover:bg-orange-50"
        >
          ← Back
        </button>
        <div className="flex flex-col items-stretch gap-2 sm:items-end">
          <p className="max-w-xs text-xs font-semibold leading-5 text-slate-500 sm:text-right">
            {saved
              ? "บันทึกแล้ว ให้ FFIA Advisor ช่วยจัดลำดับสิ่งที่ควรแก้ก่อน"
              : "บันทึกข้อมูลร้านก่อน เพื่อให้ FFIA ใช้ข้อมูลล่าสุดในการวิเคราะห์"}
          </p>
          <div className="flex flex-wrap justify-end gap-2">
            {saved ? (
              <Link
                href={`/chat?prompt=${encodeURIComponent(ADVISOR_PROMPT)}`}
                className="rounded-xl border border-orange-200 bg-white px-4 py-2.5 text-sm font-black text-orange-700 transition hover:bg-orange-50"
              >
                ให้ FFIA Advisor วิเคราะห์ต่อ →
              </Link>
            ) : (
              <button
                type="button"
                onClick={onSave}
                disabled={!canSave || saving}
                className="rounded-xl bg-orange-600 px-6 py-2.5 text-sm font-black text-white transition hover:bg-orange-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {saving ? "Saving..." : "บันทึกโปรไฟล์ร้าน →"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
