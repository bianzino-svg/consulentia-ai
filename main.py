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

BASE_DIR = Path(__file__).resolve().parent
FREE_REPORT_LIMIT = 3

templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))

app = FastAPI(title='ConsulentIA AI')

# 🔐 SESSIONI SICURE + PERSISTENTI
app.add_middleware(
    SessionMiddleware,
    secret_key='SUPER-SECRET-KEY-CAMBIALA',
    max_age=60 * 60 * 24 * 7,  # 7 giorni
    same_site="lax",
    https_only=False  # metti True quando userai https definitivo
)

app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')


def current_user(request: Request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    return get_user_by_id(user_id)


def require_user(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse('/login', status_code=302)
    return user


@app.on_event('startup')
def startup():
    init_db()


# ---------------- LANDING ----------------

@app.get('/', response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse('landing.html', {
        'request': request,
        'user': current_user(request)
    })


# ---------------- AUTH ----------------

@app.get('/register', response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse('register.html', {
        'request': request,
        'user': None,
        'error': None
    })


@app.post('/register')
def register(request: Request, full_name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    user_id = create_user(full_name, email, password)
    if not user_id:
        return templates.TemplateResponse('register.html', {
            'request': request,
            'error': 'Email già registrata',
            'user': None
        })

    request.session.clear()
    request.session['user_id'] = user_id

    return RedirectResponse('/app/dashboard', status_code=302)


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse('login.html', {
        'request': request,
        'user': None,
        'error': None
    })


@app.post('/login')
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = authenticate_user(email, password)

    if not user:
        return templates.TemplateResponse('login.html', {
            'request': request,
            'error': 'Credenziali errate',
            'user': None
        })

    # 🔥 RESET SESSIONE (evita utenti condivisi)
    request.session.clear()
    request.session['user_id'] = int(user['id'])

    return RedirectResponse('/app/dashboard', status_code=302)


@app.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/', status_code=302)


# ---------------- APP ----------------

@app.get('/app/dashboard', response_class=HTMLResponse)
def dashboard(request: Request, profile: str = 'bilanciato'):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    bundle = get_dashboard_bundle(profile)

    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'user': user,
        'profile': profile,
        'bundle': bundle
    })


@app.get('/app/reports', response_class=HTMLResponse)
def reports(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    report_rows = list_reports_for_user(int(user['id']))

    return templates.TemplateResponse('reports.html', {
        'request': request,
        'user': user,
        'reports': report_rows
    })


@app.post('/app/generate-report')
def create_report(request: Request, profile: str = Form(...)):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    user_id = int(user['id'])
    report_count = count_reports_for_user(user_id)
    premium = is_user_premium(user_id)

    if (not premium) and report_count >= FREE_REPORT_LIMIT:
        return RedirectResponse('/pricing', status_code=302)

    generate_user_report(user_id, profile)
    return RedirectResponse('/app/reports', status_code=302)


# ---------------- ADMIN ----------------

ADMIN_EMAIL = "info@bianzino.it".lower()


@app.get('/admin/users-page', response_class=HTMLResponse)
def admin_users_page(request: Request):
    user = current_user(request)

    if not user or user['email'] != ADMIN_EMAIL:
        return RedirectResponse('/', status_code=302)

    users = get_all_users()

    return templates.TemplateResponse('admin_users.html', {
        'request': request,
        'user': user,
        'users': users
    })


@app.post('/admin/users/{user_id}/premium')
def admin_set_premium(request: Request, user_id: int, value: int = Form(...)):
    user = current_user(request)

    if not user or user['email'] != ADMIN_EMAIL:
        return RedirectResponse('/', status_code=302)

    set_user_premium(user_id, value)
    return RedirectResponse('/admin/users-page', status_code=302)


# ---------------- DOWNLOAD ----------------

@app.get('/download')
def download_file(request: Request, path: str):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    file_path = Path(path)

    if not file_path.exists():
        return RedirectResponse('/app/reports', status_code=302)

    return FileResponse(str(file_path))