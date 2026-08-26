"""Device-selection regression tests (no GPU required).

Covers the production rule in ``rag_chat_v2._select_execution_device``:
CUDA is chosen only when is_available() is True AND device_count() > 0 AND
device 0 can actually be inspected; any inspection failure falls back to CPU
instead of crashing startup.
"""

import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path = None  # placeholder to keep linters quiet about order
from pathlib import Path  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for entry in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import rag_chat_v2  # noqa: E402


class DeviceSelectionTests(unittest.TestCase):
    def select(self, available, count, props=None, inspect_raises=False):
        torch_module = rag_chat_v2.torch
        with patch.object(torch_module.cuda, "is_available", return_value=available), \
             patch.object(torch_module.cuda, "device_count", return_value=count):
            if inspect_raises:
                with patch.object(torch_module.cuda, "get_device_properties",
                                  side_effect=RuntimeError("no device")):
                    return rag_chat_v2._select_execution_device()
            with patch.object(torch_module.cuda, "get_device_properties",
                              return_value=props):
                return rag_chat_v2._select_execution_device()

    def test_a_unavailable_means_cpu(self):
        self.assertEqual(self.select(available=False, count=0), "cpu")

    def test_b_available_but_zero_devices_means_cpu(self):
        """The field-observed quirk: is_available True, device_count 0."""
        self.assertEqual(self.select(available=True, count=0), "cpu")

    def test_c_real_device_selects_cuda(self):
        class FakeProps:
            total_memory = 6 * 1024 ** 3

        self.assertEqual(self.select(available=True, count=1, props=FakeProps()), "cuda")

    def test_d_inspection_failure_falls_back_to_cpu_without_crash(self):
        class FakeProps:
            total_memory = 6 * 1024 ** 3

        self.assertEqual(
            self.select(available=True, count=1, props=FakeProps(), inspect_raises=True),
            "cpu",
        )

    def test_e_zero_memory_device_rejected(self):
        class FakeProps:
            total_memory = 0

        self.assertEqual(self.select(available=True, count=1, props=FakeProps()), "cpu")

    def test_f_none_properties_rejected(self):
        self.assertEqual(self.select(available=True, count=1, props=None), "cpu")


if __name__ == "__main__":
    unittest.main(verbosity=2)
