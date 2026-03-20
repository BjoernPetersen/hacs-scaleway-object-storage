import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from botocore.exceptions import BotoCoreError
from homeassistant.components.backup import AgentBackup, BackupAgent, suggested_filename
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_BUCKET,
    CONF_OBJECT_PREFIX,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    MAX_PARALLEL_REQUESTS,
    MULTIPART_MIN_SIZE,
    MULTIPART_PART_SIZE,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable

    from types_aiobotocore_s3.type_defs import CompletedPartTypeDef

    from . import ScalewayConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[ScalewayConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    if not entries:
        _LOGGER.debug("No config entries loaded")
        return []

    return [ScalewayBackupAgent(hass, entry) for entry in entries]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed.

    :return: A function to unregister the listener.
    """
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)

    return remove_listener


class ScalewayBackupAgent(BackupAgent):
    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: ScalewayConfigEntry) -> None:
        super().__init__()
        self.name = entry.title
        self.unique_id = entry.entry_id

        self._hass = hass
        self._client = entry.runtime_data
        self._bucket = entry.data[CONF_BUCKET]
        self._prefix = entry.data[CONF_OBJECT_PREFIX]

    def _calculate_object_key(self, backup_id: str) -> str:
        prefix = self._prefix
        filename = f"home-assistant-backup-{backup_id}.tar"
        if prefix:
            return f"{prefix}{filename}"

        return filename

    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        key = self._calculate_object_key(backup_id)
        response = await self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].iter_chunks()

    # TODO: report progress in 2026.04
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Awaitable[AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        if backup.size < MULTIPART_MIN_SIZE:
            await self._upload_object(backup=backup, open_stream=open_stream)
        else:
            await self._upload_multipart_object(backup=backup, open_stream=open_stream)

    async def _upload_object(
        self,
        *,
        open_stream: Callable[[], Awaitable[AsyncIterator[bytes]]],
        backup: AgentBackup,
    ) -> None:
        key = self._calculate_object_key(backup.backup_id)
        stream = await open_stream()
        buffer = bytearray(backup.size)
        async for chunk in stream:
            buffer.extend(chunk)

        await self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Metadata={
                "backup_info": json.dumps(backup.as_dict()),
            },
            ContentDisposition=f'attachment; filename="{suggested_filename(backup)}"',
            Body=bytes(buffer),
        )

    @staticmethod
    async def _read_parts(stream: AsyncIterator[bytes]) -> AsyncGenerator[bytes]:
        buffer = bytearray()
        offset = 0

        async for chunk in stream:
            buffer.extend(chunk)
            with memoryview(buffer) as view:
                while len(buffer) - offset > MULTIPART_PART_SIZE:
                    end = offset + MULTIPART_PART_SIZE
                    part_bytes = view[offset:end]
                    yield part_bytes.tobytes()
                    offset = end

            if offset and offset >= MULTIPART_PART_SIZE:
                # compact buffer
                buffer = bytearray(buffer[offset:])
                offset = 0

        if offset < len(buffer):
            with memoryview(buffer) as view:
                yield view[offset:].tobytes()

    async def _upload_multipart_object(
        self,
        *,
        open_stream: Callable[[], Awaitable[AsyncIterator[bytes]]],
        backup: AgentBackup,
    ) -> None:
        client = self._client
        key = self._calculate_object_key(backup.backup_id)

        multipart_upload = await client.create_multipart_upload(
            Bucket=self._bucket,
            Key=key,
            Metadata={
                "backup_info": json.dumps(backup.as_dict()),
            },
            ContentDisposition=f'attachment; filename="{suggested_filename(backup)}"',
        )

        upload_id = multipart_upload["UploadId"]

        parts: list[CompletedPartTypeDef] = []
        try:
            stream = await open_stream()

            async for part_bytes in self._read_parts(stream):
                part_number = len(parts) + 1
                part = await client.upload_part(
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=part_bytes,
                )
                parts.append({"PartNumber": part_number, "ETag": part["ETag"]})
        except BotoCoreError as e:
            try:
                await client.abort_multipart_upload(
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id,
                )
            except BotoCoreError as nested_error:
                _LOGGER.error("Could not abort multipart upload", exc_info=nested_error)
            raise e

        await client.complete_multipart_upload(
            Bucket=self._bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        key = self._calculate_object_key(backup_id)
        await self._client.delete_object(Bucket=self._bucket, Key=key)

    async def _read_metadata(
        self, *, object_key: str, limiter: asyncio.Semaphore | None
    ) -> AgentBackup:
        limiter = limiter or asyncio.Semaphore()
        async with limiter:
            response = await self._client.head_object(
                Bucket=self._bucket, Key=object_key
            )
            meta = response["Metadata"]
            return AgentBackup.from_dict(json.loads(meta["backup_info"]))

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        client = self._client
        paginator = client.get_paginator("list_objects_v2")

        backups = []
        limiter = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

        async with asyncio.TaskGroup() as tg:
            async for page in paginator.paginate(
                Bucket=self._bucket, Prefix=self._prefix
            ):
                for item in page.get("Contents", []):
                    backups.append(
                        tg.create_task(
                            self._read_metadata(object_key=item["Key"], limiter=limiter)
                        )
                    )

        return [task.result() for task in backups]

    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        key = self._calculate_object_key(backup_id)
        return await self._read_metadata(object_key=key, limiter=None)
