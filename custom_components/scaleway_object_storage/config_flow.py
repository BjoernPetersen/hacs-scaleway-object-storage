from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
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
    CONF_REGION,
    CONF_SECRET_KEY,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
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
    async def _test_connection(
        self,
        *,
        errors: dict[str, str],
        config: dict[str, Any],
    ) -> bool:
        async with await helpers.create_client(config) as client:
            error_code = await helpers.check_connection(client, config)
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
                }
            )

            if await self._test_connection(errors=errors, config=user_input):
                return self.async_create_entry(
                    title=f"Scaleway - {user_input[CONF_BUCKET]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
