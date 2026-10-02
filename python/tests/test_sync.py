import math
import unittest

from eskf_ref.sync import estimate_time_offset_s


class SyncTests(unittest.TestCase):
    def test_estimate_time_offset(self):
        delay = 0.12
        reference = [(i * 0.01, math.sin(2.0 * math.pi * 1.5 * i * 0.01)) for i in range(500)]
        moving = [(i * 0.01, math.sin(2.0 * math.pi * 1.5 * (i * 0.01 - delay))) for i in range(500)]
        offset, corr = estimate_time_offset_s(
            reference,
            moving,
            max_lag_s=0.3,
            step_s=0.01,
            sample_period_s=0.01,
        )
        self.assertAlmostEqual(offset, delay, places=2)
        self.assertGreater(corr, 0.99)


if __name__ == "__main__":
    unittest.main()
