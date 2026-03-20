from typing import TYPE_CHECKING

from aiohttp_s3_client import S3Client
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import helpers
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN, ErrorCode

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

type ScalewayConfigEntry = ConfigEntry[S3Client]


async def async_setup_entry(hass: HomeAssistant, entry: ScalewayConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    match await helpers.check_connection(session, entry.data):
        case ErrorCode.INVALID_AUTH as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key=error,
            )
        case ErrorCode.CONNECTION_ERROR | ErrorCode.SERVER_ERROR as error:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key=error,
            )
        case error if error is not None:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key=error,
            )
        case None:
            pass

    entry.runtime_data = helpers.create_client(session, entry.data)

    # Notify backup listeners
    def notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ScalewayConfigEntry) -> bool:
    return True
