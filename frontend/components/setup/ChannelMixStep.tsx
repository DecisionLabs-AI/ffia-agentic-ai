"use client";
// Step 3: Platform & Revenue — channel cards (2×2 grid) + blended margin preview
import Image from "next/image";
import type { BusinessSetupChannel, BusinessSetupProfile } from "@/lib/api";

// Step 3a: Channel metadata — logo path, whether platform fee is editable
const CHANNEL_META: {
  platform: string;
  logo: string;
  gpEditable: boolean;
}[] = [
  { platform: "Grab Food",             logo: "/channels/grab.png",       gpEditable: true  },
  { platform: "LINE MAN",              logo: "/channels/lineman.png",    gpEditable: true  },
  { platform: "Shopee Food",           logo: "/channels/shopeefood.png", gpEditable: true  },
  { platform: "Walk-in / Self-pickup", logo: "/channels/walkin.png",     gpEditable: false },
];

// Step 3b: COGS base midpoints per food type (from business_rules.md L4)
const FOOD_TYPE_COGS_BASE: Record<string, number> = {
  rice_curry:   0.375,
  noodle:       0.355,
  porridge:     0.355,
  chicken_rice: 0.375,
  spicy_soup:   0.375,
  stir_fry:     0.375,
  isaan:        0.375,
  spicy_salad:  0.355,
  healthy:      0.300,
  vegan:        0.300,
  meal_prep:    0.300,
};

function estimateFoodCostPct(foodTypes: string[]): number {
  if (!foodTypes.length) return 0.375;
  const bases = foodTypes.map((ft) => FOOD_TYPE_COGS_BASE[ft] ?? 0.375);
  return bases.reduce((a, b) => a + b, 0) / bases.length;
}

function estimateFixedCostPct(storeType: string, seatRange: string): number {
  if (storeType === "ghost_kitchen") return 0.15;
  if (storeType === "hybrid_small")  return 0.20;
  if (seatRange === "31_plus")       return 0.28;
  return 0.25;
}

// Step 3c: Compute blended margin preview from current channel + profile values
function computeBlendedMargin(
  channels: BusinessSetupChannel[],
  foodTypes: string[],
  storeType: string,
  seatRange: string
) {
  const activeChannels = channels.filter((c) => c.is_active);
  const totalRev = activeChannels.reduce((s, c) => s + c.revenue_share_pct, 0);
  const blendedGp =
    totalRev <= 0
      ? 0
      : activeChannels.reduce(
          (s, c) => s + (c.revenue_share_pct / totalRev) * (c.platform_fee_pct / 100),
          0
        );
  const foodCost  = estimateFoodCostPct(foodTypes);
  const fixedCost = estimateFixedCostPct(storeType, seatRange);
  const netMargin = 1 - blendedGp - foodCost - fixedCost;

  return {
    blendedGpPct:  Math.round(blendedGp  * 1000) / 10,
    foodCostPct:   Math.round(foodCost   * 1000) / 10,
    fixedCostPct:  Math.round(fixedCost  * 1000) / 10,
    netMarginPct:  Math.round(netMargin  * 1000) / 10,
  };
}

function numberValue(v: string): number {
  const p = Number(v);
  return Number.isFinite(p) ? p : 0;
}

interface Props {
  channels: BusinessSetupChannel[];
  profile: BusinessSetupProfile;
  onUpdateChannel: (index: number, patch: Partial<BusinessSetupChannel>) => void;
  onNext: () => void;
  onBack: () => void;
  onCancel: () => void;
}

