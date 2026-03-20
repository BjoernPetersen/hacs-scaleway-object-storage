import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from aiohttp import ClientConnectionError, ClientSession, InvalidURL
from aiohttp_s3_client import S3Client
from homeassistant.exceptions import ConfigEntryAuthFailed

if TYPE_CHECKING:
    from collections.abc import Mapping


from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_REGION,
    CONF_SECRET_KEY,
    CONF_SECTION_CREDENTIALS,
    ErrorCode,
)

_LOGGER = logging.getLogger(__name__)


def create_client(
    session: ClientSession,
    config: Mapping[str, Any],
    bucket_scoped: bool = True,
) -> S3Client:
    region = config[CONF_REGION]
    if bucket_scoped:
        endpoint_url = f"https://{config[CONF_BUCKET]}.s3.{region}.scw.cloud"
    else:
        endpoint_url = f"https://s3.{region}.scw.cloud"

    if CONF_SECTION_CREDENTIALS not in config:
        # TODO: remove
        raise ConfigEntryAuthFailed()

    credentials = config[CONF_SECTION_CREDENTIALS]

    return S3Client(
        session=session,
        url=endpoint_url,
        access_key_id=credentials[CONF_ACCESS_KEY_ID],
        secret_access_key=credentials[CONF_SECRET_KEY],
        region=region,
    )


async def check_connection(
    session: ClientSession,
    config: Mapping[str, Any],
) -> ErrorCode | None:
    client = create_client(session, config, bucket_scoped=False)
    try:
        response = await client.head(object_name=config[CONF_BUCKET])
    except ClientConnectionError:
        return ErrorCode.CONNECTION_ERROR
    except InvalidURL as e:
        _LOGGER.info("Invalid URL: %s", e.url, exc_info=e)
        return ErrorCode.INVALID_BUCKET_NAME

    if response.status == HTTPStatus.OK:
        return None

    if response.status in [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN]:
        _LOGGER.info("Received status code %d, indicating auth issue", response.status)
        return ErrorCode.INVALID_AUTH

    if 500 <= response.status < 600:
        _LOGGER.warning("Received server error code %d", response.status)
        return ErrorCode.SERVER_ERROR

    _LOGGER.error("Received unexpected status code %d", response.status)
    return ErrorCode.UNKNOWN
