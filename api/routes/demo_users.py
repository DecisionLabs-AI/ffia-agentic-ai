from fastapi import APIRouter

from api.schemas import DemoUsersResponse
from api.services.auth_service import get_demo_users

router = APIRouter()


@router.get("/demo-users", response_model=DemoUsersResponse)
def demo_users():
    return {"users": get_demo_users()}
