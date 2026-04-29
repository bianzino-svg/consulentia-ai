# FILE MAIN CON TELEGRAM NOTIFICA

from pathlib import Path
import requests

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from services.auth import (
    authenticate_access_code,
    request_access,
    get_user_by_id,
    init_db,
)

BASE_DIR = Path(__file__).resolve().parent

# 🔔 TELEGRAM CONFIG
BOT_TOKEN = "METTI_QUI_IL_TUO_TOKEN"
CHAT_ID = "419716347"

def send_telegram(msg):
    try:
        requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="secret")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

def current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(int(user_id))

@app.on_event("startup")
def startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/request-access", response_class=HTMLResponse)
def request_page(request: Request):
    return templates.TemplateResponse("request_access.html", {"request": request, "sent": False})

@app.post("/request-access", response_class=HTMLResponse)
def request_submit(request: Request, full_name: str = Form(...), email: str = Form(...)):
    request_access(full_name, email)

    # 🔔 NOTIFICA TELEGRAM
    send_telegram(f"🔔 Nuovo utente:\nNome: {full_name}\nEmail: {email}")

    return templates.TemplateResponse("request_access.html", {"request": request, "sent": True})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, email: str = Form(...), access_code: str = Form(...)):
    user = authenticate_access_code(email, access_code)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Errore login"})

    request.session["user_id"] = int(user["id"])
    return RedirectResponse("/app/dashboard", status_code=302)

@app.get("/app/dashboard")
def dashboard(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})
