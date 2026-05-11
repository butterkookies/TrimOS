"""
Earth — rotating ASCII Earth for TrimOS mascot panel.

Software-rendered sphere via ray casting (donut.c style).
No external libs, no assets, no pre-rendered frames.
Procedural continents, day/night shading, cloud layer, star field.
State → rotation speed mapping preserves app.py API.
"""

import math
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text


# ── Constants ─────────────────────────────────────────────────────────────────

_SHADE   = ' .,-~:;=!*#$@'          # luminance ramp, dark → bright
_SHADE_N = len(_SHADE) - 1

_TILT_RAD = math.radians(23.5)      # Earth axis tilt
_COS_TILT = math.cos(_TILT_RAD)
_SIN_TILT = math.sin(_TILT_RAD)

# Sun direction (world space, normalized) — upper-right, toward viewer side
_LX, _LY, _LZ = 0.588, 0.392, -0.706   # already unit length ≈ 1

_CAM_Z = -2.5                        # camera Z position
_VIEW_SCALE = 1.5                    # >1 = wider FOV → sphere appears smaller

# State → Y-axis spin speed (radians per frame at 20 fps)
_SPEED: dict[str, float] = {
    "idle":       0.022,
    "scanning":   0.055,
    "optimized":  0.018,
    "stressed":   0.075,
    "optimizing": 0.050,
}

_STATE_COLOR: dict[str, str] = {
    "idle":       "#00d4ff",
    "scanning":   "#ffaa00",
    "optimized":  "#00cc66",
    "stressed":   "#ff4466",
    "optimizing": "#cc66ff",
}

_STATE_LABEL: dict[str, str] = {
    "idle":       "Earth",
    "scanning":   "scanning...",
    "optimized":  "✔ clean!",
    "stressed":   "!! help !!",
    "optimizing": "working...",
}


# ── Procedural texture ────────────────────────────────────────────────────────

def _is_land(lat: float, lon: float) -> bool:
    """Rough continent check. lat/lon in degrees."""
    # North America
    if -170 < lon < -50 and 15 < lat < 75:
        return True
    # South America
    if -82 < lon < -34 and -56 < lat < 13:
        return True
    # Europe
    if -10 < lon < 40 and 35 < lat < 71:
        return True
    # Africa
    if -18 < lon < 52 and -35 < lat < 37:
        return True
    # Asia (main body)
    if 26 < lon < 145 and 0 < lat < 77:
        return True
    # SE Asia + Indonesia
    if 95 < lon < 141 and -8 < lat < 20:
        return True
    # Australia
    if 113 < lon < 154 and -44 < lat < -10:
        return True
    # Greenland
    if -57 < lon < -16 and 59 < lat < 84:
        return True
    # Antarctica
    if lat < -65:
        return True
    return False


def _cloud(lat_d: float, lon_d: float, offset_d: float) -> float:
    """Cloud opacity 0–1 at surface point. offset_d = cloud rotation offset."""
    s = lon_d + offset_d
    v = (
        math.sin(math.radians(s * 3.1 + lat_d * 1.8))
        * math.cos(math.radians(lat_d * 1.4))
        * math.sin(math.radians(s * 1.7 - lat_d * 0.9))
    )
    return max(0.0, v * 0.55)


# ── Renderer ──────────────────────────────────────────────────────────────────

