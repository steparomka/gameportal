# Файл: auth_steam.py
# Авторизация через Steam OpenID

import os
import re
import httpx
from fastapi import Request
from urllib.parse import urlencode

STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")
STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"

def get_steam_login_url(return_url: str) -> str:
    """Генерируем ссылку для входа через Steam"""
    params = {
        "openid.ns":         "http://specs.openid.net/auth/2.0",
        "openid.mode":       "checkid_setup",
        "openid.return_to":  return_url,
        "openid.realm":      return_url.split("/auth")[0],
        "openid.identity":   "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{STEAM_OPENID_URL}?{urlencode(params)}"


async def verify_steam_login(params: dict) -> str | None:
    """Проверяем ответ от Steam и получаем Steam ID"""
    check_params = dict(params)
    check_params["openid.mode"] = "check_authentication"

    async with httpx.AsyncClient() as client:
        resp = await client.post(STEAM_OPENID_URL, data=check_params)
        if "is_valid:true" not in resp.text:
            return None

    # Извлекаем Steam ID из claimed_id
    claimed_id = params.get("openid.claimed_id", "")
    match = re.search(r"/openid/id/(\d+)$", claimed_id)
    return match.group(1) if match else None


async def get_steam_user(steam_id: str) -> dict | None:
    """Получаем данные пользователя из Steam API"""
    url = (
        f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
        f"?key={STEAM_API_KEY}&steamids={steam_id}"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        data = resp.json()

    players = data.get("response", {}).get("players", [])
    if not players:
        return None

    p = players[0]
    return {
        "steam_id":   p.get("steamid"),
        "nickname":   p.get("personaname"),
        "avatar":     p.get("avatarfull"),
        "profile_url": p.get("profileurl"),
    }
