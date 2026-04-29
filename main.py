from pathlib import Path
import requests

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from services.auth import (
    authenticate_user,
    authenticate_access_code,
    create_user,
    request_access,
    get_user_by_id,
    init_db,
    list_reports_for_user,
    get_all_users,
    count_reports_for_user,
    set_user_premium,
    set_user_active,
    regenerate_access_code,
    is_user_premium,
)
from services.dashboard_service import get_dashboard_bundle, generate_user_report

BASE_DIR = Path(__file__).resolve().parent
FREE_REPORT_LIMIT = 3
ADMIN_EMAIL = "info@bianzino.it"
ADMIN_PASSWORD = "alessio00"

# 🔔 TELEGRAM CONFIG
BOT_TOKEN = "8680952100:AAGLaefu2bIaNkjT0MiYijVD7r-kvdXhgto"
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

app = FastAPI(title="ConsulentIA AI")
app.add_middleware(
    SessionMiddleware,
    secret_key="consulentia-ai-secure-session-key-change-later",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

def current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(int(user_id))

def require_user(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return user

def is_admin_session(request: Request) -> bool:
    return bool(request.session.get("is_admin"))

def is_admin_user(user) -> bool:
    if not user:
        return False
    return str(user["email"]).strip().lower() == ADMIN_EMAIL.strip().lower()

def has_admin_access(request: Request) -> bool:
    return is_admin_session(request) or is_admin_user(current_user(request))

def is_limited_free_user(user) -> bool:
    if not user:
        return False
    user_id = int(user["id"])
    if is_admin_user(user):
        return False
    if is_user_premium(user_id):
        return False
    return count_reports_for_user(user_id) >= FREE_REPORT_LIMIT

def render_limit_page(request: Request, user):
    return templates.TemplateResponse(request, "limit.html", {"request": request, "user": user})

@app.on_event("startup")
def startup() -> None:
    init_db()

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(request, "landing.html", {"request": request, "user": current_user(request)})

@app.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request):
    return templates.TemplateResponse(request, "pricing.html", {"request": request, "user": current_user(request)})

@app.get("/request-access", response_class=HTMLResponse)
def request_access_page(request: Request):
    return templates.TemplateResponse(request, "request_access.html", {"request": request, "user": current_user(request), "sent": False})

@app.post("/request-access", response_class=HTMLResponse)
def request_access_submit(request: Request, full_name: str = Form(...), email: str = Form(...)):
    request_access(full_name, email)

    # 🔔 NOTIFICA TELEGRAM
    send_telegram(f"🔔 Nuova richiesta accesso:\nNome: {full_name}\nEmail: {email}")

    return templates.TemplateResponse(request, "request_access.html", {"request": request, "user": current_user(request), "sent": True})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None, "user": current_user(request)})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), access_code: str = Form(...)):
    user = authenticate_access_code(email, access_code)
    if not user:
        return templates.TemplateResponse(request, "login.html", {"request": request, "error": "Email o codice accesso non validi.", "user": None})
    request.session.clear()
    request.session["user_id"] = int(user["id"])
    return RedirectResponse("/app/dashboard", status_code=302)

@app.get("/admin-login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {"request": request, "error": None, "user": current_user(request)})

@app.post("/admin-login", response_class=HTMLResponse)
def admin_login(request: Request, email: str = Form(...), password: str = Form(...)):
    if email.strip().lower() != ADMIN_EMAIL.strip().lower() or password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin_login.html", {"request": request, "error": "Accesso admin non valido.", "user": None})
    request.session.clear()
    request.session["is_admin"] = True
    return RedirectResponse("/admin/users-page", status_code=302)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return RedirectResponse("/request-access", status_code=302)

@app.post("/register", response_class=HTMLResponse)
def register(request: Request, full_name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    user_id = create_user(full_name, email, password)
    if user_id is None:
        return RedirectResponse("/request-access", status_code=302)
    request.session.clear()
    request.session["user_id"] = int(user_id)
    return RedirectResponse("/app/dashboard", status_code=302)

@app.get("/app/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, profile: str = "bilanciato"):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    bundle = get_dashboard_bundle(profile)
    return templates.TemplateResponse(request, "dashboard.html", {"request": request, "user": user, "profile": profile, "bundle": bundle, "page": "dashboard", "is_limited": is_limited_free_user(user)})

@app.get("/app/fractals", response_class=HTMLResponse)
def fractals(request: Request, profile: str = "bilanciato"):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if is_limited_free_user(user):
        return render_limit_page(request, user)
    bundle = get_dashboard_bundle(profile)
    return templates.TemplateResponse(request, "fractals.html", {"request": request, "user": user, "profile": profile, "bundle": bundle, "page": "fractals"})

@app.get("/app/macro", response_class=HTMLResponse)
def macro(request: Request, profile: str = "bilanciato"):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if is_limited_free_user(user):
        return render_limit_page(request, user)
    bundle = get_dashboard_bundle(profile)
    return templates.TemplateResponse(request, "macro.html", {"request": request, "user": user, "profile": profile, "bundle": bundle, "page": "macro"})

@app.get("/app/allocation", response_class=HTMLResponse)
def allocation(request: Request, profile: str = "bilanciato"):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if is_limited_free_user(user):
        return render_limit_page(request, user)
    bundle = get_dashboard_bundle(profile)
    return templates.TemplateResponse(request, "allocation.html", {"request": request, "user": user, "profile": profile, "bundle": bundle, "page": "allocation"})

@app.get("/app/reports", response_class=HTMLResponse)
def reports(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    report_rows = list_reports_for_user(int(user["id"]))
    return templates.TemplateResponse(request, "reports.html", {"request": request, "user": user, "reports": report_rows, "page": "reports", "is_limited": is_limited_free_user(user)})

@app.post("/app/generate-report")
def create_report(request: Request, profile: str = Form(...)):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if is_limited_free_user(user):
        return render_limit_page(request, user)
    generate_user_report(int(user["id"]), profile)
    return RedirectResponse("/app/reports", status_code=302)

@app.get("/admin/users")
def admin_users_json(request: Request):
    if not has_admin_access(request):
        return RedirectResponse("/", status_code=302)
    return get_all_users()

@app.get("/admin/users-page", response_class=HTMLResponse)
def admin_users_page(request: Request):
    if not has_admin_access(request):
        return RedirectResponse("/", status_code=302)
    users = get_all_users()
    return templates.TemplateResponse(request, "admin_users.html", {"request": request, "user": current_user(request), "users": users, "page": "admin"})

@app.post("/admin/users/{user_id}/premium")
def admin_set_premium(request: Request, user_id: int, value: int = Form(...)):
    if not has_admin_access(request):
        return RedirectResponse("/", status_code=302)
    set_user_premium(user_id, value)
    return RedirectResponse("/admin/users-page", status_code=302)

@app.post("/admin/users/{user_id}/active")
def admin_set_active(request: Request, user_id: int, value: int = Form(...)):
    if not has_admin_access(request):
        return RedirectResponse("/", status_code=302)
    set_user_active(user_id, value)
    return RedirectResponse("/admin/users-page", status_code=302)

@app.post("/admin/users/{user_id}/regenerate-code")
def admin_regenerate_code(request: Request, user_id: int):
    if not has_admin_access(request):
        return RedirectResponse("/", status_code=302)
    regenerate_access_code(user_id)
    return RedirectResponse("/admin/users-page", status_code=302)

@app.get("/download")
def download_file(request: Request, path: str):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return RedirectResponse("/app/reports", status_code=302)
    return FileResponse(str(file_path), filename=file_path.name)
