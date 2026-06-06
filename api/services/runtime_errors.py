"""Runtime exception classifiers shared by API adapters."""

from __future__ import annotations

from collections.abc import Iterator


GCP_BILLING_DISABLED_ERROR = "gcp_billing_disabled"
GCP_BILLING_DISABLED_ANSWER = (
    "ขออภัย ตอนนี้ FFIA เรียกใช้ Google Cloud/Vertex AI ไม่ได้ เพราะโปรเจกต์ GCP "
    "ยังไม่ได้เปิดหรือผูก Billing account กรุณาเปิด billing ให้โปรเจกต์ที่ deploy "
    "Cloud Run และตั้งค่า Vertex AI แล้วลองใหม่อีกครั้ง"
)

_BILLING_DISABLED_PATTERNS = (
    "billing is disabled",
    "billing disabled",
    "requires billing to be enabled",
    "enable billing",
    "billing account",
)


def _walk_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def is_gcp_billing_disabled_error(exc: BaseException) -> bool:
    """Return True when Google/Vertex reports disabled project billing."""
    for item in _walk_exception_chain(exc):
        text = " ".join(str(part) for part in item.args if part)
        if not text:
            text = str(item)
        lowered = text.lower()
        if any(pattern in lowered for pattern in _BILLING_DISABLED_PATTERNS):
            return True
    return False
