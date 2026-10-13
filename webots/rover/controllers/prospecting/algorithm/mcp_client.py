"""Query the moon.wbt mcp_bridge supervisor (port 10022) for scene layout."""

from __future__ import annotations

import json
import math
import os
import socket
import struct

MCP_PORT = int(os.environ.get("WEBOTS_MCP_PORT", "10022"))
MCP_HOST = os.environ.get("WEBOTS_MCP_HOST", "127.0.0.1")


def _recv_frame(sock, deadline):
    while True:
        header = _recv_exact(sock, 4, deadline)
        if header is None:
            return None
        (length,) = struct.unpack(">I", header)
        if length == 0:
            continue
        if length > 8 * 1024 * 1024:
            return None
        data = _recv_exact(sock, length, deadline)
        if data is None:
            return None
        return json.loads(data.decode("utf-8"))


def _recv_exact(sock, n, deadline):
    import time

    buf = bytearray()
    while len(buf) < n:
        if time.monotonic() > deadline:
            return None
        sock.settimeout(max(0.05, deadline - time.monotonic()))
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)


def _call(action, params, timeout=0.2):
    import time

    deadline = time.monotonic() + timeout
    try:
        sock = socket.create_connection((MCP_HOST, MCP_PORT), timeout=timeout)
    except OSError:
        return None
    try:
        payload = json.dumps({"id": 1, "action": action, "params": params}).encode("utf-8")
        sock.sendall(struct.pack(">I", len(payload)) + payload)
        resp = _recv_frame(sock, deadline)
        if not resp or resp.get("status") != "ok":
            return None
        return resp.get("result")
    except (OSError, json.JSONDecodeError, struct.error):
        return None
    finally:
        sock.close()


def fetch_obstacles(x, y, radius=16.0):
    """Return [(x, y, radius), ...] for rocks near the rover from the live scene."""
    result = _call("find_nodes_near", {"point": [float(x), float(y), 0.0], "radius": float(radius)})
    if not result:
        return []
    out = []
    for node in result.get("nodes") or []:
        name = (node.get("name") or "").lower()
        if not (name.startswith("boulder_") or name.startswith("rock_") or name.startswith("ejecta_")):
            continue
        pos = node.get("position")
        if not pos or len(pos) < 2:
            continue
        size = node.get("size")
        r = 0.38
        if size and len(size) >= 2:
            r = max(float(size[0]), float(size[1])) * 0.5 + 0.12
        out.append((float(pos[0]), float(pos[1]), r))
    return out


def fetch_robot_yaw(robot_name="Sawppy"):
    result = _call("get_node_pose", {"node": robot_name})
    if not result:
        return None
    ori = result.get("orientation")
    if not ori or len(ori) < 4:
        return None
    return math.atan2(float(ori[3]), float(ori[0]))


def sort_goals_by_distance(goals, x, y):
    ranked = sorted(goals, key=lambda g: math.hypot(g[1] - x, g[2] - y))
    return ranked
