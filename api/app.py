import os
import httpx
import asyncio
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from utils.auth import require_auth, require_role
from utils.logger import logger


load_dotenv()

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")

ROLE_MAP = {
    "1058822264046485536": "owner",
    "1482303493757993091": "dev",
    "1058822264046485535": "admin",
    "1058822264046485534": "mod",
    "1117188071406964787": "support",
}

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

    app.add_middleware(
        SessionMiddleware,
        secret_key=os.getenv("CHAOSBOT_SESSION_SECRET"),
        https_only=True
    )

    app.mount("/web", StaticFiles(directory="web", html=True), name="web")

    @app.get("/")
    async def root():
        return RedirectResponse(url="/login")

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

    @app.get("/auth/callback")
    async def auth_callback(code: str, request: Request):
        async with httpx.AsyncClient() as client:
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

            user_res = await client.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_data = user_res.json()

            member_res = await client.get(
                f"https://discord.com/api/users/@me/guilds/{DISCORD_GUILD_ID}/member",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            member_data = member_res.json()
            member_roles = member_data.get("roles", [])

            role = "user"
            for role_id, role_name in ROLE_MAP.items():
                if role_id in member_roles:
                    role = role_name
                    break

            request.session["user"] = {
                "id": user_data["id"],
                "name": user_data["username"],
                "avatar": user_data.get("avatar"),
                "role": role
            }

        return RedirectResponse(url=ROLE_REDIRECT.get(role, "/web/dashboard.html"))

    @app.post("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/login")

    @app.get("/api/me")
    async def me(request: Request, _ = Depends(require_auth)):
        return request.session.get("user")

    @app.get("/api/dashboard", dependencies=[Depends(require_auth)])
    async def dashboard():
        return {
            "server": {
                "name": bot.guilds[0].name if bot.guilds else "—",
                "users": bot.guilds[0].member_count if bot.guilds else 0
            },
            "stats": {
                "bot": {
                    "status": "ONLINE" if bot.is_ready() else "OFFLINE",
                    "latency": round(bot.latency * 1000)
                }
            }
        }

    @app.get("/api/stats", dependencies=[Depends(require_auth)])
    async def stats():
        try:
            from utils.warnings_db import count_warnings
            import discord

            guild = bot.guilds[0] if bot.guilds else None
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
            return {"warns": 0, "activeUsers": 0, "error": str(e)}

    @app.get("/api/users", dependencies=[Depends(require_role("mod"))])
    async def users():
        try:
            guild = bot.guilds[0] if bot.guilds else None
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
                    "badges": []
                })
            return {"users": result}

        except Exception as e:
            return {"users": [], "error": str(e)}

    @app.get("/api/logs", dependencies=[Depends(require_auth)])
    async def logs():
        log_path = "/app/logs/bot.log"
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
            recent = list(reversed(lines[-50:]))
            return {"logs": [line.strip() for line in recent if line.strip()]}
        except Exception as e:
            return {"logs": [f"Log-Datei nicht gefunden: {str(e)}"]}

    @app.post("/api/mod/action", dependencies=[Depends(require_role("mod"))])
    async def mod_action(data: dict, request: Request):
        action = data.get("action")
        target_id = int(data.get("target_id", 0))
        reason = data.get("reason", "Kein Grund angegeben (Dashboard)")
        timeout_minutes = int(data.get("timeout_minutes", 0))

        guild = bot.guilds[0] if bot.guilds else None
        if not guild:
            return {"ok": False, "message": "Guild nicht gefunden"}

        mod_user = request.session.get("user")
        mod_id = int(mod_user.get("id", 0))
        moderator = guild.get_member(mod_id)
        target = guild.get_member(target_id)

        if not target:
            return {"ok": False, "message": "User nicht gefunden"}
        
        async def send_log(title, description, color):
            try:
                from utils.logger import log_to_channel
                import discord
                channel_id = int(config.log_channels.get("moderation", 0))
                if channel_id:
                    await log_to_channel(bot, channel_id, title, description, color)
            except Exception as e:
                logger.warning(f"Log Fehler: {e}")

        try:
            from utils.moderation_actions import safe_kick, safe_ban, safe_timeout
            from utils.warnings_db import add_warning, count_warnings, save_ban, save_timeout
            from utils.config import config
            from datetime import timedelta
            from discord.utils import utcnow
            import discord

            if action == "WARN":
                add_warning(
                    guild_id=guild.id,
                    user_id=target.id,
                    moderator_id=mod_id,
                    reason=reason
                )
                total = count_warnings(guild_id=guild.id, user_id=target.id)
                await send_log(
                    "⚠️ Verwarnung (Dashboard)",
                    f"**Moderator:** {moderator}\n**User:** {target.mention}\n**Verwarnungen gesamt:** {total}\n**Grund:** {reason}",
                    discord.Color.orange()
                )
                logger.info(f"WARN (Dashboard) | {moderator} -> {target} | {reason} | Total: {total}")
                return {"ok": True, "message": f"✅ {target.name} verwarnt ({total} Verwarnungen gesamt)"}

            elif action == "TIMEOUT":
                if timeout_minutes <= 0:
                    return {"ok": False, "message": "Timeout braucht Minuten > 0"}
                duration = timeout_minutes * 60
                until = utcnow() + timedelta(seconds=duration)
                loop = bot.loop
                future = asyncio.run_coroutine_threadsafe(
                    target.timeout(until, reason=reason),
                    loop
                )
                try:
                    future.result(timeout=10)
                except Exception as e: 
                    return {"ok": False, "message": f"Timeout Fehler: {str(e)}"}
                    
                save_timeout(guild.id, target.id, until, reason)
                await send_log(
                    "⚠️ Timeout (Dashboard)",
                    f"**Moderator:** {moderator}\n**User:** {target.mention}\n**Dauert:** {timeout_minutes}min \n**Grund:** {reason}",
                    discord.Color.orange()
                )
                logger.info(f"TIMEOUT (Dashboard) | {moderator} -> {target} | {timeout_minutes}min | {reason}")
                return {"ok": True, "message": f"✅ {target.name} für {timeout_minutes} Minuten in Timeout"}

            elif action == "KICK":
                loop =  bot.loop
                future = asyncio.run_coroutine_threadsafe(
                    target.kick(reason=reason),
                    loop
                )
                try:
                    future.result(timeout=10)
                except Exception as e:
                    return {"ok": False, "message": f"Kick Fehler: {str(e)}"}    
                await send_log(
                    "⚠️ KICK (Dashboard)",
                    f"**Moderator:** {moderator}\n**User:** {target.name}(ID: {target.id})\n**Grund:** {reason}",
                    discord.Color.orange()
                )
                logger.info(f"KICK (Dashboard) | {moderator} -> {target} | {reason}")
                return {"ok": True, "message": f"✅ {target.name} gekickt"}

            elif action == "BAN":
                loop = bot.loop
                future= asyncio.run_coroutine_threadsafe(
                    guild.ban(target, reason=reason),
                    loop
                )
                try:
                    future.result(timeout=10)
                except Exception as e:
                    return {"ok": False, "message": f"Bann Fehler: {str(e)}"}    
                save_ban(guild.id, target.id, reason)
                await send_log(
                    "⚠️ BAN (Dashboard)",
                    f"**Moderator:** {moderator}\n**User:** {target.name} (ID: {target.id})\n**Grund:** {reason}",
                    discord.Color.orange()
                )
                logger.info(f"BAN (Dashboard) | {moderator} -> {target} | {reason}")
                return {"ok": True, "message": f"✅ {target.name} gebannt"}

            else:
                return {"ok": False, "message": "Unbekannte Action"}

        except Exception as e:
            logger.error(f"Mod Action Fehler: {e}")
            return {"ok": False, "message": str(e)}

    @app.get("/api/dev/logs", dependencies=[Depends(require_role("dev"))])
    async def dev_logs():
        log_path = "/app/logs/bot.log"
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
            recent = list(reversed(lines[-100:]))
            return {"logs": [line.strip() for line in recent if line.strip()]}
        except Exception as e:
            return {"logs": [f"Log-Datei nicht gefunden: {str(e)}"]}

    @app.post("/api/dev/bot", dependencies=[Depends(require_role("dev"))])
    async def dev_bot_control(data: dict):
        action = data.get("action")
        import subprocess
        try:
            if action == "restart":
                subprocess.Popen(["docker", "compose", "restart", "discordbot-dev"], cwd="/app")
                return {"ok": True, "message": "Dev Bot wird neugestartet..."}
            elif action == "stop":
                subprocess.Popen(["docker", "compose", "stop", "discordbot-dev"], cwd="/app")
                return {"ok": True, "message": "Dev Bot wird gestoppt..."}
            elif action == "start":
                subprocess.Popen(["docker", "compose", "start", "discordbot-dev"], cwd="/app")
                return {"ok": True, "message": "Dev Bot wird gestartet..."}
            else:
                return {"ok": False, "message": "Unbekannte Action"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    return app