import os
import asyncio
import secrets
from urllib.parse import urlencode

import httpx
import discord
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from utils.auth import role_at_least
from utils.config import config
from utils.logger import logger, log_to_channel, LOG_FILE
from utils.permissions import get_user_perm_level, has_permission, PermLevel

# KEIN load_dotenv() mehr hier: main.py lädt schon die richtige Datei (.env ODER .env.dev).
# Vorher hat diese Datei zusätzlich immer die Prod-.env geladen – auch im Dev-Container.

# Reihenfolge = Priorität: die höchste Rolle zuerst.
# (config-Key, Dashboard-Rolle) – die IDs kommen aus config.yaml, damit Dev-Overrides greifen.
ROLE_ORDER = [
    ("owner", "owner"),
    ("co_owner", "co_owner"),
    ("dev", "dev"),
    ("admin", "admin"),
    ("moderator", "mod"),
    ("supporter", "support"),
]

ROLE_REDIRECT = {
    "owner":    "/web/panel_admin.html",
    "co_owner": "/web/panel_admin.html",
    "dev":      "/web/panel_dev.html",
    "admin":    "/web/panel_admin.html",
    "mod":      "/web/panel_mod.html",
    "support":  "/web/panel_mod.html",
    "user":     "/web/dashboard.html",
}

# Dashboard-Action → Key in config.yaml → permissions (gleiche Regeln wie die Slash-Commands)
ACTION_PERMISSION = {
    "WARN": "warn",
    "TIMEOUT": "timeout",
    "KICK": "kick",
    "BAN": "ban",
}

MAX_TIMEOUT_MINUTES = 28 * 24 * 60  # Discord erlaubt max. 28 Tage


def role_from_ids(role_ids: set[int]) -> str:
    """Sucht die höchste Dashboard-Rolle anhand der Discord-Rollen-IDs."""
    for config_key, dashboard_role in ROLE_ORDER:
        role_id = config.roles.get(config_key)
        if role_id and int(role_id) in role_ids:
            return dashboard_role
    return "user"


def check_hierarchy(guild: discord.Guild, moderator: discord.Member, target: discord.Member) -> str | None:
    """Gleiche Schutzregeln wie hardlock_check bei den Slash-Commands.
    Gibt eine Fehlermeldung zurück – oder None, wenn alles okay ist."""
    if target.id == moderator.id:
        return "Du kannst dich nicht selbst moderieren."
    if target.bot:
        return "Bots können nicht moderiert werden."
    if get_user_perm_level(target) >= PermLevel.DEV:
        return "Dieser User ist geschützt (Dev / Owner)."
    if guild.me is None or target.top_role >= guild.me.top_role:
        return "Meine Rolle ist zu niedrig für diese Aktion."
    if moderator.id != guild.owner_id and target.top_role >= moderator.top_role:
        return "User hat gleiche oder höhere Rolle als du."
    return None


