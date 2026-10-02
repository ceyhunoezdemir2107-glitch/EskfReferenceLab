import unittest

from eskf_ref.messages import parse_message


class MessageParsingTests(unittest.TestCase):
    def test_parse_telemetry_summary(self):
        raw = (
            '{"schema_version":"1.0","message_type":"TELEMETRY_SUMMARY",'
            '"source":"ARDUINO","device_time_s":12.5,"sequence":7,'
            '"payload":{"latitude_deg":48.20468,"longitude_deg":16.172,'
            '"altitude_m":291.4,"speed_mps":12.8,"course_deg":84.0,'
            '"battery_v":11.7,"link_rssi_dbm":-82,"flight_state":"flying"}}'
        )

        message = parse_message(raw, pc_recv_time_s=99.0, transport="serial")

        self.assertEqual(message.message_type, "TELEMETRY_SUMMARY")
        self.assertEqual(message.source, "ARDUINO")
        self.assertEqual(message.sequence, 7)
        self.assertEqual(message.payload["altitude_m"], 291.4)
        self.assertEqual(message.transport, "serial")


if __name__ == "__main__":
    unittest.main()
