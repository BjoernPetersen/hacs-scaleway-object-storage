from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from collections.abc import Callable

DOMAIN: Final = "scaleway_object_storage"

CONF_ACCESS_KEY_ID: Final = "access_key_id"
CONF_SECRET_KEY: Final = "secret_key"
CONF_BUCKET: Final = "bucket"
CONF_REGION: Final = "region"
CONF_OBJECT_PREFIX: Final = "object_prefix"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

MAX_PARALLEL_REQUESTS: Final[int] = 8

MULTIPART_MIN_SIZE: Final[int] = 50 * 2**20
MULTIPART_PART_SIZE: Final[int] = 32 * 2**20
