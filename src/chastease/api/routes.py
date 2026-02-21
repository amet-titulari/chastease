from flask import Blueprint, jsonify, request

api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health() -> tuple[dict, int]:
    return {"status": "ok", "service": "chastease-api"}, 200


@api_bp.post("/story/turn")
def story_turn() -> tuple[dict, int]:
    payload = request.get_json(silent=True) or {}
    action = payload.get("action", "").strip()
    if not action:
        return {"error": "Field 'action' is required."}, 400

    # Placeholder until AI service and world state are connected.
    return (
        jsonify(
            {
                "result": "accepted",
                "narration": f"Du versuchst: {action}",
                "next_state": "pending-ai-engine",
            }
        ),
        200,
    )