def create_api(bot):
    # Env erst HIER lesen (nicht beim Import), dann ist die .env von main.py sicher geladen.
    client_id = os.getenv("DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")
    redirect_uri = os.getenv("DISCORD_REDIRECT_URI")
    session_secret = os.getenv("CHAOSBOT_SESSION_SECRET")

    # Ohne starkes Secret kann man Session-Cookies fälschen → lieber gar nicht starten.
    if not session_secret or len(session_secret) < 32:
        logger.critical("❌ CHAOSBOT_SESSION_SECRET fehlt oder ist kürzer als 32 Zeichen – Dashboard startet NICHT!")
        raise RuntimeError("CHAOSBOT_SESSION_SECRET fehlt/zu kurz")

    app = FastAPI(title="ChaosBot API", docs_url=None, redoc_url=None, openapi_url=None)

    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        https_only=True,
        same_site="lax",
        max_age=12 * 60 * 60,  # 12 Stunden statt 14 Tage
    )

    app.mount("/web", StaticFiles(directory="web", html=True), name="web")

    # ──────────────────────────────────────────────
    # Helfer
    # ──────────────────────────────────────────────

    def get_guild() -> discord.Guild | None:
        # Fester Server aus der Config statt "irgendein erster Server"
        return bot.get_guild(config.guild_id)

    async def on_bot(coro, timeout: float = 15):
        """Führt eine Discord-Aktion im Event-Loop des BOTS aus und wartet darauf,
        OHNE das Dashboard zu blockieren."""
        future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout)

    def current_user(request: Request) -> dict:
        """Eingeloggt? Noch auf dem Server? Und welche Rolle hat er JETZT gerade?"""
        user = request.session.get("user")
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        guild = get_guild()
        member = guild.get_member(int(user["id"])) if guild else None
        if member is None:
            request.session.clear()
            raise HTTPException(status_code=401, detail="Nicht (mehr) auf dem Server")

        # Rolle bei JEDER Anfrage live prüfen → wer degradiert wird, verliert sofort den Zugriff
        user["role"] = role_from_ids({r.id for r in member.roles})
        request.session["user"] = user
        return user

    def need(minimum_role: str):
        def checker(request: Request) -> dict:
            user = current_user(request)
            if not role_at_least(user["role"], minimum_role):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return user
        return checker

    # ──────────────────────────────────────────────
    # Öffentlich
    # ──────────────────────────────────────────────

    @app.api_route("/health", methods=["GET", "HEAD"])
    async def health():
        return {"status": "ok"}

    @app.get("/")
    async def root():
        return RedirectResponse(url="/login")

    @app.get("/login")
    async def login(request: Request):
        # Zufälliger "state" schützt davor, dass dir jemand seinen Login unterschiebt
        state = secrets.token_urlsafe(24)
        request.session["oauth_state"] = state
        params = urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify guilds.members.read",
            "state": state,
        })
        return RedirectResponse(url=f"https://discord.com/oauth2/authorize?{params}")

    @app.get("/auth/callback")
    async def auth_callback(request: Request, code: str | None = None, state: str | None = None):
        expected_state = request.session.pop("oauth_state", None)
        if not code or not state or not expected_state or not secrets.compare_digest(state, expected_state):
            raise HTTPException(status_code=400, detail="Ungültiger Login-Versuch – bitte nochmal einloggen")

        async with httpx.AsyncClient(timeout=10) as client:
            token_res = await client.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            access_token = token_res.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="Login fehlgeschlagen")

            auth_header = {"Authorization": f"Bearer {access_token}"}
            user_res = await client.get("https://discord.com/api/users/@me", headers=auth_header)
            member_res = await client.get(
                f"https://discord.com/api/users/@me/guilds/{config.guild_id}/member",
                headers=auth_header,
            )

        if user_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Login fehlgeschlagen")

        # Nicht auf dem Server → kein Zugang (vorher gab's hier einfach Rolle "user")
        if member_res.status_code != 200:
            logger.warning(f"Dashboard-Login abgelehnt (nicht auf dem Server): {user_res.json().get('id')}")
            raise HTTPException(status_code=403, detail="Du bist nicht auf dem ChaosBot-Server")

        user_data = user_res.json()
        role_ids = {int(r) for r in member_res.json().get("roles", [])}
        role = role_from_ids(role_ids)

        request.session.clear()  # alte Session-Reste weg
        request.session["user"] = {
            "id": user_data["id"],
            "name": user_data["username"],
            "avatar": user_data.get("avatar"),
            "role": role,
        }
        return RedirectResponse(url=ROLE_REDIRECT.get(role, "/web/dashboard.html"))

    @app.post("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/login")

    # ──────────────────────────────────────────────
    # Eingeloggt (alle Servermitglieder)
    # ──────────────────────────────────────────────

    @app.get("/api/me")
    async def me(user: dict = Depends(current_user)):
        return user

    @app.get("/api/dashboard", dependencies=[Depends(current_user)])
    async def dashboard():
        guild = get_guild()
        return {
            "server": {
                "name": guild.name if guild else "—",
                "users": guild.member_count if guild else 0,
            },
            "stats": {
                "bot": {
                    "status": "ONLINE" if bot.is_ready() else "OFFLINE",
                    "latency": round(bot.latency * 1000),
                }
            },
        }

    # ──────────────────────────────────────────────
    # Staff
    # ──────────────────────────────────────────────

    @app.get("/api/stats", dependencies=[Depends(need("mod"))])
    async def stats():
        try:
            from utils.warnings_db import count_warnings

            guild = get_guild()
            if not guild:
                return {"warns": 0, "activeUsers": 0}

            total_warns = 0
            for member in guild.members:
                if not member.bot:
                    total_warns += count_warnings(guild_id=guild.id, user_id=member.id)

            active_users = sum(
                1 for member in guild.members
                if not member.bot and member.status != discord.Status.offline
            )
            return {"warns": total_warns, "activeUsers": active_users}

        except Exception as e:
            logger.error(f"/api/stats Fehler: {e}")
            return {"warns": 0, "activeUsers": 0, "error": "Interner Fehler"}

    @app.get("/api/users", dependencies=[Depends(need("mod"))])
    async def users():
        guild = get_guild()
        if not guild:
            return {"users": [], "error": "Keine Guild gefunden"}

        result = []
        for member in guild.members:
            if member.bot:
                continue
            result.append({
                "id": str(member.id),
                "name": member.display_name,
                "status": str(member.status),
                "role": member.top_role.name if member.top_role else "Member",
                "badges": [],
            })
        return {"users": result}

    def read_last_log_lines(count: int) -> list[str]:
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            recent = list(reversed(lines[-count:]))
            return [line.strip() for line in recent if line.strip()]
        except Exception:
            logger.exception("Log-Datei konnte nicht gelesen werden")
            return ["Fehler beim Lesen der Log-Datei"]

    # Logs nur noch für Staff (Support+), vorher konnte JEDER eingeloggte User sie lesen
    @app.get("/api/logs", dependencies=[Depends(need("support"))])
    async def logs():
        return {"logs": read_last_log_lines(50)}

    @app.post("/api/mod/action")
    async def mod_action(data: dict, user: dict = Depends(need("mod"))):
        from datetime import timedelta
        from discord.utils import utcnow
        from utils.warnings_db import add_warning, count_warnings, save_ban, save_timeout
        from utils.moderation_utils import handle_auto_actions

        action = str(data.get("action", "")).upper()
        reason = str(data.get("reason") or "Kein Grund angegeben (Dashboard)")[:400]

        if action not in ACTION_PERMISSION:
            return {"ok": False, "message": "Unbekannte Action"}

        try:
            target_id = int(data.get("target_id", 0))
            timeout_minutes = int(data.get("timeout_minutes", 0) or 0)
        except (TypeError, ValueError):
            return {"ok": False, "message": "Ungültige Eingabe"}

        guild = get_guild()
        if not guild:
            return {"ok": False, "message": "Guild nicht gefunden"}

        moderator = guild.get_member(int(user["id"]))
        target = guild.get_member(target_id)
        if not moderator:
            return {"ok": False, "message": "Du bist nicht (mehr) auf dem Server"}
        if not target:
            return {"ok": False, "message": "User nicht gefunden"}

        # 1) Darf DIESER Mod DIESE Aktion? (gleiche Regeln wie /kick, /ban usw.)
        if not has_permission(moderator, ACTION_PERMISSION[action]):
            logger.warning(f"DASHBOARD BLOCK | {moderator} wollte {action} ohne Berechtigung")
            return {"ok": False, "message": "❌ Dafür hast du keine Berechtigung."}

        # 2) Darf er DIESEN User moderieren? (Rollen-Hierarchie, Schutz für Dev/Owner)
        block_reason = check_hierarchy(guild, moderator, target)
        if block_reason:
            logger.warning(f"DASHBOARD BLOCK | {moderator} -> {target} | {action} | {block_reason}")
            return {"ok": False, "message": f"❌ {block_reason}"}

        log_channel_id = int(config.log_channels.get("moderation", 0))

        async def send_log(title: str, description: str, color: discord.Color):
            try:
                await on_bot(log_to_channel(bot, log_channel_id, title, description, color))
            except Exception as e:
                logger.warning(f"Log Fehler: {e}")

        try:
            if action == "WARN":
                warning_id = add_warning(
                    guild_id=guild.id, user_id=target.id,
                    moderator_id=moderator.id, reason=reason,
                )
                total = count_warnings(guild_id=guild.id, user_id=target.id)
                await send_log(
                    "⚠️ Verwarnung (Dashboard)",
                    f"**Moderator:** {moderator}\n**User:** {target.mention}\n"
                    f"**Verwarnungen gesamt:** {total}\n**Grund:** {reason}",
                    discord.Color.orange(),
                )
                # Gleiche Auto-Aktionen (Timeout/Kick/Ban) wie beim /warn-Command
                await on_bot(handle_auto_actions(
                    bot=bot, guild=guild, moderator=moderator, user=target,
                    total_warnings=total, warning_id=warning_id,
                ))
                logger.info(f"WARN (Dashboard) | {moderator} -> {target} | {reason} | Total: {total}")
                return {"ok": True, "message": f"✅ {target.name} verwarnt ({total} Verwarnungen gesamt)"}

            if action == "TIMEOUT":
                if not 0 < timeout_minutes <= MAX_TIMEOUT_MINUTES:
                    return {"ok": False, "message": "Timeout: 1 Minute bis 28 Tage"}
                until = utcnow() + timedelta(minutes=timeout_minutes)
                await on_bot(target.timeout(until, reason=reason))
                save_timeout(guild.id, target.id, until, reason)
                await send_log(
                    "⏱️ Timeout (Dashboard)",
                    f"**Moderator:** {moderator}\n**User:** {target.mention}\n"
                    f"**Dauer:** {timeout_minutes}min\n**Grund:** {reason}",
                    discord.Color.gold(),
                )
                logger.info(f"TIMEOUT (Dashboard) | {moderator} -> {target} | {timeout_minutes}min | {reason}")
                return {"ok": True, "message": f"✅ {target.name} für {timeout_minutes} Minuten in Timeout"}

            if action == "KICK":
                await on_bot(target.kick(reason=reason))
                await send_log(
                    "👢 Kick (Dashboard)",
                    f"**Moderator:** {moderator}\n**User:** {target.name} (ID: {target.id})\n**Grund:** {reason}",
                    discord.Color.orange(),
                )
                logger.info(f"KICK (Dashboard) | {moderator} -> {target} | {reason}")
                return {"ok": True, "message": f"✅ {target.name} gekickt"}

            if action == "BAN":
                await on_bot(guild.ban(target, reason=reason))
                save_ban(guild.id, target.id, reason)
                await send_log(
                    "🔨 Ban (Dashboard)",
                    f"**Moderator:** {moderator}\n**User:** {target.name} (ID: {target.id})\n**Grund:** {reason}",
                    discord.Color.dark_red(),
                )
                logger.info(f"BAN (Dashboard) | {moderator} -> {target} | {reason}")
                return {"ok": True, "message": f"✅ {target.name} gebannt"}

        except discord.Forbidden:
            return {"ok": False, "message": "❌ Discord hat die Aktion blockiert (Bot-Rechte prüfen)."}
        except asyncio.TimeoutError:
            return {"ok": False, "message": "❌ Discord hat nicht rechtzeitig geantwortet."}
        except Exception as e:
            logger.error(f"Mod Action Fehler ({action}): {e}")
            return {"ok": False, "message": "❌ Interner Fehler – siehe Logs."}

    # ──────────────────────────────────────────────
    # Dev
    # ──────────────────────────────────────────────

    @app.get("/api/dev/logs", dependencies=[Depends(need("dev"))])
    async def dev_logs():
        return {"logs": read_last_log_lines(100)}

    @app.post("/api/dev/bot", dependencies=[Depends(need("dev"))])
    async def dev_bot_control(data: dict):
        # Hinweis: Im Container gibt es kein Docker → das hier kann (absichtlich) nicht funktionieren.
        # NICHT mit einem docker.sock-Mount "reparieren" – das wäre Root-Zugriff auf den Server per Webseite.
        return {"ok": False, "message": "Bot-Steuerung übers Dashboard ist deaktiviert (bitte per SSH)."}

    return app
