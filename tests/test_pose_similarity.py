import pytest

from app.services import pose_similarity


def test_weighted_point_distance_is_more_tolerant_for_upper_body_vertical_differences():
    shoulder_ref = {"x": -0.5, "y": -1.0, "visibility": 1.0}
    shoulder_cur = {"x": -0.5, "y": -1.3, "visibility": 1.0}
    hip_ref = {"x": -0.25, "y": 0.0, "visibility": 1.0}
    hip_cur = {"x": -0.25, "y": -0.3, "visibility": 1.0}

    shoulder_distance = pose_similarity._weighted_point_distance("left_shoulder", shoulder_ref, shoulder_cur)
    hip_distance = pose_similarity._weighted_point_distance("left_hip", hip_ref, hip_cur)

    assert shoulder_distance < hip_distance
    assert shoulder_distance == pytest.approx(0.165)


def test_weighted_point_distance_preserves_full_horizontal_sensitivity():
    shoulder_ref = {"x": -0.5, "y": -1.0, "visibility": 1.0}
    shoulder_cur = {"x": -0.2, "y": -1.0, "visibility": 1.0}

    distance = pose_similarity._weighted_point_distance("left_shoulder", shoulder_ref, shoulder_cur)

    assert distance == pytest.approx(0.3)
