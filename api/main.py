import os
import json
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.db import init_db, rows, execute, now, get_settings, set_setting

init_db()

app = FastAPI(title="NightFall SaaS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
API_SECRET = os.getenv("API_SECRET", "troque-esse-segredo")


class LoginBody(BaseModel):
    username: str
    password: str


class StatusBody(BaseModel):
    status: str
    staff_note: str | None = None


class SettingsBody(BaseModel):
    settings: dict


def require_token(authorization: str | None = Header(default=None)):
    if authorization != f"Bearer {API_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def add_log(event: str, payload: dict):
    execute(
        "INSERT INTO logs (event, payload, created_at) VALUES (?, ?, ?)",
        (event, json.dumps(payload, ensure_ascii=False), now())
    )


@app.post("/auth/login")
def login(body: LoginBody):
    if body.username == ADMIN_USER and body.password == ADMIN_PASSWORD:
        return {"token": API_SECRET}
    raise HTTPException(status_code=401, detail="Login inválido")


@app.get("/dashboard", dependencies=[Depends(require_token)])
def dashboard():
    apps = rows("SELECT * FROM applications ORDER BY id DESC LIMIT 500")
    suggestions = rows("SELECT * FROM suggestions ORDER BY id DESC LIMIT 500")

    return {
        "stats": {
            "applications": len(apps),
            "pending": len([a for a in apps if a["status"] == "pending"]),
            "approved": len([a for a in apps if a["status"] == "approved"]),
            "rejected": len([a for a in apps if a["status"] == "rejected"]),
            "interview": len([a for a in apps if a["status"] == "interview"]),
            "suggestions": len(suggestions)
        },
        "applications": apps,
        "suggestions": suggestions,
        "settings": get_settings()
    }


@app.patch("/applications/{app_id}/status", dependencies=[Depends(require_token)])
def update_application(app_id: int, body: StatusBody):
    if body.status not in ["pending", "approved", "rejected", "interview"]:
        raise HTTPException(status_code=400, detail="Status inválido")

    execute(
        "UPDATE applications SET status=?, staff_note=?, updated_at=? WHERE id=?",
        (body.status, body.staff_note, now(), app_id)
    )

    add_log("application_status", {
        "id": app_id,
        "status": body.status,
        "source": "dashboard"
    })

    return {"ok": True}


@app.patch("/suggestions/{suggestion_id}/status", dependencies=[Depends(require_token)])
def update_suggestion(suggestion_id: int, body: StatusBody):
    if body.status not in ["analysis", "accepted", "rejected", "implemented"]:
        raise HTTPException(status_code=400, detail="Status inválido")

    execute(
        "UPDATE suggestions SET status=?, updated_at=? WHERE id=?",
        (body.status, now(), suggestion_id)
    )

    add_log("suggestion_status", {
        "id": suggestion_id,
        "status": body.status,
        "source": "dashboard"
    })

    return {"ok": True}


@app.put("/settings", dependencies=[Depends(require_token)])
def update_settings(body: SettingsBody):
    normalized = {}

    for key, value in body.settings.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)

        set_setting(key, value)
        normalized[key] = value

    add_log("settings_updated", {
        "source": "dashboard",
        "keys": list(normalized.keys())
    })

    return {"ok": True, "settings": get_settings()}


@app.get("/health")
def health():
    return {"ok": True}
