# MAIN WITH PREMIUM

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.auth import (
    ensure_tables,
    count_reports_for_user,
    set_user_premium,
    is_user_premium,
    get_all_users
)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

FREE_LIMIT = 3


@app.on_event("startup")
def startup():
    ensure_tables()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "landing.html", {"request": request})


@app.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request):
    return templates.TemplateResponse(request, "pricing.html", {"request": request})


@app.get("/admin/users-page", response_class=HTMLResponse)
def admin_page(request: Request):
    users = get_all_users()
    return templates.TemplateResponse(request, "admin_users.html", {"request": request, "users": users})


@app.post("/admin/users/{user_id}/premium")
def set_premium(user_id: int, value: int = Form(...)):
    set_user_premium(user_id, value)
    return RedirectResponse("/admin/users-page", status_code=302)


@app.post("/generate")
def generate(user_id: int):
    if not is_user_premium(user_id):
        count = count_reports_for_user(user_id)
        if count >= FREE_LIMIT:
            return RedirectResponse("/pricing", status_code=302)

    return {"status": "report generated"}
