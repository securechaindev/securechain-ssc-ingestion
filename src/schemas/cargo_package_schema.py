from datetime import datetime

from pydantic import BaseModel, Field


class CargoPackageSchema(BaseModel):
    name: str = Field(..., description="Name of the Cargo package (crate)")
    vendor: str = Field(default="n/a", description="Vendor source")
    repository_url: str = Field(
        default="n/a", description="Repository URL (GitHub/GitLab/Bitbucket)"
    )
    moment: datetime = Field(
        default_factory=datetime.now, description="Timestamp of the last update"
    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "repository_url": self.repository_url,
            "moment": self.moment,
        }
