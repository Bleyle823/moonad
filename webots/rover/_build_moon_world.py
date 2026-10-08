"""Build rover/worlds/moon.wbt from the Webots samples/demos moon terrain."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLE = Path(
    r"C:\Users\Omen\Desktop\webots-master\projects\samples\demos\worlds\moon.wbt"
)
DEST = ROOT / "worlds" / "moon.wbt"

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
indented = "\n".join(("    " + line if line else line) for line in ground.splitlines())

header = """#VRML_SIM R2025a utf8

EXTERNPROTO "../protos/Sawppy.proto"

WorldInfo {
  title "Sawppy on the Moon"
  info [
    "Terrain, moon_ground texture, black sky, and Earth billboard from samples/demos/worlds/moon.wbt."
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
      maxContactJoints 21
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

footer = """
  ]
  boundingObject Plane {
    size 80 80
  }
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
Solid {
  translation -2.4 2.8 0.18
  name "rock_a"
  recognitionColors [ 0.4 0.38 0.35 ]
  children [
    Shape {
      appearance PBRAppearance {
        baseColor 0.45 0.42 0.38
        roughness 1
        metalness 0
        baseColorMap ImageTexture { url [ "textures/rock.jpg" ] }
      }
      geometry Box { size 1.0 0.8 0.36 }
    }
  ]
  boundingObject Box { size 1.0 0.8 0.36 }
  locked TRUE
}
Solid {
  translation 1.2 0.8 0.12
  name "rock_b"
  recognitionColors [ 0.5 0.48 0.44 ]
  children [
    Shape {
      appearance PBRAppearance {
        baseColor 0.5 0.46 0.4
        roughness 1
        metalness 0
        baseColorMap ImageTexture { url [ "textures/rock.jpg" ] }
      }
      geometry Box { size 0.5 0.4 0.24 }
    }
  ]
  boundingObject Box { size 0.5 0.4 0.24 }
  locked TRUE
}
Solid {
  translation -1.1 -1.5 0.1
  rotation 0 0 1 0.7
  name "rock_c"
  recognitionColors [ 0.48 0.46 0.42 ]
  children [
    Shape {
      appearance PBRAppearance {
        baseColor 0.48 0.44 0.4
        roughness 1
        metalness 0
        baseColorMap ImageTexture { url [ "textures/rock.jpg" ] }
      }
      geometry Box { size 0.45 0.35 0.2 }
    }
  ]
  boundingObject Box { size 0.45 0.35 0.2 }
  locked TRUE
}
Solid {
  translation 1.8 -4.0 0.1
  name "sample_ilmenite"
  recognitionColors [ 1 0.45 0.1 ]
  children [
    Shape {
      appearance PBRAppearance { baseColor 0.85 0.42 0.12 roughness 0.35 metalness 0.55 }
      geometry Box { size 0.2 0.2 0.2 }
    }
  ]
  boundingObject Box { size 0.2 0.2 0.2 }
}
Sawppy {
  translation -2.35 -0.7 0.28
  rotation 0 0 1 6.15
  controller "sawppy_drive"
}
Robot {
  translation 0 0 -50
  name "mcp_bridge"
  controller "mcp_bridge"
  supervisor TRUE
}
"""

DEST.write_text(header + indented + "\n" + footer, encoding="utf-8")
print(f"wrote {DEST} ({DEST.stat().st_size} bytes)")
