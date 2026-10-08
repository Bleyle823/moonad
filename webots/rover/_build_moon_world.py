"""Build rover/worlds/moon.wbt: demo far terrain + uneven local mare, craters, rocks."""
from __future__ import annotations

import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLE = Path(
    r"C:\Users\Omen\Desktop\webots-master\projects\samples\demos\worlds\moon.wbt"
)
DEST = ROOT / "worlds" / "moon.wbt"

SPAWN_X, SPAWN_Y = -2.35, -0.7
SIZE = 36.0
N = 73  # ~0.5 m cells so ripples and crater rims show up
HALF = SIZE / 2.0
SPACING = SIZE / (N - 1)

CRATERS = [
    # cx, cy, radius, depth
    (6.2, 4.1, 2.15, 0.48),
    (-8.4, 5.6, 1.55, 0.32),
    (4.8, -8.2, 1.35, 0.28),
    (-10.6, -6.1, 2.55, 0.55),
    (11.4, -2.4, 1.05, 0.22),
    (-5.2, 11.0, 1.75, 0.36),
    (8.6, 10.2, 0.85, 0.18),
    (0.4, 8.3, 1.25, 0.26),
    (-12.2, 1.8, 1.45, 0.30),
    (10.8, -12.0, 1.95, 0.40),
    (2.2, 2.8, 0.55, 0.12),
    (-4.1, -3.6, 0.70, 0.16),
    (7.1, -5.5, 0.48, 0.11),
    (-7.8, -1.2, 0.62, 0.14),
    (13.5, 6.4, 1.15, 0.24),
    (-1.8, -11.4, 0.90, 0.20),
    (14.0, 12.5, 1.60, 0.34),
    (-13.5, 9.5, 0.75, 0.16),
    (1.5, -14.0, 1.40, 0.28),
    (-14.2, -11.8, 1.10, 0.22),
]


def _hash12(ix: int, iy: int) -> float:
    n = math.sin(ix * 127.1 + iy * 311.7 + 19.19) * 43758.5453
    return n - math.floor(n)


def _value_noise(x: float, y: float) -> float:
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = x - x0, y - y0
    u = fx * fx * (3.0 - 2.0 * fx)
    v = fy * fy * (3.0 - 2.0 * fy)
    n00 = _hash12(x0, y0)
    n10 = _hash12(x0 + 1, y0)
    n01 = _hash12(x0, y0 + 1)
    n11 = _hash12(x0 + 1, y0 + 1)
    return (n00 * (1.0 - u) + n10 * u) * (1.0 - v) + (n01 * (1.0 - u) + n11 * u) * v


def _fbm(x: float, y: float, octaves: int = 6) -> float:
    total = 0.0
    amp = 1.0
    freq = 0.11
    norm = 0.0
    for i in range(octaves):
        total += amp * _value_noise(x * freq + 4.2 * (i + 1), y * freq - 1.7)
        norm += amp
        amp *= 0.55
        freq *= 2.11
    return total / norm


def _ridge(x: float, y: float) -> float:
    n = abs(_fbm(x, y, octaves=4) * 2.0 - 1.0)
    return 1.0 - n


def height(x: float, y: float) -> float:
    h = 0.55 * (_fbm(x, y) - 0.5)
    h += 0.22 * (_ridge(x * 0.85, y * 0.85) - 0.45)
    h += 0.12 * (_value_noise(x * 0.55, y * 0.55) - 0.5)
    h += 0.07 * (_value_noise(x * 1.9 + 9.0, y * 1.9) - 0.5)
    h += 0.04 * (_value_noise(x * 4.6 - 2.0, y * 4.6 + 1.4) - 0.5)
    for cx, cy, radius, depth in CRATERS:
        dx, dy = x - cx, y - cy
        r = math.hypot(dx, dy)
        if r > radius * 1.55:
            continue
        t = r / radius
        if t < 1.0:
            bowl = (1.0 - t * t) ** 2
            h -= depth * bowl
        rim = math.exp(-((r - radius) / (0.18 * radius)) ** 2)
        h += depth * 0.45 * rim
    ds = math.hypot(x - SPAWN_X, y - SPAWN_Y)
    if ds < 1.8:
        w = 1.0 - (ds / 1.8) ** 2
        h *= 1.0 - 0.55 * w
    return h


def _grid_xy(i: int, j: int) -> tuple[float, float]:
    return -HALF + i * SPACING, -HALF + j * SPACING


