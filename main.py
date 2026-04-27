import random
from services.email_service import send_otp_email
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from services.auth import (
    authenticate_user,
    create_user,
    get_user_by_id,
    init_db,
    list_reports_for_user,
    get_all_users,
    count_reports_for_user,
    set_user_premium,
    is_user_premium,
)
from services.dashboard_service import get_dashboard_bundle, generate_user_report
otp_storage = {}
BASE_DIR = Path(__file__).resolve().parent
FREE_REPORT_LIMIT = 3
ADMIN_EMAIL = "info@bianzino.it"

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


def is_admin_user(user) -> bool:
    if not user:
        return False
    return str(user["email"]).strip().lower() == ADMIN_EMAIL.strip().lower()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(
        request,
        "landing.html",
        {"request": request, "user": current_user(request)},
    )


@app.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request):
    return templates.TemplateResponse(
        request,
        "pricing.html",
        {"request": request, "user": current_user(request)},
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if current_user(request):
        return RedirectResponse("/app/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "register.html",
        {"request": request, "error": None, "user": None},
    )


@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if len(password) < 6:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "request": request,
                "error": "La password deve avere almeno 6 caratteri.",
                "user": None,
            },
        )

    user_id = create_user(full_name, email, password)
    if user_id is None:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "request": request,
                "error": "Esiste già un account con questa email.",
                "user": None,
            },
        )

    request.session.clear()
    request.session["user_id"] = int(user_id)
    return RedirectResponse("/app/dashboard", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/app/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "error": None, "user": None},
    )


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = authenticate_user(email, password)
    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "Credenziali non valide.", "user": None},
        )

    request.session.clear()
    request.session["user_id"] = int(user["id"])
    return RedirectResponse("/app/dashboard", status_code=302)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


@app.get("/app/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, profile: str = "bilanciato"):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    bundle = get_dashboard_bundle(profile)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "bundle": bundle,
            "page": "dashboard",
        },
    )


@app.get("/app/fractals", response_class=HTMLResponse)
def fractals(request: Request, profile: str = "bilanciato"):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    bundle = get_dashboard_bundle(profile)
    return templates.TemplateResponse(
        request,
        "fractals.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "bundle": bundle,
            "page": "fractals",
        },
    )


@app.get("/app/macro", response_class=HTMLResponse)
def macro(request: Request, profile: str = "bilanciato"):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    bundle = get_dashboard_bundle(profile)
    return templates.TemplateResponse(
        request,
        "macro.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "bundle": bundle,
            "page": "macro",
        },
    )


@app.get("/app/allocation", response_class=HTMLResponse)
def allocation(request: Request, profile: str = "bilanciato"):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    bundle = get_dashboard_bundle(profile)
    return templates.TemplateResponse(
        request,
        "allocation.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "bundle": bundle,
            "page": "allocation",
        },
    )


@app.get("/app/reports", response_class=HTMLResponse)
def reports(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    report_rows = list_reports_for_user(int(user["id"]))
    return templates.TemplateResponse(
        request,
        "reports.html",
        {
            "request": request,
            "user": user,
            "reports": report_rows,
            "page": "reports",
        },
    )


@app.post("/app/generate-report")
def create_report(request: Request, profile: str = Form(...)):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    user_id = int(user["id"])
    report_count = count_reports_for_user(user_id)
    premium = is_user_premium(user_id)

    if (not premium) and report_count >= FREE_REPORT_LIMIT:
        return RedirectResponse("/pricing", status_code=302)

    generate_user_report(user_id, profile)
    return RedirectResponse("/app/reports", status_code=302)


@app.get("/admin/users")
def admin_users_json(request: Request):
    user = current_user(request)
    if not is_admin_user(user):
        return RedirectResponse("/", status_code=302)

    return get_all_users()


@app.get("/admin/users-page", response_class=HTMLResponse)
def admin_users_page(request: Request):
    user = current_user(request)
    if not is_admin_user(user):
        return RedirectResponse("/", status_code=302)

    users = get_all_users()
    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "page": "admin",
        },
    )


@app.post("/admin/users/{user_id}/premium")
def admin_set_premium(request: Request, user_id: int, value: int = Form(...)):
    user = current_user(request)
    if not is_admin_user(user):
        return RedirectResponse("/", status_code=302)

    set_user_premium(user_id, value)
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
@app.get('/otp-login', response_class=HTMLResponse)
def otp_login_page(request: Request):
    return templates.TemplateResponse(
        request,
        'otp_login.html',
        {'request': request}
    )


@app.post('/send-code')
def send_code(request: Request, email: str = Form(...)):
    code = str(random.randint(100000, 999999))

    otp_storage[email] = code

    send_otp_email(email, code)

    return templates.TemplateResponse(
        request,
        'otp_verify.html',
        {'request': request, 'email': email}
    )


@app.post('/verify-code')
def verify_code(request: Request, email: str = Form(...), code: str = Form(...)):
    saved_code = otp_storage.get(email)

    if not saved_code or saved_code != code:
        return templates.TemplateResponse(
            request,
            'otp_verify.html',
            {'request': request, 'email': email, 'error': 'Codice errato'}
        )

    user = get_user_by_email(email)

    if not user:
        user_id = create_user("Cliente", email, "nopassword")
    else:
        user_id = user['id']

    request.session.clear()
    request.session['user_id'] = int(user_id)

    return RedirectResponse('/app/dashboard', status_code=302)
