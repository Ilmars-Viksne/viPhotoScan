
from pydantic import BaseModel, Field

from photoscan.domain.models import OrderedCorners, ScanSettings


class PageProjectSettings(BaseModel):
    id: str = Field(..., description="Unique page ID")
    source_path: str = Field(..., description="Relative or absolute path to source image")
    checksum: str | None = Field(None, description="SHA256 checksum of source image")
    corners: OrderedCorners | None = Field(None, description="Current set of crop/perspective corners")
    rotation: int = Field(0, description="Page rotation angle: 0, 90, 180, 270")
    settings: ScanSettings = Field(default_factory=ScanSettings)
    label: str | None = Field(None, description="User-visible page label")

class ProjectModel(BaseModel):
    schema_version: str = Field("1.0.0")
    app_version: str = Field("0.1.0")
    export_dpi: int = Field(300, ge=72, le=1200)
    export_format: str = Field("PDF")
    pages: list[PageProjectSettings] = Field(default_factory=list)
