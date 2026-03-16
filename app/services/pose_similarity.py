import json
import math
import io
import os
import logging
from typing import Any

from PIL import Image, ImageOps


# Keep MediaPipe/TFLite output quiet in server logs (especially during bulk posture imports).
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "2")
os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")

try:
    import mediapipe as mp  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mp = None

if mp is not None:
    try:
        from absl import logging as absl_logging  # type: ignore

        absl_logging.set_verbosity(absl_logging.ERROR)
        absl_logging.set_stderrthreshold("error")
    except Exception:
        pass
    logging.getLogger("absl").setLevel(logging.ERROR)


BLAZEPOSE_NAMES: dict[int, str] = {
    11: "left_shoulder",
    12: "right_shoulder",
    13: "left_elbow",
    14: "right_elbow",
    15: "left_wrist",
    16: "right_wrist",
    23: "left_hip",
    24: "right_hip",
    25: "left_knee",
    26: "right_knee",
    27: "left_ankle",
    28: "right_ankle",
}

ANGLE_TRIPLETS: dict[str, tuple[str, str, str]] = {
    "left_elbow": ("left_shoulder", "left_elbow", "left_wrist"),
    "right_elbow": ("right_shoulder", "right_elbow", "right_wrist"),
    "left_knee": ("left_hip", "left_knee", "left_ankle"),
    "right_knee": ("right_hip", "right_knee", "right_ankle"),
    "left_hip": ("left_shoulder", "left_hip", "left_knee"),
    "right_hip": ("right_shoulder", "right_hip", "right_knee"),
}


def pose_similarity_available() -> bool:
    return mp is not None


def _decode_image_rgb(image_bytes: bytes):
    with Image.open(io.BytesIO(image_bytes)) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
    return image


def _detect_landmarks(image_bytes: bytes) -> dict[str, Any] | None:
    if not pose_similarity_available():
        return None
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    image = _decode_image_rgb(image_bytes)
    arr = np.array(image)

    pose = mp.solutions.pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        enable_segmentation=False,
        min_detection_confidence=0.5,
    )
    try:
        result = pose.process(arr)
    finally:
        pose.close()

    if not result.pose_landmarks:
        return None

    points: dict[str, dict[str, float]] = {}
    for idx, name in BLAZEPOSE_NAMES.items():
        lm = result.pose_landmarks.landmark[idx]
        points[name] = {
            "x": float(lm.x),
            "y": float(lm.y),
            "visibility": float(lm.visibility),
        }

    normalized = _normalize_points(points)
    if normalized is None:
        return None
    return normalized


def _normalize_points(points: dict[str, dict[str, float]]) -> dict[str, Any] | None:
    left_hip = points.get("left_hip")
    right_hip = points.get("right_hip")
    left_shoulder = points.get("left_shoulder")
    right_shoulder = points.get("right_shoulder")
    if not left_hip or not right_hip or not left_shoulder or not right_shoulder:
        return None

    center_x = (left_hip["x"] + right_hip["x"]) / 2.0
    center_y = (left_hip["y"] + right_hip["y"]) / 2.0

    shoulder_dist = math.dist(
        (left_shoulder["x"], left_shoulder["y"]),
        (right_shoulder["x"], right_shoulder["y"]),
    )
    torso_dist = math.dist(
        ((left_shoulder["x"] + right_shoulder["x"]) / 2.0, (left_shoulder["y"] + right_shoulder["y"]) / 2.0),
        (center_x, center_y),
    )
    scale = shoulder_dist if shoulder_dist > 0.02 else torso_dist
    if scale <= 0.02:
        return None

    norm_points: dict[str, dict[str, float]] = {}
    for name, point in points.items():
        norm_points[name] = {
            "x": (point["x"] - center_x) / scale,
            "y": (point["y"] - center_y) / scale,
            "visibility": float(point.get("visibility", 0.0)),
        }

    return {
        "points": norm_points,
        "meta": {
            "scale": float(scale),
            "center": [float(center_x), float(center_y)],
        },
    }


