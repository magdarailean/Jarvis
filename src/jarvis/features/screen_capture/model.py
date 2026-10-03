"""Framework-independent image payload and coordinate mapping."""

from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class ScreenGeometry:
    monitor_name: str
    left: int
    top: int
    logical_width: int
    logical_height: int
    pixel_width: int
    pixel_height: int
    device_pixel_ratio: float

    def __post_init__(self) -> None:
        for value in (self.logical_width, self.logical_height, self.pixel_width, self.pixel_height):
            if type(value) is not int or value <= 0:
                raise ValueError("Screen dimensions must be positive integers")
        if not math.isfinite(self.device_pixel_ratio) or self.device_pixel_ratio <= 0:
            raise ValueError("Invalid device pixel ratio")

    def pixel_to_normalized(self, x: float, y: float) -> tuple[float, float]:
        """Image-edge coordinates; use actual pixels, not rounded logical size × DPR."""
        if not (math.isfinite(x) and math.isfinite(y)
                and 0 <= x <= self.pixel_width and 0 <= y <= self.pixel_height):
            raise ValueError("Point is outside the captured image")
        return x / self.pixel_width, y / self.pixel_height

    def normalized_to_desktop(self, x: float, y: float) -> tuple[float, float]:
        """Qt logical desktop coordinates, including negative monitor origins."""
        if not (math.isfinite(x) and math.isfinite(y) and 0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("Point must be normalized")
        return self.left + x * self.logical_width, self.top + y * self.logical_height


@dataclass(frozen=True)
class ScreenFrame:
    id: str
    captured_at: str
    geometry: ScreenGeometry
    png: bytes = field(repr=False)
