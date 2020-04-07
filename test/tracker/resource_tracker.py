import time
import unittest

from nyx.tracker import ResourceTracker, _resources_via_ps, _resources_via_proc

try:
  # added in python 3.3
  from unittest.mock import Mock, patch
except ImportError:
  from mock import Mock, patch

PS_OUTPUT = """\
    TIME     ELAPSED   RSS %MEM
00:00:02       00:18 18848  0.4
"""


class TestResourceTracker(unittest.TestCase):
  @patch('nyx.tracker.tor_controller')
  @patch('nyx.tracker._resources_via_proc')
  @patch('nyx.tracker.system', Mock(return_value = Mock()))
  @patch('nyx.tracker.proc.is_available', Mock(return_value = True))
  def test_fetching_samplings(self, resources_via_proc_mock, tor_controller_mock):
    tor_controller_mock().get_pid.return_value = 12345
    resources_via_proc_mock.return_value = (105.3, 2.4, 8072, 0.3)

    with ResourceTracker(0.04) as daemon:
      time.sleep(0.01)

      resources = daemon.get_value()

      self.assertEqual(1, daemon.run_counter())
      self.assertEqual(0.0, resources.cpu_sample)
      self.assertEqual(43.875, resources.cpu_average)
      self.assertEqual(105.3, resources.cpu_total)
      self.assertEqual(8072, resources.memory_bytes)
      self.assertEqual(0.3, resources.memory_percent)
      self.assertTrue((time.time() - resources.timestamp) < 0.5)

      resources_via_proc_mock.return_value = (800.3, 3.2, 6020, 0.26)
      time.sleep(0.05)
      resources = daemon.get_value()

      self.assertEqual(2, daemon.run_counter())
      self.assertTrue(17000 < resources.cpu_sample < 18000)
      self.assertEqual(250.09374999999997, resources.cpu_average)
      self.assertEqual(800.3, resources.cpu_total)
      self.assertEqual(6020, resources.memory_bytes)
      self.assertEqual(0.26, resources.memory_percent)
      self.assertTrue((time.time() - resources.timestamp) < 0.5)

    resources_via_proc_mock.assert_called_with(12345)

  @patch('nyx.tracker.tor_controller')
  @patch('nyx.tracker.proc.is_available')
  @patch('nyx.tracker._resources_via_ps', Mock(return_value = (105.3, 2.4, 8072, 0.3)))
  @patch('nyx.tracker._resources_via_proc', Mock(return_value = (340.3, 3.2, 6020, 0.26)))
  @patch('nyx.tracker.system', Mock(return_value = Mock()))
  def test_picking_proc_or_ps(self, is_proc_available_mock, tor_controller_mock):
    tor_controller_mock().get_pid.return_value = 12345

    is_proc_available_mock.return_value = True

    with ResourceTracker(0.04) as daemon:
      time.sleep(0.01)

      resources = daemon.get_value()

      self.assertEqual(1, daemon.run_counter())
      self.assertEqual(0.0, resources.cpu_sample)
      self.assertEqual(106.34375, resources.cpu_average)
      self.assertEqual(340.3, resources.cpu_total)
      self.assertEqual(6020, resources.memory_bytes)
      self.assertEqual(0.26, resources.memory_percent)
      self.assertTrue((time.time() - resources.timestamp) < 0.5)

    is_proc_available_mock.return_value = False

    with ResourceTracker(0.04) as daemon:
      time.sleep(0.01)

      resources = daemon.get_value()

      self.assertEqual(1, daemon.run_counter())
      self.assertEqual(0.0, resources.cpu_sample)
      self.assertEqual(43.875, resources.cpu_average)
      self.assertEqual(105.3, resources.cpu_total)
      self.assertEqual(8072, resources.memory_bytes)
      self.assertEqual(0.3, resources.memory_percent)
      self.assertTrue((time.time() - resources.timestamp) < 0.5)

  @patch('nyx.tracker.tor_controller')
  @patch('nyx.tracker._resources_via_ps', Mock(return_value = (105.3, 2.4, 8072, 0.3)))
  @patch('nyx.tracker._resources_via_proc', Mock(side_effect = IOError()))
  @patch('nyx.tracker.system', Mock(return_value = Mock()))
  @patch('nyx.tracker.proc.is_available', Mock(return_value = True))
  def test_failing_over_to_ps(self, tor_controller_mock):
    tor_controller_mock().get_pid.return_value = 12345

    with ResourceTracker(0.01) as daemon:
      time.sleep(0.015)

      self.assertEqual(True, daemon._use_proc)
      resources = daemon.get_value()

      self.assertEqual(0, daemon.run_counter())
      self.assertEqual(0.0, resources.cpu_sample)
      self.assertEqual(0.0, resources.cpu_average)
      self.assertEqual(0, resources.cpu_total)
      self.assertEqual(0, resources.memory_bytes)
      self.assertEqual(0.0, resources.memory_percent)
      self.assertEqual(0.0, resources.timestamp)

      while daemon.run_counter() < 1:
        time.sleep(0.01)

      self.assertEqual(False, daemon._use_proc)

      resources = daemon.get_value()

      self.assertEqual(0.0, resources.cpu_sample)
      self.assertEqual(43.875, resources.cpu_average)
      self.assertEqual(105.3, resources.cpu_total)
      self.assertEqual(8072, resources.memory_bytes)
      self.assertEqual(0.3, resources.memory_percent)
      self.assertTrue((time.time() - resources.timestamp) < 0.5)

  @patch('nyx.tracker.system.call', Mock(return_value = PS_OUTPUT.split('\n')))
  def test_resources_via_ps(self):
    total_cpu_time, uptime, memory_in_bytes, memory_in_percent = _resources_via_ps(12345)

    self.assertEqual(2.0, total_cpu_time)
    self.assertEqual(18, uptime)
    self.assertEqual(19300352, memory_in_bytes)
    self.assertEqual(0.004, memory_in_percent)

  @patch('time.time', Mock(return_value = 1388967218.973117))
  @patch('nyx.tracker.proc.stats', Mock(return_value = (1.5, 0.5, 1388967200.9)))
  @patch('nyx.tracker.proc.memory_usage', Mock(return_value = (19300352, 6432)))
  @patch('nyx.tracker.proc.physical_memory', Mock(return_value = 4825088000))
  def test_resources_via_proc(self):
    total_cpu_time, uptime, memory_in_bytes, memory_in_percent = _resources_via_proc(12345)

    self.assertEqual(2.0, total_cpu_time)
    self.assertEqual(18, int(uptime))
    self.assertEqual(19300352, memory_in_bytes)
    self.assertEqual(0.004, memory_in_percent)
