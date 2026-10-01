import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Document(Base):
    __tablename__ = "documents"

    # Also the file's name on disk: uploads/<workspace_id>/<id>
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    # Kept (as empty) if the uploader's account is deleted, so a shared
    # workspace does not lose its documents.
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # The original name, for display only. Never used as a path.
    filename: Mapped[str] = mapped_column(String(255))
    # Decided by our own check of the file, not by what the sender claimed.
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
