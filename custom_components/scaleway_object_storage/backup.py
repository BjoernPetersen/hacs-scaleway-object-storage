import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from aiohttp_s3_client.client import MultipartUploader
from homeassistant.components.backup import AgentBackup, BackupAgent, suggested_filename
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_OBJECT_PREFIX,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    HEADER_CONTENT_DISPOSITION,
    HEADER_CONTENT_TYPE,
    HEADER_METADATA,
    MAX_PARALLEL_HEAD_REQUESTS,
    MAX_PARALLEL_UPLOADS,
    MULTIPART_MIN_SIZE,
    MULTIPART_PART_SIZE,
    TAR_CONTENT_TYPE,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable

    from aiohttp import StreamReader

    from . import ScalewayConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class Part:
    data: bytes
    digest: str

    @classmethod
    def from_data(cls, /, data: bytes) -> Self:
        return cls(
            data=data,
            digest=hashlib.sha256(data).hexdigest(),
        )


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
        self._prefix = entry.data[CONF_OBJECT_PREFIX]

    def _calculate_object_key(self, backup_id: str) -> str:
        prefix = self._prefix
        filename = f"home-assistant-backup-{backup_id}.tar"
        if prefix:
            return f"{prefix}{filename}"

        return filename

    @staticmethod
    async def _yield_chunks(response: StreamReader) -> AsyncGenerator[bytes]:
        async for chunk in response.iter_any():
            _LOGGER.debug("Got chunk of size %d", len(chunk))
            yield chunk

    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        key = self._calculate_object_key(backup_id)
        response = await self._client.get(
            object_name=key,
            raise_for_status=True,
        )
        # TODO: check response code
        return self._yield_chunks(response.content)

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

    @staticmethod
    def _create_headers(backup: AgentBackup) -> dict[str, str]:
        return {
            HEADER_CONTENT_DISPOSITION: f'attachment; filename="{suggested_filename(backup)}"',
            HEADER_CONTENT_TYPE: TAR_CONTENT_TYPE,
            HEADER_METADATA: json.dumps(backup.as_dict()),
        }

    async def _upload_object(
        self,
        *,
        open_stream: Callable[[], Awaitable[AsyncIterator[bytes]]],
        backup: AgentBackup,
    ) -> None:
        key = self._calculate_object_key(backup.backup_id)
        stream = await open_stream()
        await self._client.put(
            object_name=key,
            data=stream,
            headers=self._create_headers(backup),
            # TODO: proper error handling
            raise_for_status=True,
        )

    @staticmethod
    async def _read_parts(stream: AsyncIterator[bytes]) -> AsyncGenerator[Part]:
        buffer = bytearray()
        offset = 0

        async for chunk in stream:
            buffer.extend(chunk)
            with memoryview(buffer) as view:
                while len(buffer) - offset > MULTIPART_PART_SIZE:
                    end = offset + MULTIPART_PART_SIZE
                    part_bytes = view[offset:end]
                    yield Part.from_data(part_bytes.tobytes())
                    offset = end

            if offset and offset >= MULTIPART_PART_SIZE:
                # compact buffer
                buffer = bytearray(buffer[offset:])
                offset = 0

        if offset < len(buffer):
            with memoryview(buffer) as view:
                yield Part.from_data(view[offset:].tobytes())

    async def _upload_multipart_object(
        self,
        *,
        open_stream: Callable[[], Awaitable[AsyncIterator[bytes]]],
        backup: AgentBackup,
    ) -> None:
        client = self._client
        key = self._calculate_object_key(backup.backup_id)

        async with MultipartUploader(
            client, object_name=key, headers=self._create_headers(backup)
        ) as uploader:
            stream = await open_stream()

            limiter = asyncio.Semaphore(MAX_PARALLEL_UPLOADS)

            async def _perform_upload(upload_coro: Awaitable[None]) -> None:
                async with limiter:
                    await upload_coro

            async with asyncio.TaskGroup() as tg:
                async for part in self._read_parts(stream):
                    upload = uploader.put_part(
                        data=part.data,
                        content_sha256=part.digest,
                    )
                    tg.create_task(_perform_upload(upload))

    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        key = self._calculate_object_key(backup_id)
        await self._client.delete(object_name=key)

    async def _read_metadata(
        self, *, object_key: str, limiter: asyncio.Semaphore | None
    ) -> AgentBackup:
        limiter = limiter or asyncio.Semaphore()
        async with limiter:
            response = await self._client.head(object_name=object_key)
        meta = response.headers[HEADER_METADATA]
        return AgentBackup.from_dict(json.loads(meta))

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        client = self._client

        backups = []
        limiter = asyncio.Semaphore(MAX_PARALLEL_HEAD_REQUESTS)

        async with asyncio.TaskGroup() as tg:
            async for items, _ in client.list_objects_v2(prefix=self._prefix):
                for meta in items:
                    backups.append(
                        tg.create_task(
                            self._read_metadata(object_key=meta.key, limiter=limiter)
                        )
                    )

        return [task.result() for task in backups]

    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        key = self._calculate_object_key(backup_id)
        return await self._read_metadata(object_key=key, limiter=None)
