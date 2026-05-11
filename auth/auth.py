from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


USERS_PATH = Path(__file__).resolve().parent / "users.json"


class LoginRequest(BaseModel):
    username: str
    password: str


def ensure_default_users() -> None:
    if USERS_PATH.exists() and USERS_PATH.stat().st_size > 0:
        return

    default_users = {
        "users": [
            {
                "username": "admin",
                "password": "admin123",
                "nickname": "admin",
                "role": "admin",
            },
            {
                "username": "user1",
                "password": "user123",
                "nickname": "user1",
                "role": "user",
            },
        ]
    }
    USERS_PATH.write_text(json.dumps(default_users, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_users() -> list[dict[str, Any]]:
    ensure_default_users()
    payload = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    return list(payload.get("users", []))


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    for user in load_users():
        if user.get("username") == username and user.get("password") == password:
            return user
    return None
