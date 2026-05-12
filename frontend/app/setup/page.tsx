"use client";

// Step 1: Business Setup wizard orchestrator — manages 5-step stepper state,
// loads/saves data, delegates rendering to step components.
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import BusinessProfileStep from "@/components/setup/BusinessProfileStep";
import StoreSetupStep from "@/components/setup/StoreSetupStep";
import ChannelMixStep from "@/components/setup/ChannelMixStep";
import InvoiceUploadStep from "@/components/setup/InvoiceUploadStep";
import RiskProfileStep from "@/components/setup/RiskProfileStep";
import {
  BusinessSetupChannel,
  BusinessSetupProfile,
  getBusinessSetup,
  saveBusinessSetup,
} from "@/lib/api";
import { getCurrentUser } from "@/lib/auth";
import { validateChannelMix } from "@/lib/businessSetupValidation";
import {
  BusinessSetupStep,
  isValidBusinessSetupStep,
  persistBusinessSetupStep,
  readBusinessSetupStep,
} from "@/lib/businessSetupStep";

// Step 2: Default channel values (shown when no saved data exists)
const DEFAULT_CHANNELS: BusinessSetupChannel[] = [
  { platform: "Grab Food",             revenue_share_pct: 40, platform_fee_pct: 28, is_active: true },
  { platform: "LINE MAN",              revenue_share_pct: 30, platform_fee_pct: 27, is_active: true },
  { platform: "Shopee Food",           revenue_share_pct: 20, platform_fee_pct: 22, is_active: true },
  { platform: "Walk-in / Self-pickup", revenue_share_pct: 10, platform_fee_pct: 0,  is_active: true },
];

const EMPTY_PROFILE: BusinessSetupProfile = {
  restaurant_name: "",
  business_type:   "restaurant",
  food_types:      [],
  store_type:      "ghost_kitchen",
  seat_range:      "0",
  currency:        "THB",
  target_margin_pct:  30,
  warning_margin_pct: 25,
  risk_margin_pct:    20,
};

// Step 3: Step labels for progress bar header
const STEPS = [
  { label: "Your Restaurant"    },
  { label: "Store Setup"        },
  { label: "Platform & Revenue" },
  { label: "Upload Cost Data"   },
  { label: "AI Risk Profile"    },
] as const;

const COMPLETED_SETUP_STEP: BusinessSetupStep = 5;

function readTargetStep(params: URLSearchParams): BusinessSetupStep | null {
  const rawStep = params.get("step");
  if (rawStep === "upload") return 4;
  const parsed = Number(rawStep);
  return isValidBusinessSetupStep(parsed) ? parsed : null;
}

