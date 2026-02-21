from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

api_router = APIRouter()


class StoryTurnRequest(BaseModel):
    action: str = Field(min_length=1)


@api_router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "chastease-api"}


@api_router.post("/story/turn")
def story_turn(payload: StoryTurnRequest) -> dict:
    action = payload.action.strip()
    if not action:
        raise HTTPException(status_code=400, detail="Field 'action' is required.")

    # Placeholder until AI service and world state are connected.
    return {
        "result": "accepted",
        "narration": f"Du versuchst: {action}",
        "next_state": "pending-ai-engine",
    }
