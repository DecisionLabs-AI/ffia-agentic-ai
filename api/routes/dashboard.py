from fastapi import APIRouter

from api.schemas import DashboardSnapshot
from api.services.dashboard_service import get_dashboard_summary

router = APIRouter()


@router.get("/dashboard-summary", response_model=DashboardSnapshot)
def dashboard_summary(user_id: str | None = None):
    return get_dashboard_summary(user_id)