export default function ChannelMixStep({
  channels,
  profile,
  onUpdateChannel,
  onNext,
  onBack,
  onCancel,
}: Props) {
  const activeChannels = channels.filter((c) => c.is_active);
  const totalRevShare  = activeChannels.reduce((s, c) => s + c.revenue_share_pct, 0);
  const revShareOk     = Math.abs(totalRevShare - 100) <= 0.5;

  const preview = computeBlendedMargin(
    channels,
    profile.food_types,
    profile.store_type,
    profile.seat_range
  );

  // Step 3d: Net margin status badge style
  const marginStatus =
    preview.netMarginPct > 25
      ? { label: "Good",    icon: "✓", color: "#3d9068", bg: "rgba(90,175,132,0.12)",  border: "rgba(90,175,132,0.35)"  }
      : preview.netMarginPct >= 15
      ? { label: "Warning", icon: "⚠", color: "#c28747", bg: "rgba(255,190,90,0.12)",  border: "rgba(236,208,169,0.5)"  }
      : { label: "Risk",    icon: "✕", color: "#c16f6f", bg: "rgba(255,90,90,0.10)",   border: "rgba(237,197,197,0.55)" };

  // Step 3e: Delivery revenue for insight line
  const deliveryRev = channels
    .filter((c) => c.is_active && ["Grab Food","LINE MAN","Shopee Food"].includes(c.platform))
    .reduce((s, c) => s + c.revenue_share_pct, 0);
  const walkinRev = channels.find((c) => c.platform === "Walk-in / Self-pickup")?.revenue_share_pct ?? 0;

  function channelInsight(): string {
    if (deliveryRev >= 70)
      return `💡 ${deliveryRev.toFixed(0)}% of your revenue depends on high-commission platforms. Consider promoting self-pickup.`;
    if (walkinRev > 0 && walkinRev < 20)
      return `💡 Increasing Walk-in / Self-pickup by 10% could meaningfully reduce your avg platform fee.`;
    return "💡 Your channel mix looks balanced across delivery and direct sales.";
  }

  // Step 3f: Validate before advancing
  function handleNext() {
    if (!activeChannels.length) return;
    if (!revShareOk) return;
    onNext();
  }

  const canAdvance = activeChannels.length > 0 && revShareOk;

  return (
    <div>
      {/* Step 3g: Step heading */}
      <p className="text-lg font-black text-slate-900">Platform & Revenue</p>
      <p className="mt-1 text-sm text-slate-500">
        Enable the channels you use, set each one&apos;s revenue share and platform fee.
        FFIA uses this to estimate your blended margin in real-time.
      </p>

      {/* Step 3h: 2×2 channel card grid */}
      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {CHANNEL_META.map((meta, i) => {
          const channelIndex = channels.findIndex((c) => c.platform === meta.platform);
          if (channelIndex === -1) return null;
          const ch = channels[channelIndex];
          const isWalkin = meta.platform === "Walk-in / Self-pickup";

          return (
            <div
              key={meta.platform}
              className={`rounded-2xl border p-4 transition-all ${
                ch.is_active
                  ? "border-orange-200 bg-white shadow-sm"
                  : "border-slate-100 bg-slate-50 opacity-60"
              }`}
            >
              {/* Step 3h-i: Card header — logo + name + active toggle */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <div className="relative h-7 w-16 flex-shrink-0">
                    <Image
                      src={meta.logo}
                      alt={meta.platform}
                      fill
                      className="object-contain object-left"
                      sizes="64px"
                    />
                  </div>
                  <span className="text-sm font-bold text-slate-800 leading-tight">
                    {meta.platform}
                  </span>
                  {isWalkin && (
                    <span className="rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[0.65rem] font-bold text-emerald-700">
                      No commission
                    </span>
                  )}
                </div>
                {/* Step 3h-ii: Active channel checkbox */}
                <label className="flex cursor-pointer items-center gap-1.5 text-xs font-bold text-slate-500 flex-shrink-0">
                  <input
                    type="checkbox"
                    checked={ch.is_active}
                    onChange={(e) => onUpdateChannel(channelIndex, { is_active: e.target.checked })}
                    className="h-4 w-4 rounded border-slate-300 accent-orange-600"
                  />
                  Active
                </label>
              </div>

              {/* Step 3h-iii: Inputs — only when active */}
              {ch.is_active && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[0.7rem] font-bold uppercase tracking-wide text-slate-500">
                      Revenue Share %
                    </label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={ch.revenue_share_pct}
                      onChange={(e) =>
                        onUpdateChannel(channelIndex, { revenue_share_pct: numberValue(e.target.value) })
                      }
                      className="mt-1 w-full rounded-xl border border-slate-200 px-2.5 py-2 text-sm font-bold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
                    />
                  </div>
                  <div>
                    <label className="block text-[0.7rem] font-bold uppercase tracking-wide text-slate-500">
                      Platform Fee %
                    </label>
                    {meta.gpEditable ? (
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={ch.platform_fee_pct}
                        onChange={(e) =>
                          onUpdateChannel(channelIndex, { platform_fee_pct: numberValue(e.target.value) })
                        }
                        className="mt-1 w-full rounded-xl border border-slate-200 px-2.5 py-2 text-sm font-bold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
                      />
                    ) : (
                      <div className="mt-1 rounded-xl border border-slate-100 bg-slate-50 px-2.5 py-2 text-sm font-bold text-slate-400">
                        0% — no commission
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Step 3i: Revenue share validation banner */}
      <div className="mt-4">
        {activeChannels.length === 0 ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-800">
            Enable at least one channel to continue.
          </div>
        ) : revShareOk ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm font-semibold text-emerald-800">
            ✓ Revenue shares total 100%
          </div>
        ) : (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-800">
            Enabled channels total <strong>{totalRevShare.toFixed(0)}%</strong> — must add up to 100%. Adjust the values above.
          </div>
        )}
      </div>

      {/* Step 3j: Blended margin preview card */}
      <div className="mt-4 rounded-2xl border border-orange-100 bg-white p-4 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-orange-600">
          Estimated Blended Margin Preview
        </p>
        <p className="mt-0.5 text-xs text-slate-500">
          Calculated from your enabled channels, food types, and store setup. Updates as you type.
        </p>

        {/* Step 3j-i: 4 metric tiles */}
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            { label: "Avg GP Cost",     value: `${preview.blendedGpPct.toFixed(1)}%`  },
            { label: "Est. Food Cost",  value: `${preview.foodCostPct.toFixed(1)}%`   },
            { label: "Est. Fixed Cost", value: `${preview.fixedCostPct.toFixed(1)}%`  },
            { label: "Est. Net Margin", value: `${preview.netMarginPct.toFixed(1)}%`  },
          ].map((m) => (
            <div key={m.label} className="rounded-xl border border-slate-100 bg-slate-50 p-2.5 text-center">
              <p className="text-[0.65rem] font-bold uppercase tracking-wide text-slate-500">{m.label}</p>
              <p className="mt-1 text-lg font-black text-slate-900">{m.value}</p>
            </div>
          ))}
        </div>

        {/* Step 3j-ii: Status badge */}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold"
            style={{ background: marginStatus.bg, border: `1px solid ${marginStatus.border}`, color: marginStatus.color }}
          >
            {marginStatus.icon} Margin status: {marginStatus.label}
          </span>
          <p className="text-xs text-slate-500">{channelInsight()}</p>
        </div>

        {/* Step 3j-iii: Scenario guidance */}
        {preview.netMarginPct < 15 && (
          <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">
            FFIA recommends an <strong>Operational Optimization</strong> strategy — switch to closer suppliers or promote self-pickup to reduce GP costs. (Scenario 3)
          </div>
        )}
        {preview.netMarginPct >= 15 && preview.netMarginPct < 20 && (
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
            FFIA suggests a <strong>Targeted Price Adjustment</strong> on your most fuel-impacted items. (Scenario 2)
          </div>
        )}
      </div>

      {/* Step 3k: Navigation */}
      <div className="mt-6 flex items-center justify-between">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-600 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onBack}
            className="rounded-xl border border-orange-200 px-4 py-2.5 text-sm font-bold text-orange-700 hover:bg-orange-50"
          >
            ← Back
          </button>
        </div>
        <button
          type="button"
          onClick={handleNext}
          disabled={!canAdvance}
          className="rounded-xl bg-orange-600 px-6 py-2.5 text-sm font-black text-white transition hover:bg-orange-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
