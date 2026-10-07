import unittest

from auris.system_status import collect_system_status


class SystemStatusTests(unittest.TestCase):
    def test_status_distinguishes_available_and_optional_machine_metrics(self):
        status = collect_system_status()

        self.assertTrue(status["machine"])
        self.assertGreater(status["cpu_count"], 0)
        self.assertIn("utilization_percent", status["cpu"])
        self.assertIn("memory", status)
        self.assertIn("gpu", status)
        self.assertIn("power", status)
        self.assertIn("network", status)
        self.assertGreater(status["disk"]["total_gb"], 0)


if __name__ == "__main__":
    unittest.main()
