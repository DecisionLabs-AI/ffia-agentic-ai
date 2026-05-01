// Step 2: Store Setup — store type + conditional seat range
import type { BusinessSetupProfile } from "@/lib/api";

const STORE_OPTIONS = [
  { value: "ghost_kitchen", label: "Ghost Kitchen (Delivery Only)" },
  { value: "hybrid_small", label: "Hybrid Small (Dine-in + Delivery)" },
  { value: "full_restaurant", label: "Full Restaurant (Dine-in Focus)" },
];

const SEAT_LABELS: Record<string, string> = {
  "0":       "ไม่มีที่นั่ง (Delivery Only)",
  "1_10":    "1–10 ที่นั่ง (ร้านขนาดเล็ก)",
  "11_30":   "11–30 ที่นั่ง (ร้านขนาดกลาง)",
  "31_plus": "มากกว่า 30 ที่นั่ง (ร้านขนาดใหญ่)",
};

// Step 2a: Valid seat ranges per store type (matches original profile.py logic)
const SEAT_FOR_STORE: Record<string, string[]> = {
  ghost_kitchen:   ["0"],
  hybrid_small:    ["1_10"],
  full_restaurant: ["11_30", "31_plus"],
};

interface Props {
  profile: BusinessSetupProfile;
  onUpdate: <K extends keyof BusinessSetupProfile>(key: K, value: BusinessSetupProfile[K]) => void;
  onNext: () => void;
  onBack: () => void;
  onCancel: () => void;
}

export default function StoreSetupStep({ profile, onUpdate, onNext, onBack, onCancel }: Props) {
  const validSeats = SEAT_FOR_STORE[profile.store_type] ?? ["0"];

  // Step 2b: When store type changes, reset seat_range to first valid option
  function handleStoreTypeChange(newStoreType: string) {
    onUpdate("store_type", newStoreType);
    const firstValid = SEAT_FOR_STORE[newStoreType]?.[0] ?? "0";
    onUpdate("seat_range", firstValid);
  }

  // Step 2c: Validate seat_range is valid for the current store_type before advancing
  function handleNext() {
    const seats = SEAT_FOR_STORE[profile.store_type] ?? ["0"];
    const validSeat = seats.includes(profile.seat_range) ? profile.seat_range : seats[0];
    if (validSeat !== profile.seat_range) onUpdate("seat_range", validSeat);
    onNext();
  }

  return (
    <div>
      {/* Step 2d: Step heading */}
      <p className="text-lg font-black text-slate-900">Store Setup</p>
      <p className="mt-1 text-sm text-slate-500">Tell us how your restaurant operates.</p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {/* Step 2e: Store type select */}
        <div>
          <label className="block text-sm font-bold text-slate-700">Store Type</label>
          <select
            value={profile.store_type}
            onChange={(e) => handleStoreTypeChange(e.target.value)}
            className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
          >
            {STORE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* Step 2f: Seat range — hidden for ghost_kitchen, read-only if single option */}
        {profile.store_type !== "ghost_kitchen" && (
          <div>
            <label className="block text-sm font-bold text-slate-700">Seat Range</label>
            {validSeats.length === 1 ? (
              <div className="mt-2 w-full rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5 text-sm font-semibold text-slate-500">
                {SEAT_LABELS[validSeats[0]] ?? validSeats[0]}
              </div>
            ) : (
              <select
                value={validSeats.includes(profile.seat_range) ? profile.seat_range : validSeats[0]}
                onChange={(e) => onUpdate("seat_range", e.target.value)}
                className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
              >
                {validSeats.map((v) => (
                  <option key={v} value={v}>{SEAT_LABELS[v] ?? v}</option>
                ))}
              </select>
            )}
          </div>
        )}

        {/* Step 2g: Ghost kitchen — show informational badge instead */}
        {profile.store_type === "ghost_kitchen" && (
          <div className="flex items-end pb-0.5">
            <div className="rounded-xl border border-blue-100 bg-blue-50 px-3 py-2.5 text-xs font-bold text-blue-700 w-full">
              Delivery Only — no dine-in seats
            </div>
          </div>
        )}
      </div>

      {/* Step 2h: Navigation */}
      <div className="mt-8 flex items-center justify-between">
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
          className="rounded-xl bg-orange-600 px-6 py-2.5 text-sm font-black text-white transition hover:bg-orange-700"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
