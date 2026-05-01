from fastapi import APIRouter

from api.schemas import SandboxLoginRequest, SandboxLoginResponse
from api.services.auth_service import authenticate_demo_user

router = APIRouter()


@router.post("/login", response_model=SandboxLoginResponse)
def login(body: SandboxLoginRequest):
    user = authenticate_demo_user(body.username, body.password)
    if not user:
        return {"ok": False, "user": None, "error": "Invalid username or password"}
    return {"ok": True, "user": user, "error": None}
