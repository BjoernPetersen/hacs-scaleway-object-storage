from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "scaleway_object_storage"

CONF_ACCESS_KEY: Final = "access_key"
CONF_SECRET_KEY: Final = "secret_key"
CONF_BUCKET: Final = "bucket"
CONF_REGION: Final = "region"
CONF_OBJECT_PREFIX: Final = "object_prefix"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
