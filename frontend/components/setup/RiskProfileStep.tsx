// Step 4: AI Risk Profile — summary card, capability tags, alert cards, save
import Link from "next/link";
import type { BusinessSetupChannel, BusinessSetupProfile } from "@/lib/api";
import { validateChannelMix } from "@/lib/businessSetupValidation";

// Step 4a: LPG-intensive food types (from profile.py)
const LPG_FOOD_TYPES = new Set(["rice_curry", "stir_fry", "spicy_soup", "isaan", "chicken_rice", "thai_grill"]);

const FOOD_TYPE_COGS_BASE: Record<string, number> = {
  rice_curry: 0.375, noodle: 0.355, porridge: 0.355, chicken_rice: 0.375,
  spicy_soup: 0.375, stir_fry: 0.375, thai_grill: 0.375, isaan: 0.375, spicy_salad: 0.355,
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
    ghost_kitchen: "ร้านแบบ Ghost Kitchen",
    hybrid_small: "ร้านขนาดเล็กแบบ Hybrid",
    full_restaurant: "ร้านแบบ Full-Service",
  };
  const store = storeLabels[profile.store_type] ?? "ร้านอาหาร";
  const lpgCount = profile.food_types.filter((ft) => LPG_FOOD_TYPES.has(ft)).length;
  const menuTrait = profile.food_types.length > 0 && lpgCount >= profile.food_types.length / 2
    ? "มีเมนูไวต่อราคาพลังงาน" : "มีเมนูหลากหลาย";
  const deliveryRev = channels.filter((c) => c.is_active && ["Grab Food","LINE MAN","Shopee Food"].includes(c.platform))
    .reduce((s, c) => s + c.revenue_share_pct, 0);
  const channelTrait = deliveryRev >= 70 ? "พึ่งพาแพลตฟอร์มสูง"
    : deliveryRev >= 40 ? "มีรายได้ผสมระหว่างเดลิเวอรี่และหน้าร้าน" : "มีช่องทางขายตรงค่อนข้างแข็งแรง";
  return `${store} ที่${channelTrait} และ${menuTrait}`;
}

// Step 4d: Fuel sensitivity insight
function buildFuelInsight(profile: BusinessSetupProfile, nm: number): string {
  const total = Math.max(profile.food_types.length, 1);
  const lpgRatio = profile.food_types.filter((ft) => LPG_FOOD_TYPES.has(ft)).length / total;
  if (lpgRatio >= 0.6) {
    const suffix = nm < 18 ? " และ margin ตอนนี้ใกล้ระดับเสี่ยงแล้ว" : "";
    return `ดีเซลขึ้น ฿5/L อาจทำให้ margin ลดลงประมาณ ~3–5% เพราะเมนูส่วนใหญ่ใช้ LPG ในการปรุง${suffix}`;
  }
  if (lpgRatio >= 0.3) {
    const suffix = nm < 18 ? " และ margin ตอนนี้ใกล้ระดับเสี่ยงแล้ว" : "";
    return `ดีเซลขึ้น ฿5/L อาจทำให้ margin ลดลงประมาณ ~1–3% เพราะบางเมนูใช้พลังงานสูงในการปรุง${suffix}`;
  }
  return "ราคาดีเซลมีผลกระทบโดยตรงค่อนข้างจำกัดกับเมนูปัจจุบัน";
}

// Step 4e: Capability tags
function deriveCapabilityTags(profile: BusinessSetupProfile, channels: BusinessSetupChannel[]): { label: string; color: string; bg: string; border: string }[] {
  const tags: { label: string; color: string; bg: string; border: string }[] = [];
  const deliveryRev = channels.filter((c) => c.is_active && ["Grab Food","LINE MAN","Shopee Food"].includes(c.platform))
    .reduce((s, c) => s + c.revenue_share_pct, 0);
  const walkinRev = channels.find((c) => c.is_active && c.platform === "Walk-in / Self-pickup")?.revenue_share_pct ?? 0;
  if (profile.food_types.some((ft) => LPG_FOOD_TYPES.has(ft)))
    tags.push({ label: "ลดความเสี่ยง LPG",     color: "#5a87c9", bg: "rgba(89,135,201,0.10)",  border: "rgba(189,210,236,0.50)" });
  if (deliveryRev >= 60)
    tags.push({ label: "ปรับ GP/ช่องทางขาย",    color: "#c28747", bg: "rgba(255,190,90,0.10)",  border: "rgba(236,208,169,0.50)" });
  if (walkinRev < 20)
    tags.push({ label: "ปรับสัดส่วนช่องทางขาย", color: "#c16f6f", bg: "rgba(220,80,80,0.08)",   border: "rgba(237,197,197,0.55)" });
  return tags;
}

// Step 4f: Risk level badge
function deriveRiskLevel(nm: number) {
  if (nm > 25) return { label: "สุขภาพดี",  icon: "✓", color: "#3d9068", bg: "rgba(90,175,132,0.10)",  border: "rgba(90,175,132,0.38)"  };
  if (nm >= 15) return { label: "เตือน",  icon: "⚠", color: "#c28747", bg: "rgba(255,190,90,0.10)",  border: "rgba(236,208,169,0.55)" };
  return           { label: "วิกฤต", icon: "✕", color: "#c16f6f", bg: "rgba(220,80,80,0.08)",   border: "rgba(237,197,197,0.60)" };
}

