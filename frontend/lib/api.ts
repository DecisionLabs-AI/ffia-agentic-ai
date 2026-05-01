// Step 1: Base URL — reads from env var, falls back to local FastAPI.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8001";

if (process.env.NODE_ENV === "development") {
  console.log("FFIA API_BASE_URL:", API_BASE_URL);
}

function readTimeout(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

const DEFAULT_API_TIMEOUT_MS = readTimeout(
  process.env.NEXT_PUBLIC_API_TIMEOUT_MS,
  10000
);

const CHAT_API_TIMEOUT_MS = readTimeout(
  process.env.NEXT_PUBLIC_CHAT_TIMEOUT_MS,
  45000
);

// Step 4b: OCR calls invoke Gemini Vision — allow up to 90 s before surfacing a timeout error
const OCR_TIMEOUT_MS = 90_000;

type ApiFetchOptions = RequestInit & {
  timeoutMs?: number;
};

// Step 2: Token helpers — stored in localStorage
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ffia_token");
}

export function setToken(token: string): void {
  localStorage.setItem("ffia_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("ffia_token");
}

// Step 3: Generic typed fetch wrapper — attaches Bearer token automatically
async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const { timeoutMs = DEFAULT_API_TIMEOUT_MS, signal, ...fetchOptions } = options;
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const abortFromCaller = () => controller.abort();
  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", abortFromCaller, { once: true });
    }
  }

  try {
    if (process.env.NODE_ENV === "development" && path === "/chat") {
      console.log("Posting chat to:", `${API_BASE_URL}${path}`);
    }
    if (process.env.NODE_ENV === "development" && path === "/login") {
      console.log("Posting login to:", `${API_BASE_URL}${path}`);
    }

    const res = await fetch(`${API_BASE_URL}${path}`, {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });

    if (res.status === 401) {
      clearToken();
      if (typeof window !== "undefined") window.location.href = "/login";
      throw new Error("Unauthorized");
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? "API error");
    }

    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}

