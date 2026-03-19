from typing import Any

from aiobotocore.session import AioSession

from scaleway_object_storage.const import (
    CONF_REGION,
    CONF_ACCESS_KEY,
    CONF_SECRET_KEY,
)


def create_client(config: dict[str, Any]):
    session = AioSession()
    region = config[CONF_REGION]
    endpoint_url = f"https://s3.{region}.scw.cloud"
    return session.create_client(
        service_name="s3",
        use_ssl=True,
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=config[CONF_ACCESS_KEY],
        aws_secret_access_key=config[CONF_SECRET_KEY],
    )
