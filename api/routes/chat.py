from fastapi import APIRouter

from api.schemas import SandboxChatRequest, SandboxChatResponse
from api.services.agent_service import ask_agent

router = APIRouter()


@router.post("/chat", response_model=SandboxChatResponse)
async def chat(body: SandboxChatRequest):
    return await ask_agent(
        message=body.message,
        user_id=body.user_id,
        history=[item.model_dump() for item in body.history],
    )