def _joint_angle_deg(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    mag_ba = math.hypot(ba[0], ba[1])
    mag_bc = math.hypot(bc[0], bc[1])
    if mag_ba <= 1e-9 or mag_bc <= 1e-9:
        return 180.0
    cosv = (ba[0] * bc[0] + ba[1] * bc[1]) / (mag_ba * mag_bc)
    cosv = max(-1.0, min(1.0, cosv))
    return math.degrees(math.acos(cosv))


def extract_reference_landmarks_json(image_bytes: bytes) -> str | None:
    detected = _detect_landmarks(image_bytes)
    if detected is None:
        return None
    return json.dumps(detected, ensure_ascii=True)


def score_against_reference(image_bytes: bytes, reference_landmarks_json: str) -> dict[str, Any] | None:
    current = _detect_landmarks(image_bytes)
    if current is None:
        return None

    try:
        reference = json.loads(reference_landmarks_json)
    except Exception:
        return None

    ref_points = (reference or {}).get("points") or {}
    cur_points = (current or {}).get("points") or {}

    pos_weight_sum = 0.0
    pos_error_sum = 0.0
    for name in BLAZEPOSE_NAMES.values():
        rp = ref_points.get(name)
        cp = cur_points.get(name)
        if not rp or not cp:
            continue
        weight = min(float(rp.get("visibility", 0.0)), float(cp.get("visibility", 0.0)))
        if weight < 0.2:
            continue
        dist = math.dist((float(rp.get("x", 0.0)), float(rp.get("y", 0.0))), (float(cp.get("x", 0.0)), float(cp.get("y", 0.0))))
        pos_error_sum += weight * dist
        pos_weight_sum += weight

    if pos_weight_sum <= 1e-9:
        return None

    e_pos = pos_error_sum / pos_weight_sum

    ang_weight_sum = 0.0
    ang_error_sum = 0.0
    for _, (a_name, b_name, c_name) in ANGLE_TRIPLETS.items():
        ra = ref_points.get(a_name)
        rb = ref_points.get(b_name)
        rc = ref_points.get(c_name)
        ca = cur_points.get(a_name)
        cb = cur_points.get(b_name)
        cc = cur_points.get(c_name)
        if not (ra and rb and rc and ca and cb and cc):
            continue
        weight = min(
            float(ra.get("visibility", 0.0)),
            float(rb.get("visibility", 0.0)),
            float(rc.get("visibility", 0.0)),
            float(ca.get("visibility", 0.0)),
            float(cb.get("visibility", 0.0)),
            float(cc.get("visibility", 0.0)),
        )
        if weight < 0.2:
            continue

        ref_angle = _joint_angle_deg(
            (float(ra.get("x", 0.0)), float(ra.get("y", 0.0))),
            (float(rb.get("x", 0.0)), float(rb.get("y", 0.0))),
            (float(rc.get("x", 0.0)), float(rc.get("y", 0.0))),
        )
        cur_angle = _joint_angle_deg(
            (float(ca.get("x", 0.0)), float(ca.get("y", 0.0))),
            (float(cb.get("x", 0.0)), float(cb.get("y", 0.0))),
            (float(cc.get("x", 0.0)), float(cc.get("y", 0.0))),
        )
        ang_error_sum += weight * abs(ref_angle - cur_angle)
        ang_weight_sum += weight

    e_ang = (ang_error_sum / ang_weight_sum / 180.0) if ang_weight_sum > 1e-9 else 0.0

    # Penalize weak landmark quality.
    vis_values = []
    for name in BLAZEPOSE_NAMES.values():
        rp = ref_points.get(name)
        cp = cur_points.get(name)
        if not rp or not cp:
            continue
        vis_values.append(min(float(rp.get("visibility", 0.0)), float(cp.get("visibility", 0.0))))
    mean_vis = (sum(vis_values) / len(vis_values)) if vis_values else 0.0
    e_vis = max(0.0, 0.6 - mean_vis)

    alpha = 0.75
    beta = 0.20
    gamma = 0.05

    combined_error = max(0.0, min(1.0, (alpha * e_pos) + (beta * e_ang) + (gamma * e_vis)))
    score = 100.0 * (1.0 - combined_error)

    return {
        "score": round(score, 2),
        "position_error": round(e_pos, 4),
        "angle_error": round(e_ang, 4),
        "visibility_penalty": round(e_vis, 4),
        "mean_visibility": round(mean_vis, 4),
    }
