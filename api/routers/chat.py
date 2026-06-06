# =============================================================================
# FFIA — api/routers/chat.py
# AI assistant chat endpoint.
# run_agent() is synchronous (LangGraph + Vertex AI) so it runs in a thread
# executor to avoid blocking the FastAPI event loop.
# =============================================================================

# Step 1: Imports
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.deps import get_current_user_id
from api.schemas import ChatRequest, ChatResponse, ToolStep
from api.services.agent_service import _INJECTION_REFUSAL, _is_prompt_injection
from api.services.runtime_errors import (
    GCP_BILLING_DISABLED_ANSWER,
    is_gcp_billing_disabled_error,
)

router = APIRouter()

# Step 2: Thread pool for blocking agent calls
_executor = ThreadPoolExecutor(max_workers=4)


# Step 3: POST /chat/message — synchronous agent call, returns full response
@router.post("/message", response_model=ChatResponse)
async def chat_message(
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    from agent.main import run_agent  # type: ignore[import]
    from langchain_core.messages import AIMessage, HumanMessage  # type: ignore[import]

    # Step 3a: Input guard — block prompt injection before reaching the agent
    if _is_prompt_injection(body.message):
        return ChatResponse(output=_INJECTION_REFUSAL, intermediate_steps=[])

    # Step 3b: Rebuild LangChain message history from plain dicts
    history = []
    for msg in body.history:
        if msg.role == "human":
            history.append(HumanMessage(content=msg.content))
        else:
            history.append(AIMessage(content=msg.content))

    # Step 3c: Run blocking agent in thread executor to free the event loop
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor,
            lambda: run_agent(
                user_message=body.message,
                chat_history=history,
                callbacks=[],
                current_user_id=user_id,
            ),
        )
    except Exception as exc:
        if not is_gcp_billing_disabled_error(exc):
            raise
        return ChatResponse(
            output=GCP_BILLING_DISABLED_ANSWER,
            intermediate_steps=[
                ToolStep(
                    tool="runtime",
                    observation="gcp_billing_disabled",
                )
            ],
        )

    # Step 3d: Normalize intermediate steps to schema
    steps = [
        ToolStep(tool=str(t), observation=str(o))
        for t, o in result.get("intermediate_steps", [])
    ]

    return ChatResponse(output=result.get("output", ""), intermediate_steps=steps)


# Step 4: GET /chat/stream?message=...&history=... — SSE streaming response
# Uses the same thread executor; sends the final answer as a single SSE event.
# Full token-by-token streaming requires LangChain callback integration (future work).
@router.get("/stream")
async def chat_stream(
    message: str,
    user_id: str = Depends(get_current_user_id),
):
    from agent.main import run_agent  # type: ignore[import]

    async def _generate():
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                _executor,
                lambda: run_agent(
                    user_message=message,
                    chat_history=[],
                    callbacks=[],
                    current_user_id=user_id,
                ),
            )
            output = result.get("output", "")
        except Exception as exc:
            if not is_gcp_billing_disabled_error(exc):
                raise
            output = GCP_BILLING_DISABLED_ANSWER
        # Step 4a: Emit as SSE — one data event per line of output
        for line in output.split("\n"):
            yield f"data: {line}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")
