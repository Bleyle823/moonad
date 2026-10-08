"""Expand rover.urdf.xacro without a sourced ROS install."""
import os
import shutil

SRC = r"C:\Users\Omen\Desktop\ros2_rover-jazzy\rover_description"
DST = os.path.join(SRC, "_expanded")
FIND = "$(find rover_description)"

if os.path.isdir(DST):
    shutil.rmtree(DST)

repl = DST.replace("\\", "/")
count = 0
for root, dirs, files in os.walk(SRC):
    if os.path.basename(root) == "_expanded" or "_expanded" in root.split(os.sep):
        continue
    for name in files:
        if not name.endswith(".xacro"):
            continue
        src_path = os.path.join(root, name)
        rel = os.path.relpath(src_path, SRC)
        dst_path = os.path.join(DST, rel)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        text = open(src_path, encoding="utf-8").read()
        text = text.replace(FIND, repl)
        open(dst_path, "w", encoding="utf-8").write(text)
        count += 1
print("wrote", count, "files to", DST)
