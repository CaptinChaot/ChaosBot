from utils.config import config
from utils import guild_settings_db as db


GUILD_SELECTIONS = ("roles", "channels", "log_channels", "rules", "tickets", "twitch", "birthday")

class GuildConfig:
    def __init__(self, guild_id: int, data:dict):
        self.guild_id = guild_id
        self._data = data


    def _section(self, name: str) -> dict:
        return self._data.get(name, {})

    @property
    def roles(self) -> dict:
        return self._section("roles")

    @property
    def channels(self) -> dict:
        return self._section("channels")

    @property
    def log_channels(self) -> dict:
        return self._section("log_channels")

    @property
    def rules(self) -> dict:
        return self._section("rules")

    @property
    def tickets(self) -> dict:
        return self._section("tickets")

    @property
    def twitch(self) -> dict:
        return self._section("twitch")

    @property
    def birthday(self) -> dict:
        return self._section("birthday")

        #-GLOBAL CONFIGS
    @property
    def permissions(self) -> dict:
        return config.permissions

    @property
    def automod(self) -> dict:
        return config.automod

    @property
    def moderation(self) -> dict:
        return config.moderation

    @property
    def features(self) -> dict:
        return config.features

_cache: dict[int, GuildConfig] = {}


def get_guild_config(guild_id: int) -> GuildConfig:
    if guild_id not in _cache:
        _cache[guild_id] = _load(guild_id)
    return _cache[guild_id]


def _load(guild_id: int) -> GuildConfig:
    data = {}
    for section, key, value in db.get_settings(guild_id):
        data.setdefault(section, {})[key] = value
    return GuildConfig(guild_id, data)

def update_setting(guild_id: int, section: str, key: str, value):
    db.set_setting(guild_id, section, key, value)
    _cache.pop(guild_id, None)

def seed_from_config(guild_id: int) -> bool:
    """Kopiert einmalig die Werte aus der config.yaml in die DB."""
    if db.has_setting(guild_id):
        return False

    for section in GUILD_SELECTIONS:
        values = getattr(config, section) or {}
        for key, value in values.items():
            if isinstance(value, (dict, list, bool)):
                continue
            db.set_setting(guild_id, section, key, value)

    _cache.pop(guild_id, None)    
    return True