// Step 4g: Derive top delivery platform
function topDeliveryPlatform(channels: BusinessSetupChannel[]): { label: string; revShare: number; fee: number } {
  const delivery = channels.filter((c) => c.is_active && ["Grab Food","LINE MAN","Shopee Food"].includes(c.platform));
  if (!delivery.length) return { label: "แพลตฟอร์มเดลิเวอรี่", revShare: 0, fee: 30 };
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
  const walkinRev = channels.find((c) => c.is_active && c.platform === "Walk-in / Self-pickup")?.revenue_share_pct ?? 0;
  const hasLpg    = profile.food_types.some((ft) => LPG_FOOD_TYPES.has(ft));
  const top       = topDeliveryPlatform(channels);

  // Critical
  let critical;
  if (nm < 15) {
    critical = { type: "critical" as const, title: "Margin อยู่ในระดับเสี่ยง",
      problem: `Margin ประมาณ ${nm.toFixed(1)}% ต่ำกว่าระดับปลอดภัย 15%`,
      reason:  "ค่า GP จากแพลตฟอร์มและต้นทุนอาหารกำลังกดกำไรพร้อมกัน",
      action:  `ค่อย ๆ ย้ายยอดขายบางส่วนจาก ${top.label} ไป Walk-in / Self-pickup เพื่อลดค่าคอมมิชชัน` };
  } else if (deliveryRev >= 80) {
    critical = { type: "critical" as const, title: "พึ่งพาเดลิเวอรี่สูงเกินไป",
      problem: `${deliveryRev.toFixed(0)}% ของรายได้มาจากแพลตฟอร์มที่มีค่าคอมมิชชันสูง`,
      reason:  "ค่า GP กิน margin ตั้งแต่ก่อนนับต้นทุนวัตถุดิบ",
      action:  `ค่อย ๆ ย้ายยอดขายบางส่วนจาก ${top.label} ไป Walk-in / Self-pickup เพื่อลดค่าคอมมิชชัน` };
  } else {
    critical = { type: "critical" as const, title: "ยังไม่พบความเสี่ยงวิกฤต",
      problem: "ข้อมูล setup ปัจจุบันยังไม่พบจุดที่เสี่ยงรุนแรงต่อ margin",
      reason:  "Margin ช่องทางขาย และโครงสร้างต้นทุนยังอยู่ในช่วงที่พอควบคุมได้",
      action:  "ติดตามราคาดีเซลและต้นทุนวัตถุดิบหลักทุกสัปดาห์ผ่าน FFIA" };
  }

  // Warning
  let warning;
  if (hasLpg && nm < 20) {
    warning = { type: "warning" as const, title: "ต้นทุน LPG กระทบกำไร",
      problem: `ร้านมีเมนูที่ใช้พลังงานสูง และ margin ตอนนี้อยู่ประมาณ ${nm.toFixed(1)}% ใกล้ระดับเสี่ยง`,
      reason:  "เมนูผัด ต้ม หรือซุป ได้รับผลกระทบจากราคาพลังงานมากกว่าเมนูทั่วไป",
      action:  "ปรับราคาเมนูที่ใช้พลังงานสูง 10–15% หรือจับคู่กับเมนูต้นทุนต่ำเพื่อช่วยพยุงกำไร" };
  } else if (deliveryRev >= 60) {
    warning = { type: "warning" as const, title: "ค่า GP กด margin",
      problem: `แพลตฟอร์มเดลิเวอรี่คิดเป็น ${deliveryRev.toFixed(0)}% ของรายได้ ซึ่งสูงกว่าเป้าหมายที่ควรต่ำกว่า 60%`,
      reason:  `${top.label} มีค่าคอมมิชชัน ${top.fee.toFixed(0)}% ทำให้ margin ต่อออเดอร์ลดลง`,
      action:  `ทำโปรรับเองเพื่อย้ายยอดบางส่วนจาก ${top.label} มายังช่องทางที่ไม่เสียค่าคอมมิชชัน` };
  } else {
    warning = { type: "warning" as const, title: "ติดตามต้นทุนวัตถุดิบ",
      problem: "ต้นทุนอาหารเป็นตัวแปรใหญ่ที่มีผลต่อ margin ของร้าน",
      reason:  "ราคาตลาดของวัตถุดิบหลักเปลี่ยนเร็วและอาจทำให้กำไรลดลง",
      action:  "ตรวจราคาวัตถุดิบหลัก 5 รายการทุกเดือนเทียบกับข้อมูลอ้างอิงที่เชื่อถือได้" };
  }

  // Opportunity
  let opportunity;
  if (walkinRev < 20) {
    opportunity = { type: "opportunity" as const, title: "เพิ่มช่องทางรับเอง",
      problem: `Walk-in / Self-pickup ยังเป็น ${walkinRev.toFixed(0)}% ของรายได้`,
      reason:  "ออเดอร์รับเองไม่มีค่า GP จึงเหลือ margin สูงกว่า",
      action:  `ทำโปรรับเอง เพื่อย้ายยอดบางส่วนจาก ${top.label} มายังช่องทางที่ไม่เสียค่าคอมมิชชัน` };
  } else if (nm > 25 && profile.store_type !== "ghost_kitchen") {
    opportunity = { type: "opportunity" as const, title: "มีพื้นที่ทำโปรโมชัน",
      problem: `Margin ประมาณ ${nm.toFixed(1)}% ยังมีพื้นที่ให้ทำโปรโมชันแบบเลือกเมนูได้`,
      reason:  "Margin ที่สูงกว่า 25% ทำให้ลดราคาเฉพาะเมนูได้โดยเสี่ยงน้อยกว่า",
      action:  "เลือกทำโปรกับ 2–3 เมนูที่ต้นทุนต่ำเพื่อเพิ่มยอดขาย" };
  } else {
    opportunity = { type: "opportunity" as const, title: "ปรับรอบซื้อวัตถุดิบ",
      problem: "การซื้อวัตถุดิบย่อยบ่อย ๆ ทำให้ต้นทุนขนส่งต่อหน่วยสูงขึ้น",
      reason:  "การซื้อรายวันเพิ่มค่าน้ำมันและค่าขนส่งเข้าไปในต้นทุนวัตถุดิบ",
      action:  "ลองรวมรอบซื้อเป็นวันเว้นวันเพื่อลดต้นทุนขนส่งโดยรวม" };
  }

  return [critical, warning, opportunity];
}