// Step 4: Multipart upload (no JSON Content-Type so browser sets boundary)
async function apiUpload<T>(
  path: string,
  formData: FormData,
  timeoutMs: number = DEFAULT_API_TIMEOUT_MS,
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers,
      body: formData,
      signal: controller.signal,
    });

    if (res.status === 401) {
      clearToken();
      if (typeof window !== "undefined") window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? "Upload error");
    }
    return res.json() as Promise<T>;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Upload timed out. Please try again.");
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginResponse {
  ok: boolean;
  user: DemoUser | null;
  error?: string | null;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function getMe(): Promise<{ user_id: string; display_name: string }> {
  return apiFetch("/auth/me");
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export interface InvoiceResponse {
  id: number;
  vendor: string;
  invoice_no: string;
  invoice_date: string;
  total_amount: number;
  created_at?: string;
  items?: InvoiceItem[];
}

export interface InvoiceItem {
  item_id?: number;
  item_name?: string;
  name: string;
  qty: number;
  unit_price: number;
  total: number;
  excluded_from_analysis?: boolean;
  excluded_reason?: string | null;
}

export interface DashboardSummary {
  invoice_item_count: number;
  latest_invoice: InvoiceResponse | null;
  diesel_price: Record<string, unknown>;
}

export interface TopItem {
  name: string;
  total_spend: number;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch("/dashboard/summary");
}

export async function getDashboardInvoices(): Promise<InvoiceResponse[]> {
  return apiFetch("/dashboard/invoices");
}

export async function getTopItems(limit = 5): Promise<TopItem[]> {
  return apiFetch(`/dashboard/top-items?limit=${limit}`);
}

export async function getDashboardChannels(): Promise<unknown[]> {
  return apiFetch("/dashboard/channels");
}

export interface OilPriceSnapshot {
  diesel: number | null;
  source: string;
  updated_at: string | null;
}

export interface ProfileSnapshot {
  restaurant_name: string | null;
  restaurant_type: string | null;
  store_type?: string | null;
  main_platform: string | null;
}

export interface ChannelMixItem {
  channel: string;
  revenue_share_pct: number;
  platform_fee_pct: number;
  is_active: boolean;
}

export interface TopSpendItem {
  item_name: string;
  amount: number;
}

export interface DashboardSnapshot {
  oil_price: OilPriceSnapshot;
  monthly_spend: number | null;
  invoice_count: number | null;
  items_tracked: number | null;
  profile: ProfileSnapshot;
  channel_mix: ChannelMixItem[];
  top_spend_items: TopSpendItem[];
  error?: string | null;
}

export async function getDashboardSnapshot(userId?: string): Promise<DashboardSnapshot> {
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return apiFetch(`/dashboard-summary${query}`);
}

// ── Upload ────────────────────────────────────────────────────────────────────

export interface OCRInvoiceResponse extends InvoiceResponse {
  saved_invoice_id: number | null;
  ocr_error: string;
}

// Step 4c: OCR preview — sandbox route (user_id as form field, no Bearer auth)
// Root cause note: sandbox login never issues a JWT, so Bearer-auth /upload/* routes
// always 401. These functions use the sandbox /invoices/* routes instead.
export interface OCRPreviewResponse {
  vendor: string;
  invoice_no: string;
  invoice_date: string;
  total_amount: number;
  items: InvoiceItem[];
  ocr_error: string;
}

export async function ocrInvoicePreview(file: File, userId: string): Promise<OCRPreviewResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("user_id", userId);
  return apiUpload<OCRPreviewResponse>("/invoices/ocr-preview", form, OCR_TIMEOUT_MS);
}

// Step 4d: Save reviewed invoice — sandbox route with user_id in body
export interface InvoiceSavePayload {
  vendor: string;
  invoice_no: string;
  invoice_date: string;
  total_amount: number;
  items: InvoiceItem[];
}

export interface SavedInvoiceResult {
  ok: boolean;
  invoice_id: number | null;
  invoice_no: string;
  item_count: number;
  total: number;
  error: string;
}

export async function saveInvoiceFromOCR(userId: string, payload: InvoiceSavePayload): Promise<SavedInvoiceResult> {
  return apiFetch<SavedInvoiceResult>("/invoices/save", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, ...payload }),
  });
}

// Step 4e: Current-month invoice list — sandbox route with user_id as query param
export async function getCurrentMonthInvoices(userId: string): Promise<InvoiceResponse[]> {
  return apiFetch<InvoiceResponse[]>(`/invoices/current-month?user_id=${encodeURIComponent(userId)}`);
}

// Step 4f: Line items for a specific invoice — sandbox route
function getInvoiceItemsForUploadPath(invoiceId: number, userId: string): string {
  return `/invoices/${invoiceId}/items?user_id=${encodeURIComponent(userId)}`;
}

export function getInvoiceItemsForUploadUrl(invoiceId: number, userId: string): string {
  return `${API_BASE_URL}${getInvoiceItemsForUploadPath(invoiceId, userId)}`;
}

export async function getInvoiceItemsForUpload(invoiceId: number, userId: string): Promise<InvoiceItem[]> {
  const items = await apiFetch<InvoiceItem[]>(getInvoiceItemsForUploadPath(invoiceId, userId));
  return items.map((item) => ({
    ...item,
    name: item.name || item.item_name || "",
  }));
}

// Step 4f-2: Soft-exclude or restore a saved invoice line item.
export async function toggleInvoiceItemExclusion(
  itemId: number,
  userId: string,
  excluded: boolean,
  reason?: string,
): Promise<InvoiceItem> {
  const result = await apiFetch<{ ok: boolean; error?: string; item?: InvoiceItem }>(
    `/invoices/items/${itemId}/exclude`,
    {
      method: "PATCH",
      body: JSON.stringify({ user_id: userId, excluded, reason }),
    },
  );
  if (!result.ok || !result.item) {
    throw new Error(result.error || "Unable to update line item.");
  }
  return {
    ...result.item,
    name: result.item.name || result.item.item_name || "",
  };
}

