from enum import StrEnum

from pydantic import BaseModel, Field


class ScanMode(StrEnum):
    AUTO = "auto"
    COLOR = "color"
    GRAYSCALE = "grayscale"
    BLACK_WHITE = "black_white"
    ORIGINAL_ENHANCED = "original_enhanced"
    RECEIPT = "receipt"
    PHOTO = "photo"

class Corner(BaseModel):
    x: float = Field(..., description="Normalized x coordinate between 0.0 and 1.0")
    y: float = Field(..., description="Normalized y coordinate between 0.0 and 1.0")

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

class OrderedCorners(BaseModel):
    top_left: Corner
    top_right: Corner
    bottom_right: Corner
    bottom_left: Corner

    def to_list(self) -> list[tuple[float, float]]:
        return [
            self.top_left.to_tuple(),
            self.top_right.to_tuple(),
            self.bottom_right.to_tuple(),
            self.bottom_left.to_tuple(),
        ]

class ScanSettings(BaseModel):
    mode: ScanMode = ScanMode.AUTO

    # Advanced slider configurations (normalized controls)
    brightness: float = Field(0.0, ge=-1.0, le=1.0, description="Offset to brightness")
    contrast: float = Field(1.0, ge=0.0, le=3.0, description="Multiplier for contrast")
    white_level: float = Field(255.0, ge=128.0, le=255.0)
    black_level: float = Field(0.0, ge=0.0, le=127.0)
    shadow_removal_strength: float = Field(0.5, ge=0.0, le=1.0)
    background_cleanup_strength: float = Field(0.5, ge=0.0, le=1.0)
    denoising_strength: float = Field(0.0, ge=0.0, le=1.0)
    sharpening_amount: float = Field(0.0, ge=0.0, le=2.0)
    saturation: float = Field(1.0, ge=0.0, le=2.0)

    # Thresholding specific configurations
    adaptive_threshold_window_size: int = Field(25, ge=3, le=101, description="Must be an odd number")
    threshold_bias: float = Field(10.0, ge=-50.0, le=50.0)

    # Border & geometry settings
    border_removal: bool = Field(True)
    output_dpi: int = Field(300, ge=72, le=1200)
    paper_size: str | None = Field(None, description="e.g. A4, Letter, Legal, or custom")
    padding: float = Field(0.0, ge=0.0, le=10.0, description="Padding percentage")

class QualityReport(BaseModel):
    detection_confidence: float = Field(..., ge=0.0, le=1.0)
    blur_estimate: float = Field(..., description="Laplacian variance estimate")
    exposure_quality: float = Field(..., ge=0.0, le=1.0)
    highlight_clipping: float = Field(..., ge=0.0, le=1.0)
    shadow_severity: float = Field(..., ge=0.0, le=1.0)
    skew_angle: float = Field(..., description="Angle of residual skew in degrees")
    perspective_severity: float = Field(..., description="Perspective distortion measure")
    estimated_readable_resolution: str = Field(...)
    output_contrast: float = Field(...)
    potential_text_stroke_loss: bool = Field(False)
    possible_glare_or_occlusion: bool = Field(False)
    warnings: list[str] = Field(default_factory=list)
