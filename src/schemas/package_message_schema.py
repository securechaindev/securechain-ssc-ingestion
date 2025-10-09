from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class PackageMessageSchema(BaseModel):
    node_type: str = Field(..., description="Package manager (e.g., PyPIPackage, NPMPackage, ...)")
    package: str = Field(..., description="Package name")
    vendor: str = Field("n/a", description="Package vendor")
    repository_url: HttpUrl | None = Field(default=None, description="Repository URL")
    moment: datetime = Field(default_factory=datetime.now)
    constraints: str | None = None
    parent_id: str | None = None
    parent_version: str | None = None
    refresh: bool = False
