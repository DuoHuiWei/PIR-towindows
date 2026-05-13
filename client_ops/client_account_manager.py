from __future__ import annotations

import json
from pathlib import Path
from typing import Any


USERS_PATH = Path(__file__).resolve().parents[1] / "auth" / "users.json"


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


def _load_payload() -> dict[str, Any]:
    ensure_default_users()
    return json.loads(USERS_PATH.read_text(encoding="utf-8-sig"))


def _write_payload(payload: dict[str, Any]) -> None:
    USERS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _public_user(user: dict[str, Any]) -> dict[str, str]:
    return {
        "username": str(user.get("username", "")),
        "nickname": str(user.get("nickname", "")),
        "role": str(user.get("role", "user")),
    }


def list_users(keyword: str = "") -> list[dict[str, str]]:
    users = [_public_user(user) for user in _load_payload().get("users", [])]
    needle = keyword.strip().lower()
    if not needle:
        return users
    return [
        user
        for user in users
        if needle in user["username"].lower() or needle in user["nickname"].lower()
    ]


def delete_user(username: str) -> dict[str, object]:
    target = username.strip()
    if not target:
        raise ValueError("username is required")

    payload = _load_payload()
    users = list(payload.get("users", []))
    target_user = next((user for user in users if user.get("username") == target), None)
    if target_user is None:
        raise KeyError(f"user not found: {target}")

    if target_user.get("role") == "admin":
        admin_count = sum(1 for user in users if user.get("role") == "admin")
        if admin_count <= 1:
            raise ValueError("cannot delete the last admin user")

    payload["users"] = [user for user in users if user.get("username") != target]
    _write_payload(payload)
    return {
        "username": target,
        "nickname": str(target_user.get("nickname", "")),
        "deleted": True,
    }


def reset_password(username: str, new_password: str) -> dict[str, object]:
    target = username.strip()
    password = new_password.strip()
    if not target:
        raise ValueError("username is required")
    if not password:
        raise ValueError("new password is required")

    payload = _load_payload()
    users = list(payload.get("users", []))
    for user in users:
        if user.get("username") == target:
            user["password"] = password
            _write_payload(payload)
            return {
                "username": target,
                "nickname": str(user.get("nickname", "")),
                "reset": True,
            }

    raise KeyError(f"user not found: {target}")


def add_user(nickname: str, username: str, password: str) -> dict[str, str]:
    clean_nickname = nickname.strip()
    clean_username = username.strip()
    clean_password = password.strip()
    if not clean_nickname:
        raise ValueError("nickname is required")
    if not clean_username:
        raise ValueError("username is required")
    if len(clean_password) < 6:
        raise ValueError("password must be at least 6 characters")

    payload = _load_payload()
    users = list(payload.get("users", []))
    if any(user.get("nickname") == clean_nickname for user in users):
        raise ValueError("nickname already exists")
    if any(user.get("username") == clean_username for user in users):
        raise ValueError("username already exists")

    user = {
        "username": clean_username,
        "password": clean_password,
        "nickname": clean_nickname,
        "role": "user",
    }
    users.append(user)
    payload["users"] = users
    _write_payload(payload)
    return _public_user(user)
