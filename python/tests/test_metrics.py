import math
import unittest

from eskf_ref.metrics import orientation_error_rad, vector_error_norm
from eskf_ref.transforms import RigidTransform, apply_transform, rotate_vector


class MetricTests(unittest.TestCase):
    def test_vector_error_norm(self):
        self.assertAlmostEqual(vector_error_norm([1, 2, 3], [1, 4, 3]), 2.0)

    def test_orientation_error(self):
        q_identity = [1.0, 0.0, 0.0, 0.0]
        q_yaw_90 = [math.cos(math.pi / 4.0), 0.0, 0.0, math.sin(math.pi / 4.0)]
        self.assertAlmostEqual(orientation_error_rad(q_identity, q_yaw_90), math.pi / 2.0)

    def test_rotate_vector_preserves_magnitude(self):
        q_yaw_90 = [math.cos(math.pi / 4.0), 0.0, 0.0, math.sin(math.pi / 4.0)]
        rotated = rotate_vector(q_yaw_90, [2.0, 0.0, 0.0])
        self.assertAlmostEqual(rotated[0], 0.0, places=6)
        self.assertAlmostEqual(rotated[1], 2.0, places=6)
        self.assertAlmostEqual(rotated[2], 0.0, places=6)

    def test_apply_transform(self):
        transform = RigidTransform((1.0, 0.0, 0.0, 0.0), (1.0, 2.0, 3.0))
        self.assertEqual(apply_transform(transform, [4.0, 5.0, 6.0]), (5.0, 7.0, 9.0))


if __name__ == "__main__":
    unittest.main()
