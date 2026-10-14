"""Lander task agent — buyer machine on the lunar surface.

Posts a job and commits escrow to the lunar economy bus. No keys, no chain calls.
"""

from __future__ import annotations

import os
import sys

from controller import Robot

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lunar_economy"))
from bus import post_job  # noqa: E402

JOB_ID = "job-moon-001"
BUYER_ID = "lander-1"
WORKER_ID = "prospector-1"
PER_DISCOVERY = "0.01"
ESCROW_TOTAL = "0.05"
SAMPLES = [
    "sample_ilmenite",
    "sample_ilmenite_02",
    "sample_ilmenite_03",
]


def main():
    robot = Robot()
    step = int(robot.getBasicTimeStep())
    if robot.step(step) == -1:
        return
    job = post_job(
        JOB_ID,
        BUYER_ID,
        WORKER_ID,
        PER_DISCOVERY,
        ESCROW_TOTAL,
        SAMPLES,
    )
    print("[lander]", "job_posted", job["job_id"], "escrow", ESCROW_TOTAL, "AGUNG")
    while robot.step(step) != -1:
        pass


if __name__ == "__main__":
    main()
