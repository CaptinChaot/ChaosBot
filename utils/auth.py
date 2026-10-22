from fastapi import Request, HTTPException

# Die Rollen-Hierarchie — höhere Zahl = mehr Rechte
# (in 10er-Schritten, damit co_owner zwischen dev und owner passt – wie bei PermLevel)
ROLE_HIERARCHY = {
    "user": 0,
    "support": 10,
    "mod": 20,
    "admin": 30,
    "dev": 40,
    "co_owner": 45,
    "owner": 50,
}


def role_at_least(role: str, minimum_role: str) -> bool:
    """True, wenn 'role' mindestens so hoch ist wie 'minimum_role'."""
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(minimum_role, 999)


# Prüft nur, ob überhaupt jemand eingeloggt ist (ohne Rollen-Check)
def require_auth(request: Request):
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

# Die eigentliche Rollenprüfung passiert jetzt in api/app.py,
# weil sie die LIVE-Rollen vom Discord-Server braucht (dafür braucht man den Bot).
