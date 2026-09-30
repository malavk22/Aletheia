import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings

CHUNK_SIZE = 1024 * 1024  # read 1 MB at a time


class FileTooLarge(Exception):
    pass


def document_path(workspace_id: uuid.UUID, document_id: uuid.UUID) -> Path:
    # Built only from ids we generated, never from the uploaded filename, so a
    # name like "../../evil.pdf" cannot place a file outside the upload folder.
    return Path(settings.upload_dir) / str(workspace_id) / str(document_id)


def save_file(source: BinaryIO, destination: Path) -> int:
    """Copy `source` to `destination` and return its size in bytes.

    Stops with FileTooLarge as soon as the size limit is passed, and leaves
    nothing on disk if anything goes wrong.
    """
    limit = settings.max_upload_mb * 1024 * 1024
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with destination.open("wb") as target:
            while chunk := source.read(CHUNK_SIZE):
                size += len(chunk)
                if size > limit:
                    raise FileTooLarge
                target.write(chunk)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return size