export default function SetupPage() {
  const [userId,     setUserId    ] = useState("");
  const [step,       setStep      ] = useState<BusinessSetupStep>(1);
  const [profile,    setProfile   ] = useState<BusinessSetupProfile>(EMPTY_PROFILE);
  const [channelMix, setChannelMix] = useState<BusinessSetupChannel[]>(DEFAULT_CHANNELS);
  const [loading,    setLoading   ] = useState(true);
  const [saving,     setSaving    ] = useState(false);
  const [saveOk,     setSaveOk    ] = useState(false);
  const [loadError,  setLoadError ] = useState("");
  const [setupSaved, setSetupSaved] = useState(false);

  // Step 4: Load existing data on mount; honour ?step=upload deep-link
  useEffect(() => {
    const user = getCurrentUser();
    if (!user) { window.location.href = "/login"; return; }
    setUserId(user.user_id);

    const params = new URLSearchParams(window.location.search);
    const deepLinkedStep = readTargetStep(params);
    const restoredStep = readBusinessSetupStep(user.user_id);
    const initialStep = deepLinkedStep ?? restoredStep ?? 1;
    const shouldPreferCompletedStep = deepLinkedStep === null && restoredStep === 4;
    setStep(initialStep);

    (async () => {
      setLoading(true);
      setLoadError("");
      if (process.env.NODE_ENV === "development") {
        console.log("Loading business setup for user_id:", user.user_id);
      }
      try {
        const data = await getBusinessSetup(user.user_id);
        if (data.profile) {
          setProfile({ ...EMPTY_PROFILE, ...data.profile });
          setSetupSaved(true);
          if (shouldPreferCompletedStep) {
            setStep(COMPLETED_SETUP_STEP);
            persistBusinessSetupStep(user.user_id, COMPLETED_SETUP_STEP);
          }
        } else {
          setSetupSaved(false);
        }
        if (data.channel_mix?.length)  setChannelMix(data.channel_mix);
        if (data.error)                setLoadError(data.error);
      } catch {
        setLoadError("โหลดข้อมูล Business Setup ไม่สำเร็จ");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function goToStep(nextStep: BusinessSetupStep) {
    setSaveOk(false);
    setStep(nextStep);
    persistBusinessSetupStep(userId, nextStep);
  }

  // Step 5: Profile field updater
  function updateProfile<K extends keyof BusinessSetupProfile>(key: K, value: BusinessSetupProfile[K]) {
    setSaveOk(false);
    setLoadError("");
    setProfile((prev) => ({ ...prev, [key]: value }));
  }

  // Step 6: Channel field updater
  function updateChannel(index: number, patch: Partial<BusinessSetupChannel>) {
    setSaveOk(false);
    setLoadError("");
    setChannelMix((prev) => prev.map((ch, i) => (i === index ? { ...ch, ...patch } : ch)));
  }

  // Step 7: Cancel — return to overview
  function handleCancel() { window.location.href = "/"; }

  // Step 8: Save on final step
  async function handleSave() {
    if (!userId) return;
    const channelValidation = validateChannelMix(channelMix);
    if (!channelValidation.isValid) {
      setSaveOk(false);
      setLoadError(channelValidation.error || "Unable to save business setup.");
      return;
    }
    setSaving(true);
    setSaveOk(false);
    setLoadError("");
    try {
      const result = await saveBusinessSetup(userId, profile, channelMix);
      if (!result.ok) {
        setLoadError(result.error || "Unable to save business setup.");
        return;
      }
      // Step 8b: Reload fresh data after save
      const fresh = await getBusinessSetup(userId);
      if (fresh.profile)             setProfile({ ...EMPTY_PROFILE, ...fresh.profile });
      if (fresh.channel_mix?.length) setChannelMix(fresh.channel_mix);
      setSetupSaved(true);
      goToStep(COMPLETED_SETUP_STEP);
      setSaveOk(true);
    } catch {
      setLoadError("บันทึกข้อมูล Business Setup ไม่สำเร็จ");
    } finally {
      setSaving(false);
    }
  }

  // Step 9: Retry after load error
  function handleRetry() {
    setLoadError("");
    setLoading(true);
    getBusinessSetup(userId)
      .then((data) => {
        if (data.profile) {
          setProfile({ ...EMPTY_PROFILE, ...data.profile });
          setSetupSaved(true);
        } else {
          setSetupSaved(false);
        }
        if (data.channel_mix?.length) setChannelMix(data.channel_mix);
        if (data.error)               setLoadError(data.error);
      })
      .catch(() => setLoadError("โหลดข้อมูล Business Setup ไม่สำเร็จ"))
      .finally(() => setLoading(false));
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl">
        {/* Step 10: Page header */}
        <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-600">
          Business Setup
        </p>
        <h1 className="mt-1 text-3xl font-black text-slate-950">Business Setup</h1>
        <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
          Set up your restaurant profile and manage invoice cost data in one place.
        </p>

        {/* Step 11: Loading skeleton */}
        {loading ? (
          <div className="mt-8 rounded-2xl border border-orange-100 bg-white p-6 text-sm font-semibold text-slate-500 shadow-sm">
            กำลังโหลดข้อมูล Business Setup...
          </div>
        ) : (
          <div className="mt-6">
            {/* Step 12: Inline load error with retry */}
            {loadError && !saveOk && (
              <div className="mb-4 flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
                <span>{loadError}</span>
                <button
                  type="button"
                  onClick={handleRetry}
                  className="flex-shrink-0 rounded-lg border border-red-300 bg-white px-3 py-1 text-xs font-bold text-red-700 hover:bg-red-50"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Step 13: Save success banner */}
            {saveOk && (
              <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
                ✓ Business Setup saved successfully.
              </div>
            )}

            {/* Step 14: Stepper header — step labels + progress bar */}
            <div className="rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
              {/* Step badge */}
              <div className="mb-4 flex items-center gap-3 flex-wrap">
                {STEPS.map((s, i) => {
                  const n = i + 1;
                  const isDone    = n < step;
                  const isActive  = n === step;
                  return (
                    <div key={s.label} className="flex items-center gap-2">
                      <div
                        className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-[0.65rem] font-black transition-all ${
                          isDone   ? "bg-orange-600 text-white"
                          : isActive ? "bg-orange-600 text-white ring-4 ring-orange-100"
                          : "bg-slate-100 text-slate-400"
                        }`}
                      >
                        {isDone ? "✓" : n}
                      </div>
                      <span
                        className={`text-xs font-bold ${
                          isActive ? "text-orange-700" : isDone ? "text-slate-500" : "text-slate-300"
                        }`}
                      >
                        {s.label}
                      </span>
                      {i < STEPS.length - 1 && (
                        <div className={`ml-1 h-0.5 w-6 rounded-full transition-all ${isDone ? "bg-orange-400" : "bg-slate-100"}`} />
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Progress bar */}
              <div className="mb-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-orange-500 transition-all duration-300"
                  style={{ width: `${(step / 5) * 100}%` }}
                />
              </div>
              <p className="mb-5 text-xs font-bold text-slate-400">
                Step {step} of 5 — {STEPS[step - 1].label}
              </p>

              {/* Step 15: Active step renderer */}
              {step === 1 && (
                <BusinessProfileStep
                  profile={profile}
                  onUpdate={updateProfile}
                  onNext={() => goToStep(2)}
                  onCancel={handleCancel}
                />
              )}
              {step === 2 && (
                <StoreSetupStep
                  profile={profile}
                  onUpdate={updateProfile}
                  onNext={() => goToStep(3)}
                  onBack={() => goToStep(1)}
                  onCancel={handleCancel}
                />
              )}
              {step === 3 && (
                <ChannelMixStep
                  channels={channelMix}
                  profile={profile}
                  onUpdateChannel={updateChannel}
                  onNext={() => goToStep(4)}
                  onBack={() => goToStep(2)}
                  onCancel={handleCancel}
                />
              )}
              {step === 4 && (
                <InvoiceUploadStep
                  userId={userId}
                  onNext={() => goToStep(5)}
                  onBack={() => goToStep(3)}
                  onCancel={handleCancel}
                />
              )}
              {step === 5 && (
                <RiskProfileStep
                  profile={profile}
                  channels={channelMix}
                  onSave={handleSave}
                  onBack={() => goToStep(4)}
                  saving={saving}
                  saved={setupSaved}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
