import os
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from utils.auth import require_auth, require_role

load_dotenv()

# Discord OAuth2 Einstellungen aus der .env
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")

# Welche Discord Rollen-IDs welcher Panel-Rolle entsprechen
# Diese IDs musst du noch mit deinen echten Rollen-IDs ersetzen!
ROLE_MAP = {
    "1058822264046485536":   "owner",
    "1482303493757993091":     "dev",
    "1058822264046485535":   "admin",
    "1058822264046485534":     "mod",
    "1117188071406964787": "support",
}

# Wohin wird der User nach Login je nach Rolle weitergeleitet
ROLE_REDIRECT = {
    "owner":   "/web/panel_admin.html",
    "dev":     "/web/panel_dev.html",
    "admin":   "/web/panel_admin.html",
    "mod":     "/web/panel_mod.html",
    "support": "/web/panel_mod.html",
    "user":    "/web/dashboard.html",
}

def create_api(bot):
    app = FastAPI(title="ChaosBot API")

    # Session Middleware — speichert Login-Daten im Cookie
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.getenv("CHAOSBOT_SESSION_SECRET"),
        https_only=False  # später True wenn HTTPS läuft
    )

    # Statische Dateien — dein HTML/CSS/JS Dashboard
    app.mount("/web", StaticFiles(directory="web", html=True), name="web")

    # Startseite leitet zum Login weiter
    @app.get("/")
    async def root():
        return RedirectResponse(url="/login")

    # ---------------------------
    # DISCORD OAuth2 LOGIN
    # ---------------------------

    # Schritt 1: User wird zu Discord weitergeleitet
    @app.get("/login")
    async def login():
        url = (
            f"https://discord.com/oauth2/authorize"
            f"?client_id={DISCORD_CLIENT_ID}"
            f"&redirect_uri={DISCORD_REDIRECT_URI}"
            f"&response_type=code"
            f"&scope=identify+guilds.members.read"
        )
        return RedirectResponse(url=url)

    # Schritt 2: Discord leitet zurück mit einem Code
    # Wir tauschen den Code gegen einen Token und holen die Userdaten
    @app.get("/auth/callback")
    async def auth_callback(code: str, request: Request):
        async with httpx.AsyncClient() as client:

            # Code gegen Access Token tauschen
            token_res = await client.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": DISCORD_CLIENT_ID,
                    "client_secret": DISCORD_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": DISCORD_REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            token_data = token_res.json()
            access_token = token_data.get("access_token")

            if not access_token:
                raise HTTPException(status_code=400, detail="Login fehlgeschlagen")

            # Userdaten von Discord holen (Name, ID, Avatar)
            user_res = await client.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_data = user_res.json()

            # Rollen des Users auf deinem Server holen
            member_res = await client.get(
                f"https://discord.com/api/users/@me/guilds/{DISCORD_GUILD_ID}/member",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            member_data = member_res.json()
            member_roles = member_data.get("roles", [])

            # Rolle bestimmen — höchste Rolle gewinnt
            role = "user"
            for role_id, role_name in ROLE_MAP.items():
                if role_id in member_roles:
                    role = role_name
                    break

            # User in Session speichern
            request.session["user"] = {
                "id": user_data["id"],
                "name": user_data["username"],
                "avatar": user_data.get("avatar"),
                "role": role
            }

        # Weiterleitung je nach Rolle
        return RedirectResponse(url=ROLE_REDIRECT.get(role, "/web/dashboard.html"))

    # ---------------------------
    # LOGOUT
    # ---------------------------
    @app.post("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/login")

    # ---------------------------
    # API ENDPOINTS
    # ---------------------------

    # Gibt die Session-Daten des eingeloggten Users zurück
    @app.get("/api/me")
    async def me(request: Request, _ = Depends(require_auth)):
        return request.session.get("user")

    # Dashboard Daten — jeder eingeloggte User
    @app.get("/api/dashboard", dependencies=[Depends(require_auth)])
    async def dashboard():
        return {
            "server": {
                "name": bot.guilds[0].name if bot.guilds else "—",
                "users": bot.guilds[0].member_count if bot.guilds else 0
            },
            "stats": {
                "warns": 0,
                "activeUsers": 0,
                "bot": {
                    "status": "ONLINE" if bot.is_ready() else "OFFLINE",
                    "latency": round(bot.latency * 1000)
                }
            }
        }

    # Mod Actions — nur ab Mod aufwärts
    @app.post("/api/mod/action", dependencies=[Depends(require_role("mod"))])
    async def mod_action(data: dict):
        return {"ok": True, "message": "action received"}
# Echte Logs aus bot.log lesen
    @app.get("/api/logs", dependencies=[Depends(require_auth)])
    async def logs():
        log_path = "/app/logs/bot.log"
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
            # Letzte 50 Zeilen, neueste zuerst
            recent = list(reversed(lines[-50:]))
            return {"logs": [line.strip() for line in recent if line.strip()]}
        except Exception as e:
            return {"logs": [f"Log-Datei nicht gefunden: {str(e)}"]}

    # Echte User vom Discord Server laden
   # Echte User vom Discord Server laden
    @app.get("/api/users", dependencies=[Depends(require_role("mod"))])
    async def users():
        try:
            guild = bot.guilds[0] if bot.guilds else None
            if not guild:
                return {"users": [], "error": "Keine Guild gefunden"}

            return {"users": [], "debug": {
                "guild_name": guild.name,
                "member_count": guild.member_count,
                "cached_members": len(guild.members)
            }}

        except Exception as e:
            return {"users": [], "error": str(e), "type": str(type(e))}
    return app