def _build_local_ifs() -> str:
    points = []
    uvs = []
    for j in range(N):
        for i in range(N):
            x, y = _grid_xy(i, j)
            z = height(x, y)
            points.append(f"{x:.4f} {y:.4f} {z:.4f}")
            uvs.append(f"{-x / 8.0:.4f} {y / 8.0:.4f}")
    tris = []
    for j in range(N - 1):
        for i in range(N - 1):
            a = j * N + i
            b = a + 1
            c = a + N
            d = c + 1
            tris.append(f"{a}, {b}, {d}, {c}, -1")
    point_txt = ", ".join(points)
    uv_txt = ", ".join(uvs)
    idx_txt = ", ".join(tris)
    return f"""DEF LOCAL_MARE Shape {{
      appearance PBRAppearance {{
        baseColor 0.72 0.71 0.68
        baseColorMap ImageTexture {{
          url [ "textures/moon/moon_ground.jpg" ]
        }}
        roughness 1
        metalness 0
      }}
      geometry IndexedFaceSet {{
        creaseAngle 1.4
        coord Coordinate {{
          point [
            {point_txt}
          ]
        }}
        texCoord TextureCoordinate {{
          point [
            {uv_txt}
          ]
        }}
        coordIndex [
          {idx_txt}
        ]
        texCoordIndex [
          {idx_txt}
        ]
      }}
    }}"""


def _elevation_collider() -> str:
    cn = 41
    step = SIZE / (cn - 1)
    heights = []
    for j in range(cn):
        for i in range(cn):
            wx = -HALF + i * step
            wy = -HALF + j * step
            heights.append(f"{height(wx, wy):.4f}")
    htxt = ", ".join(heights)
    return f"""Pose {{
    translation {-HALF:.4f} {-HALF:.4f} 0
    children [
      ElevationGrid {{
        xDimension {cn}
        yDimension {cn}
        xSpacing {step:.4f}
        ySpacing {step:.4f}
        height [ {htxt} ]
      }}
    ]
  }}"""


# Compact lunar rock (flat underside), from Webots Rock.proto "regular" hull, Z-up.
_ROCK_POINTS = (
    "0.0283 -0.0123 0.0494, 0.0515 0.0517 0.0471, 0.0213 0.0450 0.0468, "
    "0.0608 0.0574 0.0325, -0.0161 0.0464 0.0210, -0.0175 0.0004 0.0295, "
    "0.0659 0.0077 -0.0015, 0.0296 -0.0428 0.0261, -0.0213 -0.0406 0.0249, "
    "0.0576 -0.0247 0.0051, 0.0346 0.0554 0.0064, -0.0625 -0.0035 0.0255, "
    "0.0046 -0.0540 -0.0394, -0.0445 -0.0316 0.0104, -0.0316 -0.0461 -0.0521, "
    "0.0382 -0.0188 -0.0490, -0.0555 -0.0468 -0.0379, -0.0019 0.0426 -0.0396, "
    "-0.0668 -0.0031 -0.0295, -0.0360 -0.0154 -0.0562, -0.0385 0.0333 -0.0195"
)
_ROCK_INDEX = (
    "2 0 1 -1 1 0 3 -1 4 0 2 -1 0 4 5 -1 3 0 6 -1 7 0 5 -1 6 0 7 -1 "
    "8 7 5 -1 6 7 9 -1 10 3 6 -1 11 5 4 -1 11 8 5 -1 12 7 8 -1 12 9 7 -1 "
    "6 9 12 -1 13 8 11 -1 14 12 8 -1 15 6 12 -1 15 10 6 -1 13 11 16 -1 "
    "16 8 13 -1 14 8 16 -1 15 12 14 -1 10 15 17 -1 18 11 4 -1 16 11 18 -1 "
    "14 16 19 -1 15 14 19 -1 19 16 18 -1 19 17 15 -1 18 20 19 -1 17 19 20 -1 "
    "4 20 18 -1 4 17 20 -1 4 10 17 -1 2 10 4 -1 1 3 10 -1 1 10 2 -1"
)


def _scaled_rock_points(scale: float) -> str:
    parts = []
    for trip in _ROCK_POINTS.split(","):
        nums = trip.split()
        if len(nums) != 3:
            continue
        x, y, z = (float(v) * scale for v in nums)
        parts.append(f"{x:.4f} {y:.4f} {z:.4f}")
    return ", ".join(parts)


