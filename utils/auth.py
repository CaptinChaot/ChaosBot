import os
import httpx
from fastapi import Request, HTTPException

# Diese Funktion prüft ob der User eingeloggt ist
# und gibt einen 401 Fehler zurück wenn nicht
def require_auth(request: Request):
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Not authenticated")

# Diese Funktion gibt die Rolle des eingeloggten Users zurück
def get_role(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user.get("role", "user")

# Die Rollen-Hierarchie — höhere Zahl = mehr Rechte
ROLE_HIERARCHY = {
    "user": 0,
    "support": 1,
    "mod": 2,
    "admin": 3,
    "dev": 4,
    "owner": 5
}

# Prüft ob der User mindestens eine bestimmte Rolle hat
def require_role(minimum_role: str):
    def checker(request: Request):
        role = get_role(request)
        if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get(minimum_role, 0):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return role
    return checker