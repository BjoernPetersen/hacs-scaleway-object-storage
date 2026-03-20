import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_REGION
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import helpers
from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_OBJECT_PREFIX,
    CONF_SECRET_KEY,
    CONF_SECTION_CREDENTIALS,
    DOCS_PLACEHOLDERS,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import (
        ConfigFlowResult,
    )

_LOGGER = logging.getLogger(__name__)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SECTION_CREDENTIALS): section(STEP_REAUTH_DATA_SCHEMA),
        vol.Required(CONF_REGION, default="fr-par"): SelectSelector(
            SelectSelectorConfig(
                translation_key="regions",
                options=[
                    "fr-par",
                    "nl-ams",
                    "pl-waw",
                    "it-mil",
                ],
            )
        ),
        vol.Required(CONF_BUCKET): cv.string,
        vol.Optional(CONF_OBJECT_PREFIX): cv.string,
    }
)


class ScalewayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _test_connection(
        self,
        *,
        errors: dict[str, str],
        config: dict[str, Any],
    ) -> bool:
        session = async_get_clientsession(self.hass)
        error_code = await helpers.check_connection(session, config)
        if error_code:
            errors["base"] = error_code
            return False

        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_BUCKET: user_input[CONF_BUCKET],
                    CONF_REGION: user_input[CONF_REGION],
                    CONF_OBJECT_PREFIX: user_input[CONF_OBJECT_PREFIX],
                }
            )

            if await self._test_connection(errors=errors, config=user_input):
                return self.async_create_entry(
                    title=user_input[CONF_BUCKET],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            description_placeholders=DOCS_PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_reauth(
        self, reauth_data: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if reauth_data is not None:
            config = entry.data | {CONF_SECTION_CREDENTIALS: reauth_data}
            if await self._test_connection(errors=errors, config=config):
                return self.async_update_reload_and_abort(
                    entry,
                    data=config,
                    reload_even_if_entry_is_unchanged=True,
                )

        return self.async_show_form(
            step_id="reauth",
            data_schema=self.add_suggested_values_to_schema(
                STEP_REAUTH_DATA_SCHEMA,
                reauth_data or entry.data.get(CONF_SECTION_CREDENTIALS),
            ),
            description_placeholders={
                "bucket_name": entry.data[CONF_BUCKET],
                **DOCS_PLACEHOLDERS,
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_data is not None:
            if await self._test_connection(errors=errors, config=user_data):
                return self.async_update_reload_and_abort(
                    entry,
                    data=user_data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_data or entry.data,
            ),
            description_placeholders=DOCS_PLACEHOLDERS,
            errors=errors,
        )
