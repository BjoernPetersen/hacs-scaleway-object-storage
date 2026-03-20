import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    from aiobotocore.session import ClientCreatorContext
    from types_aiobotocore_s3.client import S3Client

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_REGION,
    CONF_SECRET_KEY,
)

_LOGGER = logging.getLogger(__name__)


async def create_client(config: Mapping[str, Any]) -> ClientCreatorContext[S3Client]:
    try:
        from aiobotocore.session import AioSession
    except ImportError:
        _LOGGER.warning("aiobotocore import failed (attempt #1)")
        await asyncio.sleep(10)

    from aiobotocore.session import AioSession

    session = AioSession()
    region = config[CONF_REGION]
    endpoint_url = f"https://s3.{region}.scw.cloud"

    def _create_client() -> ClientCreatorContext[S3Client]:
        return session.create_client(
            service_name="s3",
            use_ssl=True,
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=config[CONF_ACCESS_KEY_ID],
            aws_secret_access_key=config[CONF_SECRET_KEY],
        )

    # Client creation is doing blocking calls, so we run it in a thread pool...
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _create_client)


async def check_connection(client: S3Client, config: Mapping[str, Any]) -> str | None:
    from botocore.exceptions import ClientError, ConnectionError, ParamValidationError

    try:
        await client.head_bucket(Bucket=config[CONF_BUCKET])
    except ClientError:
        return "invalid_auth"
    except ParamValidationError as e:
        if "Invalid bucket name" in str(e):
            return "invalid_bucket_name"
        return "validation_failed"
    except ConnectionError:
        return "cannot_connect"
    else:
        return None
