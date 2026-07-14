from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CommandError(BaseModel):
    code: str
    message: str


class CommandEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    command: str
    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: CommandError | None = None
