# =============================================================================
# FFIA — api/schemas.py
# Pydantic request and response models for all API routers.
# =============================================================================

from __future__ import annotations
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Auth ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    display_name: str


class MeResponse(BaseModel):
    user_id: str
    display_name: str


# ── Invoice / Upload ─────────────────────────────────────────────────────────

class InvoiceItem(BaseModel):
    item_id: int | None = None
    item_name: str | None = None
    name: str
    qty: float
    unit_price: float
    total: float
    excluded_from_analysis: bool = False
    excluded_reason: str | None = None


class InvoiceResponse(BaseModel):
    id: int
    vendor: str
    invoice_no: str
    invoice_date: str
    total_amount: float
    created_at: datetime | None = None
    items: list[InvoiceItem] = Field(default_factory=list)


class OCRInvoiceResponse(BaseModel):
    vendor: str
    invoice_no: str
    invoice_date: str
    total_amount: float
    items: list[InvoiceItem] = Field(default_factory=list)
    saved_invoice_id: int | None = None
    ocr_error: str = ""


class InvoiceSaveRequest(BaseModel):
    vendor: str
    invoice_no: str
    invoice_date: str
    total_amount: float
    items: list[InvoiceItem] = Field(default_factory=list)


class SavedInvoiceResponse(BaseModel):
    ok: bool
    invoice_id: int | None = None
    invoice_no: str = ""
    item_count: int = 0
    total: float = 0.0
    error: str = ""


# ── Dashboard ────────────────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    invoice_item_count: int
    latest_invoice: InvoiceResponse | None = None
    diesel_price: dict[str, Any] = Field(default_factory=dict)


class TopItem(BaseModel):
    name: str
    total_spend: float


# ── Profile ──────────────────────────────────────────────────────────────────

class ChannelIn(BaseModel):
    label: str
    revenue_share_pct: float
    gp_pct: float
    enabled: bool


class ProfileUpsertRequest(BaseModel):
    restaurant_name: str
    business_type: str
    food_types: list[str]
    store_type: str
    seat_range: str
    currency: str = "THB"
    target_margin_pct: float
    warning_margin_pct: float
    risk_margin_pct: float
    channels: dict[str, ChannelIn] | None = None


class ChannelResponse(BaseModel):
    platform: str
    revenue_share_pct: float
    platform_fee_pct: float
    is_active: bool


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str            # "human" or "ai"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class ToolStep(BaseModel):
    tool: str
    observation: str


class ChatResponse(BaseModel):
    output: str
    intermediate_steps: list[ToolStep] = Field(default_factory=list)


# ── Sandbox Next.js Migration API ─────────────────────────────────────────────

class SandboxChatRequest(BaseModel):
    message: str
    user_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class SandboxChatResponse(BaseModel):
    answer: str
    trace: list[ToolStep] = Field(default_factory=list)
    error: str | None = None


class DemoUser(BaseModel):
    username: str
    user_id: str
    display_name: str | None = None
    restaurant_name: str | None = None


class DemoUsersResponse(BaseModel):
    users: list[DemoUser] = Field(default_factory=list)


class SandboxLoginRequest(BaseModel):
    username: str
    password: str


class SandboxLoginResponse(BaseModel):
    ok: bool
    user: DemoUser | None = None
    error: str | None = None


class OilPriceSnapshot(BaseModel):
    diesel: float | None = None
    source: str
    updated_at: str | None = None


class ProfileSnapshot(BaseModel):
    restaurant_name: str | None = None
    restaurant_type: str | None = None
    store_type: str | None = None
    main_platform: str | None = None


class ChannelMixItem(BaseModel):
    channel: str
    revenue_share_pct: float
    platform_fee_pct: float
    is_active: bool


class TopSpendItem(BaseModel):
    item_name: str
    amount: float


class DashboardSnapshot(BaseModel):
    oil_price: OilPriceSnapshot
    monthly_spend: float | None = None
    invoice_count: int | None = None
    items_tracked: int | None = None
    profile: ProfileSnapshot
    channel_mix: list[ChannelMixItem] = Field(default_factory=list)
    top_spend_items: list[TopSpendItem] = Field(default_factory=list)
    error: str | None = None
