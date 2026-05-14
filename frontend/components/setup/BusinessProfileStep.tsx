// Step 1: Your Restaurant — name + food type chips
import type { BusinessSetupProfile } from "@/lib/api";

const FOOD_OPTIONS = [
  { value: "rice_curry", label: "ข้าวแกง / ข้าวราดแกง" },
  { value: "noodle", label: "ก๋วยเตี๋ยว / ราเมน" },
  { value: "porridge", label: "โจ๊ก / ข้าวต้ม" },
  { value: "chicken_rice", label: "ข้าวมันไก่ / ข้าวขาหมู" },
  { value: "spicy_soup", label: "ต้มยำ / ต้มแซ่บ" },
  { value: "stir_fry", label: "ข้าวผัด / ผัดกะเพรา" },
  { value: "thai_grill", label: "ปิ้งย่าง / หมูกระทะ" },
  { value: "isaan", label: "ส้มตำ / อาหารอีสาน" },
  { value: "spicy_salad", label: "ยำ / อาหารรสจัด" },
  { value: "healthy", label: "อาหารสุขภาพ / สลัดบ็อกซ์" },
  { value: "vegan", label: "มังสวิรัติ / Vegan" },
  { value: "meal_prep", label: "ข้าวกล่อง / Meal Prep" },
];

interface Props {
  profile: BusinessSetupProfile;
  onUpdate: <K extends keyof BusinessSetupProfile>(key: K, value: BusinessSetupProfile[K]) => void;
  onNext: () => void;
  onCancel: () => void;
}

export default function BusinessProfileStep({ profile, onUpdate, onNext, onCancel }: Props) {
  // Step 1a: Toggle a food type chip on/off
  function toggleFoodType(value: string) {
    const exists = profile.food_types.includes(value);
    onUpdate(
      "food_types",
      exists ? profile.food_types.filter((f) => f !== value) : [...profile.food_types, value]
    );
  }

  // Step 1b: Validate required fields before advancing
  function handleNext() {
    if (!profile.restaurant_name.trim()) return;
    if (profile.food_types.length === 0) return;
    onNext();
  }

  const canAdvance = profile.restaurant_name.trim().length > 0 && profile.food_types.length > 0;

  return (
    <div>
      {/* Step 1c: Step heading */}
      <p className="text-lg font-black text-slate-900">Your Restaurant</p>
      <p className="mt-1 text-sm text-slate-500">
        Start with the basics — your restaurant name and the food you serve.
      </p>

      {/* Step 1d: Restaurant name input */}
      <div className="mt-5">
        <label className="block text-sm font-bold text-slate-700">
          Restaurant Name <span className="text-orange-500">*</span>
        </label>
        <input
          value={profile.restaurant_name}
          onChange={(e) => onUpdate("restaurant_name", e.target.value)}
          placeholder="e.g. My Restaurant"
          className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-semibold outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
        />
        {profile.restaurant_name.trim().length === 0 && (
          <p className="mt-1 text-xs text-orange-600">Please enter your restaurant name.</p>
        )}
      </div>

      {/* Step 1e: Food types chip selector */}
      <div className="mt-5">
        <label className="block text-sm font-bold text-slate-700">
          What does your restaurant sell? <span className="text-orange-500">*</span>
        </label>
        <p className="mt-0.5 text-xs text-slate-500">Select all that apply</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {FOOD_OPTIONS.map((opt) => {
            const selected = profile.food_types.includes(opt.value);
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggleFoodType(opt.value)}
                className={`rounded-full border px-3 py-1.5 text-xs font-bold transition-all ${
                  selected
                    ? "border-orange-600 bg-orange-600 text-white shadow-sm"
                    : "border-orange-200 bg-white text-orange-800 hover:bg-orange-50"
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
        {profile.food_types.length === 0 && (
          <p className="mt-2 text-xs text-orange-600">Please select at least one food type.</p>
        )}
      </div>

      {/* Step 1f: Navigation */}
      <div className="mt-8 flex items-center justify-between">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-600 hover:bg-slate-50"
        >
          Cancel
        </button>
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