def _rock_solid(name: str, x: float, y: float, scale: float, yaw: float, color: str, define: bool = False) -> str:
    del define
    z = height(x, y) + 0.055 * scale
    pts = _scaled_rock_points(scale)
    return f"""Solid {{
  translation {x:.3f} {y:.3f} {z:.3f}
  rotation 0 0 1 {yaw:.3f}
  name "{name}"
  recognitionColors [ {color} ]
  contactMaterial "regolith"
  children [
    Shape {{
      appearance PBRAppearance {{
        baseColor {color}
        baseColorMap ImageTexture {{ url [ "textures/rock.jpg" ] }}
        roughness 1
        metalness 0
      }}
      geometry IndexedFaceSet {{
        coord Coordinate {{ point [ {pts} ] }}
        coordIndex [ {_ROCK_INDEX} ]
        creaseAngle 0.6
      }}
    }}
  ]
  boundingObject Sphere {{ radius {0.07 * scale:.3f} }}
  locked TRUE
}}
"""


def _pebble_shape(x: float, y: float, radius: float, color: str) -> str:
    z = height(x, y) + radius * 0.55
    return f"""    Pose {{
      translation {x:.3f} {y:.3f} {z:.3f}
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor {color}
            roughness 1
            metalness 0
          }}
          geometry Sphere {{ radius {radius:.3f} subdivision 1 }}
        }}
      ]
    }}"""


def _scatter() -> str:
    rng = random.Random(42)
    chunks = []
    occupied = [(SPAWN_X, SPAWN_Y, 2.4)]

    def free(x, y, rad):
        if abs(x) > HALF - 1.2 or abs(y) > HALF - 1.2:
            return False
        for ox, oy, orad in occupied:
            if math.hypot(x - ox, y - oy) < rad + orad:
                return False
        return True

    palettes = [
        "0.48 0.46 0.43",
        "0.42 0.41 0.38",
        "0.55 0.53 0.49",
        "0.38 0.37 0.35",
        "0.50 0.47 0.43",
    ]

    n = 0
    first = True
    placements = []
    for _ in range(10):
        for _try in range(40):
            x = rng.uniform(-HALF + 2, HALF - 2)
            y = rng.uniform(-HALF + 2, HALF - 2)
            sc = rng.uniform(2.4, 4.8)
            if free(x, y, 0.55 * sc):
                occupied.append((x, y, 0.5 * sc))
                placements.append((f"boulder_{n}", x, y, sc))
                n += 1
                break
    for _ in range(22):
        for _try in range(40):
            x = rng.uniform(-HALF + 1.5, HALF - 1.5)
            y = rng.uniform(-HALF + 1.5, HALF - 1.5)
            sc = rng.uniform(1.1, 2.2)
            if free(x, y, 0.28 * sc):
                occupied.append((x, y, 0.25 * sc))
                placements.append((f"rock_{n}", x, y, sc))
                n += 1
                break
    for ci, (cx, cy, radius, _d) in enumerate(CRATERS):
        if radius < 1.0:
            continue
        k = 4 + int(radius)
        for k_i in range(k):
            ang = k_i * 6.28 / k + rng.uniform(-0.2, 0.2)
            rr = radius * rng.uniform(0.92, 1.18)
            x = cx + math.cos(ang) * rr
            y = cy + math.sin(ang) * rr
            sc = rng.uniform(0.7, 1.4)
            if free(x, y, 0.18):
                occupied.append((x, y, 0.16))
                placements.append((f"ejecta_{ci}_{k_i}", x, y, sc))
    for name, x, y, sc in placements:
        chunks.append(
            _rock_solid(name, x, y, sc, rng.uniform(0, 6.28), rng.choice(palettes), define=first)
        )
        first = False
    pebble_shapes = []
    for _ in range(70):
        x = rng.uniform(-HALF + 1, HALF - 1)
        y = rng.uniform(-HALF + 1, HALF - 1)
        if not free(x, y, 0.12):
            continue
        occupied.append((x, y, 0.08))
        pebble_shapes.append(
            _pebble_shape(x, y, rng.uniform(0.03, 0.08), rng.choice(palettes))
        )
    chunks.append(
        "Solid {\n  name \"pebbles\"\n  children [\n"
        + "\n".join(pebble_shapes)
        + "\n  ]\n  locked TRUE\n}\n"
    )
    return "\n".join(chunks)


