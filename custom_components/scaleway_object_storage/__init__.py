from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from . import helpers
from .const import DOMAIN, DATA_BACKUP_AGENT_LISTENERS

if TYPE_CHECKING:
    from types_aiobotocore_s3.client import S3Client

type ScalewayConfigEntry = ConfigEntry[S3Client]


async def async_setup_entry(hass: HomeAssistant, entry: ScalewayConfigEntry) -> bool:
    client = helpers.create_client(entry.data)
    async with client as s3_client:
        error = await helpers.check_connection(s3_client, entry.data)
        if error:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key=error,
            )

    entry.runtime_data = await client.__aenter__()

    # Notify backup listeners
    def notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ScalewayConfigEntry) -> bool:
    client = entry.runtime_data
    await client.__aexit__(None, None, None)
    return True
