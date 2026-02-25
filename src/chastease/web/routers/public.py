from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["web-public"])

# Templates directory: src/chastease/templates
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/contract", response_class=HTMLResponse)
def contract_shell(request: Request):
    return templates.TemplateResponse("contract.html", {"request": request})

