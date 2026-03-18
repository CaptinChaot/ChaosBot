from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

class Config:
    def __init__(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"❌ config.yaml nicht gefunden unter {CONFIG_PATH}")

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

    @property
    def guild_id(self) -> int:
        return int(self._data.get("guild_id", 0))

    @property
    def roles(self) -> dict:
        return self._data.get("roles", {})

    @property
    def log_channels(self) -> dict:
        return self._data.get("log_channels", {})
    
    @property
    def moderation(self) -> dict:
        return self._data.get("moderation", {})
    
    @property
    def role_management(self) -> dict:
        return self._data.get("role_management", {})
    
    @property
    def permissions(self) -> dict:
        return self._data.get("permissions", {})
    
    @property
    def security(self) -> dict:
        sec =self._data.get("security", {})
        return sec if isinstance(sec, dict) else {}
    
    @property
    def tickets(self) -> dict:
        tickets = self._data.get("tickets",{})
        return tickets if isinstance(tickets, dict) else {}
    
    @property
    def features(self) -> dict:
        features = self._data.get("features", {})
        return features if isinstance(features, dict) else {}
    
    @property
    def channels(self) -> dict:
        channels = self._data.get("channels", {})
        return channels if isinstance(channels, dict) else {}
    @property
    def welcome_channel(self) -> int | None:
        return int(self.channels.get("welcome_channel", 0))
    
    @property
    def member_count_vc(self) -> int | None:
        return int(self.channels.get("member_count_vc", 0))
    
    @property
    def twitch(self) -> dict:
        twitch = self._data.get("twitch", {})
        return twitch if isinstance(twitch, dict) else {}
    
    @property
    def rules(self) -> dict:
        return self._data.get("rules", {})
    
    @property
    def automod(self) -> dict:
        return self._data.get("automod", {})
    
    @property
    def birthday(self) -> dict:
        return self._data.get("birthday", {})
    
# Singleton
config = Config()
