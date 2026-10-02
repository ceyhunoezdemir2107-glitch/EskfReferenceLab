import math
import unittest

from eskf_ref.evaluate import evaluate_log


class EvaluateTests(unittest.TestCase):
    def test_evaluate_state_pairs(self):
        path = "test_eval_tmp.jsonl"
        lines = [
            '{"schema_version":"1.0","message_type":"REFERENCE_STATE","source":"ANDROID","device_time_s":1.0,"sequence":1,"payload":{"position_available":true,"velocity_available":true,"position_m":[0,0,0],"velocity_mps":[1,0,0],"quaternion_wxyz":[1,0,0,0]}}',
            '{"schema_version":"1.0","message_type":"ESTIMATOR_STATE","source":"ARDUINO","device_time_s":1.01,"sequence":2,"payload":{"position_m":[3,4,0],"velocity_mps":[1,2,0],"quaternion_wxyz":[1,0,0,0]}}',
        ]
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            result = evaluate_log(path, reference_source="ANDROID", estimator_source="ARDUINO", max_dt_s=0.05)
            self.assertEqual(result["pair_count"], 1)
            self.assertAlmostEqual(result["metrics"]["position_error_m_rmse"], 5.0)
            self.assertAlmostEqual(result["metrics"]["velocity_error_mps_rmse"], 2.0)
            self.assertAlmostEqual(result["metrics"]["orientation_error_deg_rmse"], 0.0)
        finally:
            import os
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
