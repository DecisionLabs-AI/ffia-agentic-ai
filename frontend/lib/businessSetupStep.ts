export type BusinessSetupStep = 1 | 2 | 3 | 4 | 5;

const BUSINESS_SETUP_STEP_FALLBACK_KEY = "ffia_business_setup_step";

export function businessSetupStepKey(userId?: string): string {
  return userId ? `ffia_business_setup_step_${userId}` : BUSINESS_SETUP_STEP_FALLBACK_KEY;
}

export function isValidBusinessSetupStep(value: number): value is BusinessSetupStep {
  return Number.isInteger(value) && value >= 1 && value <= 5;
}

export function readBusinessSetupStep(userId?: string): BusinessSetupStep | null {
  if (typeof window === "undefined") return null;
  const parsed = Number(localStorage.getItem(businessSetupStepKey(userId)));
  return isValidBusinessSetupStep(parsed) ? parsed : null;
}

export function persistBusinessSetupStep(userId: string | undefined, nextStep: number): void {
  if (typeof window === "undefined" || !isValidBusinessSetupStep(nextStep)) return;
  localStorage.setItem(businessSetupStepKey(userId), String(nextStep));
}