// Step 4g: Delete invoice — sandbox route; throws if backend signals failure
export async function deleteInvoice(id: number, userId: string): Promise<void> {
  const result = await apiFetch<{ ok: boolean; error?: string }>(
    `/invoices/${id}?user_id=${encodeURIComponent(userId)}`,
    { method: "DELETE" },
  );
  if (result && !result.ok) throw new Error(result.error || "Delete failed.");
}

// Step 4h: Legacy upload helpers — kept for backward compat but not used by the wizard
export async function uploadInvoice(file: File): Promise<OCRInvoiceResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiUpload<OCRInvoiceResponse>("/upload/invoice", form);
}

export async function listInvoices(limit = 10): Promise<InvoiceResponse[]> {
  return apiFetch(`/upload/invoices?limit=${limit}`);
}

// ── Profile ───────────────────────────────────────────────────────────────────

export interface ProfileData {
  restaurant_name?: string;
  business_type?: string;
  food_types?: string[];
  store_type?: string;
  seat_range?: string;
  currency?: string;
  target_margin_pct?: number;
  warning_margin_pct?: number;
  risk_margin_pct?: number;
}

export async function getProfile(): Promise<ProfileData> {
  return apiFetch("/profile/");
}

export async function saveProfile(data: ProfileData): Promise<void> {
  return apiFetch("/profile/", { method: "POST", body: JSON.stringify(data) });
}

export async function getChannels(): Promise<unknown[]> {
  return apiFetch("/profile/channels");
}

// ── Business Setup ───────────────────────────────────────────────────────────

export interface BusinessSetupProfile {
  restaurant_name: string;
  business_type: string;
  food_types: string[];
  store_type: string;
  seat_range: string;
  currency: string;
  target_margin_pct: number;
  warning_margin_pct: number;
  risk_margin_pct: number;
}

export interface BusinessSetupChannel {
  platform: string;
  revenue_share_pct: number;
  platform_fee_pct: number;
  is_active: boolean;
}

export interface BusinessSetupResponse {
  profile: BusinessSetupProfile | null;
  channel_mix: BusinessSetupChannel[];
  error: string | null;
}

export interface BusinessSetupSaveResponse {
  ok: boolean;
  error: string | null;
}

export async function getBusinessSetup(userId: string): Promise<BusinessSetupResponse> {
  return apiFetch(`/business-setup?user_id=${encodeURIComponent(userId)}`);
}

export async function saveBusinessSetup(
  userId: string,
  profile: BusinessSetupProfile,
  channelMix: BusinessSetupChannel[]
): Promise<BusinessSetupSaveResponse> {
  return apiFetch("/business-setup", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, profile, channel_mix: channelMix }),
  });
}

// ── Sandbox Demo Users ───────────────────────────────────────────────────────

export interface DemoUser {
  username: string;
  user_id: string;
  display_name?: string | null;
  restaurant_name?: string | null;
}

export async function getDemoUsers(): Promise<DemoUser[]> {
  const response = await apiFetch<{ users: DemoUser[] }>("/demo-users");
  return response.users;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "human" | "ai";
  content: string;
}

export interface ToolStep {
  tool: string;
  observation: string;
}

export interface ChatResponse {
  output: string;
  intermediate_steps: ToolStep[];
  error?: string;
}

export async function sendMessage(
  message: string,
  history: ChatMessage[],
  userId?: string
): Promise<ChatResponse> {
  const response = await apiFetch<{ answer: string; trace?: ToolStep[]; error?: string | null }>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, history, user_id: userId }),
    timeoutMs: CHAT_API_TIMEOUT_MS,
  });
  return {
    output: response.answer,
    intermediate_steps: response.trace ?? [],
    error: response.error ?? undefined,
  };
}