const ALERT_STYLES = {
  critical:    { typeLabel: "✕ วิกฤต",    color: "#c16f6f", bg: "rgba(220,80,80,0.06)",    border: "rgba(237,197,197,0.7)", borderW: "2px"   },
  warning:     { typeLabel: "⚠ เตือน",     color: "#c28747", bg: "rgba(255,190,90,0.07)",   border: "rgba(236,208,169,0.7)", borderW: "1.5px" },
  opportunity: { typeLabel: "✓ โอกาส", color: "#3d9068", bg: "rgba(90,175,132,0.07)",   border: "rgba(90,175,132,0.45)", borderW: "1px"   },
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
  const channelValidation = validateChannelMix(channels);

  const canSave =
    profile.restaurant_name.trim().length > 0 &&
    profile.food_types.length > 0 &&
    channelValidation.isValid;

  return (
    <div>
      {/* Step 4i: Heading */}
      <p className="text-lg font-black text-slate-900">AI Risk Profile</p>
      <p className="mt-1 text-sm text-slate-500">
        ประเมินเบื้องต้นจากข้อมูลร้าน ช่องทางขาย ค่า GP ประเภทอาหาร และกำไรประมาณการ ก่อนให้ FFIA Advisor วิเคราะห์เชิงลึกต่อ
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
            <p className="mt-0.5 text-[0.6rem] text-slate-500">Margin ประมาณ {nm.toFixed(1)}%</p>
          </div>
        </div>
      </div>

      {/* Step 4k: Alert cards section header */}
      <div className="mt-5">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
          ความเสี่ยงและโอกาสที่ FFIA พบ
        </p>
        <p className="mt-0.5 text-xs text-slate-400">
          คำนวณจากข้อมูล setup ล่าสุด เพื่อช่วยให้เห็นจุดที่ควรตรวจสอบก่อน
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
                <strong>ปัญหา:</strong> {alert.problem}
              </p>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                <strong>สาเหตุ:</strong> {alert.reason}
              </p>
              <p className="mt-1 text-xs text-slate-700 leading-relaxed">
                <strong>คำแนะนำ:</strong> {alert.action}
              </p>
            </div>
          );
        })}
      </div>

      {/* Step 4m: Warning if required fields missing */}
      {!canSave && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-800">
          {channelValidation.error || "ข้อมูลบางส่วนยังไม่ครบ กรุณากลับไปกรอก Step 1 และ 2 ให้ครบก่อน"}
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
              ? "บันทึกโปรไฟล์ร้านแล้ว ให้ FFIA Advisor ใช้ข้อมูลล่าสุดในการวิเคราะห์ได้เลย"
              : "บันทึกข้อมูลร้านก่อน เพื่อให้ FFIA ใช้ข้อมูลล่าสุดในการวิเคราะห์"}
          </p>
          <div className="flex flex-wrap justify-end gap-2">
            {saved ? (
              <>
                <button
                  type="button"
                  onClick={onSave}
                  disabled={!canSave || saving}
                  className="rounded-xl border border-orange-200 bg-white px-4 py-2.5 text-sm font-black text-orange-700 transition hover:bg-orange-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {saving ? "Saving..." : "อัปเดตโปรไฟล์ร้าน"}
                </button>
                <Link
                  href={`/chat?prompt=${encodeURIComponent(ADVISOR_PROMPT)}`}
                  className="rounded-xl bg-orange-600 px-6 py-2.5 text-sm font-black text-white transition hover:bg-orange-700"
                >
                  ให้ FFIA Advisor วิเคราะห์ต่อ →
                </Link>
              </>
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