def _render(width: int, height: int, rot_y: float, cloud_offset: float) -> str:
    """
    Ray-cast unit sphere onto (width × height) grid.
    Returns newline-joined ASCII string.
    """
    # Precompute per-frame values
    cos_y =  math.cos(rot_y)
    sin_y =  math.sin(rot_y)
    # Inverse Y rotation coefficients (for texture lookup)
    inv_cos_y =  cos_y   # cos(-rot_y) = cos(rot_y)
    inv_sin_y = -sin_y   # sin(-rot_y) = -sin(rot_y)

    # Precompute inverse tilt (constant each frame)
    # Inverse Rx(tilt): Rx(-tilt) has +sin, -sin swapped
    cos_t =  _COS_TILT
    sin_t = -_SIN_TILT   # inverse

    half_w  = width  / 2.0
    half_h  = height / 2.0
    inv_hw  = 1.0 / half_w
    inv_hh  = 1.0 / half_h
    # Terminal chars are ~2× taller than wide; compensate so sphere looks round
    aspect  = 0.45

    cloud_deg = math.degrees(cloud_offset) % 360.0

    shade   = _SHADE
    shade_n = _SHADE_N
    lx, ly, lz = _LX, _LY, _LZ
    cam_z   = _CAM_Z

    rows: list[str] = []
    for j in range(height):
        sy = (j - half_h) * inv_hh * _VIEW_SCALE
        row: list[str] = []
        for i in range(width):
            sx = (i - half_w) * inv_hw * aspect * _VIEW_SCALE

            # ── Ray direction (from camera toward pixel) ──────────────────
            rdz = -cam_z          # = 2.5 (toward +z)
            rlen_inv = 1.0 / math.sqrt(sx*sx + sy*sy + rdz*rdz)
            rdx = sx  * rlen_inv
            rdy = sy  * rlen_inv
            rdz = rdz * rlen_inv

            # ── Ray-sphere intersection (unit sphere @ origin) ────────────
            # Ray: P(t) = cam + t*rd,  cam = (0, 0, cam_z)
            # |P|² = 1  →  t² + 2(cam·rd)t + (|cam|²-1) = 0
            b    = cam_z * rdz                    # cam·rd (only z nonzero)
            disc = b*b - (cam_z*cam_z - 1.0)     # |cam|²=cam_z²

            if disc < 0.0:
                # Background — deterministic star field
                h = (i * 2531 + j * 5381) & 0xFFFF
                row.append('.' if h < 700 else ' ')
                continue

            t  = -b - math.sqrt(disc)
            if t < 0.0:
                row.append(' ')
                continue

            # ── Surface normal (= hit point on unit sphere) ───────────────
            nx = rdx * t
            ny = rdy * t
            nz = cam_z + rdz * t

            # ── Diffuse lighting (world-space normal) ─────────────────────
            light = nx*lx + ny*ly + nz*lz
            if light < 0.0:
                light = 0.0

            # ── Inverse-rotate normal → texture (lat/lon) space ──────────
            # Step 1: inverse Y spin
            tx =  inv_cos_y * nx + inv_sin_y * nz   # note sign of inv_sin_y
            ty =  ny
            tz = -inv_sin_y * nx + inv_cos_y * nz   # = sin_y*nx + cos_y*nz

            # Step 2: inverse axis tilt (Rx with -tilt → swap sin signs)
            sx2 =  tx
            sy2 =  cos_t * ty + sin_t * tz
            sz2 = -sin_t * ty + cos_t * tz

            # ── Spherical coords ──────────────────────────────────────────
            lat_r = math.asin(max(-1.0, min(1.0, sy2)))
            lon_r = math.atan2(sz2, sx2)
            lat_d = math.degrees(lat_r)
            lon_d = math.degrees(lon_r)

            # ── Surface brightness ────────────────────────────────────────
            land = _is_land(lat_d, lon_d)
            if land:
                brightness = 0.12 + light * 0.88
            else:
                brightness = 0.04 + light * 0.62

            # ── Cloud layer ───────────────────────────────────────────────
            cld = _cloud(lat_d, lon_d, cloud_deg)
            brightness += cld * (1.0 - brightness) * 0.38

            # ── Map to ASCII ──────────────────────────────────────────────
            idx = int(max(0.0, min(1.0, brightness)) * shade_n)
            row.append(shade[idx])

        rows.append(''.join(row))

    return '\n'.join(rows)


# ── Textual Widget ────────────────────────────────────────────────────────────

class Mascot(Widget):
    """Rotating ASCII Earth — replaces character mascot, same set_state() API."""

    DEFAULT_CSS = """
    Mascot {
        width: 100%;
        height: 100%;
        content-align: center middle;
        background: transparent;
    }
    """

    state = reactive("idle")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._timer      = None
        self._rot_y      = 0.0
        self._cloud_off  = 0.0
        self._speed      = _SPEED["idle"]
        self._frame      = ""

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 20, self._tick)

    def _tick(self) -> None:
        self._rot_y     = (self._rot_y     + self._speed)       % (2 * math.pi)
        self._cloud_off = (self._cloud_off + self._speed * 0.35) % (2 * math.pi)

        w = self.size.width
        h = self.size.height - 1    # reserve bottom row for label
        if w > 4 and h > 2:
            self._frame = _render(w, h, self._rot_y, self._cloud_off)

        self.refresh()

    def watch_state(self, new_state: str) -> None:
        self._speed = _SPEED.get(new_state, _SPEED["idle"])

    def render(self) -> Text:
        color = _STATE_COLOR.get(self.state, "#e0e0e0")
        label = _STATE_LABEL.get(self.state, self.state)

        text = Text()
        if self._frame:
            text.append(self._frame, style=f"bold {color}")
        text.append(f"\n  {label}", style=f"dim {color}")
        return text

    def set_state(self, state: str) -> None:
        """Public API — same signature as original mascot."""
        if state in _SPEED:
            self.state = state