src = SAMPLE.read_text(encoding="utf-8")
start = src.index("DEF GROUND Shape {")
end = src.index("DEF EARTH")
ground = src[start:end].rstrip() + "\n"
ground = ground.replace(
    '"webots://projects/samples/demos/worlds/textures/moon/moon_ground.jpg"',
    '"textures/moon/moon_ground.jpg"',
)
ground = ground.replace(
    "DEF GROUND Shape {",
    "DEF GROUND Shape {\n  castShadows FALSE",
    1,
)
far_ground = "\n".join(("    " + line if line else line) for line in ground.splitlines())

local_visual = _build_local_ifs()
local_visual_indented = "\n".join(
    ("    " + line if line else line) for line in local_visual.splitlines()
)

header = """#VRML_SIM R2025a utf8

EXTERNPROTO "../protos/Sawppy.proto"

WorldInfo {
  title "Sawppy on the Moon"
  info [
    "Uneven mare, miniature craters, rocks and pebbles on the official moon_ground terrain."
    "urdf2webots Sawppy (ENU). Click the 3D view, then w/a/s/d/x."
  ]
  gravity 1.62
  basicTimeStep 16
  lineScale 0.2
  coordinateSystem "ENU"
  contactProperties [
    ContactProperties {
      material1 "wheel"
      material2 "regolith"
      coulombFriction 1.4
      bounce 0
      softERP 0.8
      softCFM 1e-5
      maxContactJoints 8
    }
  ]
}
Viewpoint {
  orientation 0.02 -0.013 -0.9997 2.42
  position 1.92 3.48 0.9
  near 0.1
  follow "Sawppy"
}
Background {
  skyColor [ 0 0 0 ]
  luminosity 1
  backIrradianceUrl [ "textures/sky/empty_office_back.hdr" ]
  bottomIrradianceUrl [ "textures/sky/empty_office_bottom.hdr" ]
  frontIrradianceUrl [ "textures/sky/empty_office_front.hdr" ]
  leftIrradianceUrl [ "textures/sky/empty_office_left.hdr" ]
  rightIrradianceUrl [ "textures/sky/empty_office_right.hdr" ]
  topIrradianceUrl [ "textures/sky/empty_office_top.hdr" ]
}
DirectionalLight {
  ambientIntensity 0.08
  direction -0.2 -0.5 -0.9
  intensity 1.4
  color 1 0.97 0.92
  castShadows FALSE
}
Solid {
  name "regolith"
  contactMaterial "regolith"
  children [
"""

mid = f"""
{local_visual_indented}
"""

footer_ground = (
    """
  ]
  boundingObject """
    + _elevation_collider()
    + """
  locked TRUE
}
Solid {
  translation -3000 -3000 600
  rotation 0.8628597956588616 0.357398915361335 0.35740591535967725 1.717776
  name "earth"
  children [
    Shape {
      appearance PBRAppearance {
        baseColorMap ImageTexture {
          url [ "textures/moon/earth.png" ]
        }
        roughness 0.5
        metalness 0
      }
      geometry IndexedFaceSet {
        coord Coordinate {
          point [
            0 -400 -400
            0 400 -400
            0 400 400
            0 -400 400
          ]
        }
        texCoord TextureCoordinate {
          point [
            1 0
            1 1
            0 1
            0 0
          ]
        }
        coordIndex [
          0, 1, 2, 3, -1
        ]
        texCoordIndex [
          0, 1, 2, 3, -1
        ]
      }
    }
  ]
  locked TRUE
}
"""
)

footer_rest = f"""
{_scatter()}
Solid {{
  translation 1.8 -4.0 {height(1.8, -4.0) + 0.1:.3f}
  name "sample_ilmenite"
  recognitionColors [ 1 0.45 0.1 ]
  children [
    Shape {{
      appearance PBRAppearance {{ baseColor 0.85 0.42 0.12 roughness 0.35 metalness 0.55 }}
      geometry Box {{ size 0.2 0.2 0.2 }}
    }}
  ]
  boundingObject Box {{ size 0.2 0.2 0.2 }}
}}
Sawppy {{
  translation {SPAWN_X} {SPAWN_Y} {height(SPAWN_X, SPAWN_Y) + 0.38:.3f}
  rotation 0 0 1 6.15
  controller "sawppy_drive"
}}
Robot {{
  translation 0 0 -50
  name "mcp_bridge"
  controller "mcp_bridge"
  supervisor TRUE
}}
"""

DEST.write_text(
    header + mid + footer_ground + footer_rest,
    encoding="utf-8",
)
print(f"wrote {DEST} ({DEST.stat().st_size} bytes)")
