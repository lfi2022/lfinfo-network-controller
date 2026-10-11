import unittest

from app import packet_rate


class PacketRateTests(unittest.TestCase):
    def test_calculates_packets_per_second_from_monotonic_counters(self):
        self.assertEqual(packet_rate(160, (100, '2026-01-01T12:00:00+00:00'), '2026-01-01T12:00:10+00:00'), 6.0)

    def test_returns_none_after_counter_reset(self):
        self.assertIsNone(packet_rate(20, (100, '2026-01-01T12:00:00+00:00'), '2026-01-01T12:00:10+00:00'))

    def test_returns_none_without_previous_sample(self):
        self.assertIsNone(packet_rate(100, None, '2026-01-01T12:00:10+00:00'))


if __name__ == '__main__':
    unittest.main()
