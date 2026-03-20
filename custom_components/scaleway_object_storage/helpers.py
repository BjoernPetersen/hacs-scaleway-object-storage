import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from aiohttp import ClientConnectionError, ClientSession, InvalidURL
from aiohttp_s3_client import S3Client

if TYPE_CHECKING:
    from collections.abc import Mapping


from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_REGION,
    CONF_SECRET_KEY,
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

    return S3Client(
        session=session,
        url=endpoint_url,
        access_key_id=config[CONF_ACCESS_KEY_ID],
        secret_access_key=config[CONF_SECRET_KEY],
        region=region,
    )


async def check_connection(
    session: ClientSession,
    config: Mapping[str, Any],
) -> str | None:
    client = create_client(session, config, bucket_scoped=False)
    try:
        response = await client.head(object_name=config[CONF_BUCKET])
    except ClientConnectionError:
        return "cannot_connect"
    except InvalidURL as e:
        _LOGGER.warning("Invalid URL: %s", e.url, exc_info=e)
        return "invalid_bucket_name"

    if response.status == HTTPStatus.OK:
        return None

    _LOGGER.error("Received status code %d for bucket access", response.status)

    if response.status in [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN]:
        return "invalid_auth"

    if 500 <= response.status < 600:
        return "server_error"

    return "unknown"
