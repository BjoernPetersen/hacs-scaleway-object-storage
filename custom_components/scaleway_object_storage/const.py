from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.components.backup import BackupNotFound
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from collections.abc import Callable

DOMAIN: Final = "scaleway_object_storage"

CONF_SECTION_CREDENTIALS: Final = "credentials"
CONF_ACCESS_KEY_ID: Final = "access_key_id"
CONF_SECRET_KEY: Final = "secret_key"
CONF_BUCKET: Final = "bucket"
CONF_OBJECT_PREFIX: Final = "object_prefix"

DOCS_PLACEHOLDERS: Final = {
    "api_key_docs": "https://www.scaleway.com/docs/iam/api-cli/using-api-key-object-storage/",
    "bucket_docs": "https://www.scaleway.com/docs/object-storage/how-to/create-a-bucket/",
}

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

MAX_PARALLEL_HEAD_REQUESTS: Final[int] = 8
MAX_PARALLEL_UPLOADS: Final[int] = 4

MULTIPART_MIN_SIZE: Final[int] = 50 * 2**20
MULTIPART_PART_SIZE: Final[int] = 32 * 2**20

HEADER_METADATA: Final[str] = "x-amz-meta-backup-info"
HEADER_CONTENT_DISPOSITION: Final[str] = "Content-Disposition"
HEADER_CONTENT_TYPE: Final[str] = "Content-Type"
TAR_CONTENT_TYPE: Final[str] = "application/x-tar"


class ErrorCode(StrEnum):
    UNKNOWN = "unknown"
    INVALID_AUTH = "invalid_auth"
    INVALID_BUCKET_NAME = "invalid_bucket_name"
    SERVER_ERROR = "server_error"
    CONNECTION_ERROR = "cannot_connect"
    BACKUP_NOT_FOUND = BackupNotFound.error_code
