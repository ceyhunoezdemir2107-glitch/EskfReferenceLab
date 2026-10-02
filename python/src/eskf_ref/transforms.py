from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .metrics import Quaternion, Vector3, quat_multiply, quat_normalize


@dataclass(frozen=True)
class RigidTransform:
    """Body transform p_to = R(q_to_from) * p_from + t_to_from."""

    q_to_from_wxyz: tuple[float, float, float, float]
    t_to_from_m: tuple[float, float, float]


def rotate_vector(q_wxyz: Quaternion, vector: Vector3) -> tuple[float, float, float]:
    if len(vector) != 3:
        raise ValueError("vector must have 3 elements")
    w, x, y, z = quat_normalize(q_wxyz)
    vx, vy, vz = (float(item) for item in vector)

    # Optimized q * v * q^-1 without normalizing the vector quaternion.
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def apply_transform(transform: RigidTransform, position_m: Sequence[float]) -> tuple[float, float, float]:
    rotated = rotate_vector(transform.q_to_from_wxyz, position_m)
    return (
        rotated[0] + transform.t_to_from_m[0],
        rotated[1] + transform.t_to_from_m[1],
        rotated[2] + transform.t_to_from_m[2],
    )


def transform_orientation(transform: RigidTransform, q_from_body_wxyz: Quaternion) -> tuple[float, float, float, float]:
    return quat_multiply(transform.q_to_from_wxyz, q_from_body_wxyz)
