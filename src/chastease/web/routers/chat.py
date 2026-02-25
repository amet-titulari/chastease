from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["web-chat"])

# Templates directory: src/chastease/templates
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


@router.get("/chat", response_class=HTMLResponse)
def chat_shell(request: Request):
    return templates.TemplateResponse(request, "chat.html")
