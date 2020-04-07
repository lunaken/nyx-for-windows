"""
Unit tests for nyx.panel.header.
"""

import time
import unittest

import stem.control
import stem.exit_policy
import stem.version
import stem.util.system

import nyx.panel.header
import test

from test import require_curses

try:
  # added in python 3.3
  from unittest.mock import Mock, patch
except ImportError:
  from mock import Mock, patch

EXPECTED_PANEL = """
nyx - odin (Linux 3.5.0-54-generic)        Tor 0.2.8.1-alpha-dev
Unnamed - 174.21.17.28:7000, Dir Port: 7001, Control Port (cookie): 7002
cpu: 12.3% tor, 5.7% nyx   mem: 11 MB (2.1%)   pid: 765
fingerprint: 1A94D1A794FCB2F8B6CBC179EF8FDD4008A98D3B
flags: Running, Exit

page 2 / 4 - m: menu, p: pause, h: page help, q: quit
""".strip()


def test_sampling():
  return nyx.panel.header.Sampling(
    retrieved = 1234.5,
    is_connected = True,
    connection_time = 2345.6,
    last_heartbeat = 3456.7,

    fingerprint = '1A94D1A794FCB2F8B6CBC179EF8FDD4008A98D3B',
    nickname = 'Unnamed',
    newnym_wait = None,
    exit_policy = stem.exit_policy.ExitPolicy('reject *:*'),
    flags = ['Running', 'Exit'],

    version = '0.2.8.1-alpha-dev',
    version_status = 'unrecommended',

    address = '174.21.17.28',
    or_port = '7000',
    dir_port = '7001',
    control_port = '7002',
    socket_path = None,
    is_relay = True,

    auth_type = 'cookie',
    pid = '765',
    start_time = 4567.8,
    fd_limit = 100,
    fd_used = 40,

    nyx_total_cpu_time = 100,
    tor_cpu = '12.3',
    nyx_cpu = '5.7',
    memory = '11 MB',
    memory_percent = '2.1',

    hostname = 'odin',
    platform = 'Linux 3.5.0-54-generic',
  )


class TestHeaderPanel(unittest.TestCase):
  @require_curses
  @patch('nyx.panel.header.nyx_interface')
  @patch('nyx.panel.header.tor_controller')
  @patch('nyx.panel.header.Sampling.create')
  def test_rendering_panel(self, sampling_mock, tor_controller_mock, nyx_interface_mock):
    nyx_interface_mock().is_paused.return_value = False
    nyx_interface_mock().get_page.return_value = 1
    nyx_interface_mock().page_count.return_value = 4
    sampling_mock.return_value = test_sampling()

    panel = nyx.panel.header.HeaderPanel()
    self.assertEqual(EXPECTED_PANEL, test.render(panel._draw).content)

  @patch('nyx.panel.header.tor_controller')
  @patch('nyx.tracker.get_resource_tracker')
  @patch('nyx.tracker.get_consensus_tracker')
  @patch('time.time', Mock(return_value = 1234.5))
  @patch('os.times', Mock(return_value = (0.08, 0.03, 0.0, 0.0, 18759021.31)))
  @patch('os.uname', Mock(return_value = ('Linux', 'odin', '3.5.0-54-generic', '#81~precise1-Ubuntu SMP Tue Jul 15 04:05:58 UTC 2014', 'i686')))
  @patch('stem.util.system.start_time', Mock(return_value = 5678))
  @patch('stem.util.proc.file_descriptors_used', Mock(return_value = 89))
  def test_sample(self, consensus_tracker_mock, resource_tracker_mock, tor_controller_mock):
    tor_controller_mock().is_alive.return_value = True
    tor_controller_mock().connection_time.return_value = 567.8
    tor_controller_mock().get_latest_heartbeat.return_value = 89.0
    tor_controller_mock().get_newnym_wait.return_value = 0
    tor_controller_mock().get_exit_policy.return_value = stem.exit_policy.ExitPolicy('reject *:*')
    tor_controller_mock().get_version.return_value = stem.version.Version('0.1.2.3-tag')
    tor_controller_mock().get_pid.return_value = '123'

    tor_controller_mock().get_info.side_effect = lambda param, default = None: {
      'address': '174.21.17.28',
      'fingerprint': '1A94D1A794FCB2F8B6CBC179EF8FDD4008A98D3B',
      'status/version/current': 'recommended',
      'process/descriptor-limit': 678,
    }[param]

    tor_controller_mock().get_conf.side_effect = lambda param, default = None: {
      'Nickname': 'Unnamed',
      'HashedControlPassword': None,
      'CookieAuthentication': '1',
      'DirPort': '7001',
      'ControlSocket': None,
    }[param]

    tor_controller_mock().get_listeners.side_effect = lambda param, default = None: {
      stem.control.Listener.OR: [('0.0.0.0', 7000)],
      stem.control.Listener.CONTROL: [('0.0.0.0', 9051)],
    }[param]

    resources = Mock()
    resources.cpu_sample = 6.7
    resources.memory_bytes = 62464
    resources.memory_percent = .125

    resource_tracker_mock().get_value.return_value = resources
    stem.util.system.SYSTEM_CALL_TIME = 0.0

    consensus_tracker_mock().my_router_status_entry.return_value = None

    vals = nyx.panel.header.Sampling.create()

    self.assertEqual(1234.5, vals.retrieved)
    self.assertEqual(True, vals.is_connected)
    self.assertEqual(567.8, vals.connection_time)
    self.assertEqual(89.0, vals.last_heartbeat)
    self.assertEqual('1A94D1A794FCB2F8B6CBC179EF8FDD4008A98D3B', vals.fingerprint)
    self.assertEqual('Unnamed', vals.nickname)
    self.assertEqual(0, vals.newnym_wait)
    self.assertEqual(stem.exit_policy.ExitPolicy('reject *:*'), vals.exit_policy)
    self.assertEqual([], vals.flags)
    self.assertEqual('0.1.2.3-tag', vals.version)
    self.assertEqual('recommended', vals.version_status)
    self.assertEqual('174.21.17.28', vals.address)
    self.assertEqual(7000, vals.or_port)
    self.assertEqual('7001', vals.dir_port)
    self.assertEqual('9051', vals.control_port)
    self.assertEqual(None, vals.socket_path)
    self.assertEqual(True, vals.is_relay)
    self.assertEqual('cookie', vals.auth_type)
    self.assertEqual('123', vals.pid)
    self.assertEqual(5678, vals.start_time)
    self.assertEqual(678, vals.fd_limit)
    self.assertEqual(89, vals.fd_used)
    self.assertEqual(0.11, vals.nyx_total_cpu_time)
    self.assertEqual('670.0', vals.tor_cpu)
    self.assertEqual('0.0', vals.nyx_cpu)
    self.assertEqual('61 KB', vals.memory)
    self.assertEqual('12.5', vals.memory_percent)
    self.assertEqual('odin', vals.hostname)
    self.assertEqual('Linux 3.5.0-54-generic', vals.platform)

  def test_sample_format(self):
    vals = nyx.panel.header.Sampling(
      version = '0.2.8.1',
      version_status = 'unrecommended',
    )

    self.assertEqual('0.2.8.1 is unrecommended', vals.format('{version} is {version_status}'))

    test_input = {
      25: '0.2.8.1 is unrecommended',
      20: '0.2.8.1 is unreco...',
      15: '0.2.8.1 is...',
      10: '0.2.8.1...',
      5: '',
      0: '',
    }

    for width, expected in test_input.items():
      self.assertEqual(expected, vals.format('{version} is {version_status}', width))

  @require_curses
  def test_draw_platform_section(self):
    vals = nyx.panel.header.Sampling(
      hostname = 'odin',
      platform = 'Linux 3.5.0-54-generic',
      version = '0.2.8.1-alpha-dev',
      version_status = 'unrecommended',
    )

    test_input = {
      80: 'nyx - odin (Linux 3.5.0-54-generic)        Tor 0.2.8.1-alpha-dev',
      70: 'nyx - odin (Linux 3.5.0-54-generic)        Tor 0.2.8.1-alpha-dev',
      60: 'nyx - odin (Linux 3.5.0-54-generic)        Tor 0.2.8.1-al...',
      50: 'nyx - odin (Linux 3.5.0-54-generic)',
      40: 'nyx - odin (Linux 3.5.0-54-generic)',
      30: 'nyx - odin (Linux 3.5.0-54...)',
      20: 'nyx - odin (Linu...)',
      10: 'nyx - odin',
      0: '',
    }

    for width, expected in test_input.items():
      self.assertEqual(expected, test.render(nyx.panel.header._draw_platform_section, 0, 0, width, vals).content)

  @require_curses
  def test_draw_platform_section_without_version(self):
    vals = nyx.panel.header.Sampling(
      hostname = 'odin',
      platform = 'Linux 3.5.0-54-generic',
      version = 'Unknown',
    )

    rendered = test.render(nyx.panel.header._draw_platform_section, 0, 0, 80, vals)
    self.assertEqual('nyx - odin (Linux 3.5.0-54-generic)', rendered.content)

  @require_curses
  def test_draw_ports_section(self):
    vals = nyx.panel.header.Sampling(
      nickname = 'Unnamed',
      address = '174.21.17.28',
      or_port = '7000',
      dir_port = '7001',
      control_port = '9051',
      auth_type = 'cookie',
      is_relay = True,
    )

    test_input = {
      80: 'Unnamed - 174.21.17.28:7000, Dir Port: 7001, Control Port (cookie): 9051',
      50: 'Unnamed - 174.21.17.28:7000, Dir Port: 7001, Control Port: 9051',
      0: 'Unnamed - 174.21.17.28:7000, Dir Port: 7001, Control Port: 9051',
    }

    for width, expected in test_input.items():
      self.assertEqual(expected, test.render(nyx.panel.header._draw_ports_section, 0, 0, width, vals).content)

  @require_curses
  def test_draw_ports_section_with_relaying(self):
    vals = nyx.panel.header.Sampling(
      control_port = None,
      socket_path = '/path/to/control/socket',
      is_relay = False,
    )

    self.assertEqual('Relaying Disabled, Control Socket: /path/to/control/socket', test.render(nyx.panel.header._draw_ports_section, 0, 0, 80, vals).content)

  @require_curses
  @patch('time.localtime')
  def test_draw_disconnected(self, localtime_mock):
    localtime_mock.return_value = time.strptime('22:43 04/09/2016', '%H:%M %m/%d/%Y')
    self.assertEqual('Tor Disconnected (22:43 04/09/2016, press r to reconnect)', test.render(nyx.panel.header._draw_disconnected, 0, 0, 1460267022.231895).content)

  @require_curses
  def test_draw_resource_usage(self):
    vals = nyx.panel.header.Sampling(
      start_time = 1460166022.231895,
      connection_time = 1460267022.231895,
      is_connected = False,
      tor_cpu = '2.1',
      nyx_cpu = '5.4',
      memory = '118 MB',
      memory_percent = '3.0',
      pid = '22439',
    )

    test_input = {
      80: 'cpu: 2.1% tor, 5.4% nyx    mem: 118 MB (3.0%)  pid: 22439  uptime: 1-04:03:20',
      70: 'cpu: 2.1% tor, 5.4% nyx    mem: 118 MB (3.0%)  pid: 22439',
      60: 'cpu: 2.1% tor, 5.4% nyx    mem: 118 MB (3.0%)  pid: 22439',
      50: 'cpu: 2.1% tor, 5.4% nyx    mem: 118 MB (3.0%)',
      40: 'cpu: 2.1% tor, 5.4% nyx',
      30: 'cpu: 2.1% tor, 5.4% nyx',
      20: '',
      10: '',
      0: '',
    }

    for width, expected in test_input.items():
      self.assertEqual(expected, test.render(nyx.panel.header._draw_resource_usage, 0, 0, width, vals, None).content)

  @require_curses
  def test_draw_fingerprint_and_fd_usage(self):
    vals = nyx.panel.header.Sampling(
      fingerprint = '1A94D1A794FCB2F8B6CBC179EF8FDD4008A98D3B',
      fd_used = None,
    )

    test_input = {
      80: 'fingerprint: 1A94D1A794FCB2F8B6CBC179EF8FDD4008A98D3B',
      70: 'fingerprint: 1A94D1A794FCB2F8B6CBC179EF8FDD4008A98D3B',
      60: 'fingerprint: 1A94D1A794FCB2F8B6CBC179EF8FDD4008A98D3B',
      50: 'fingerprint: 1A94D1A794FCB2F8B6CBC179EF8FDD4008...',
      40: 'fingerprint: 1A94D1A794FCB2F8B6CBC179...',
      30: 'fingerprint: 1A94D1A794FCB2...',
      20: 'fingerprint: 1A94...',
      10: 'fingerp...',
      0: '',
    }

    for width, expected in test_input.items():
      self.assertEqual(expected, test.render(nyx.panel.header._draw_fingerprint_and_fd_usage, 0, 0, width, vals).content)

  @require_curses
  def test_draw_fingerprint_and_fd_usage_with_fd_count(self):
    test_input = {
      59: 'fingerprint: <stub>',
      60: 'fingerprint: <stub>, file descriptors: 60 / 100 (60%)',
      75: 'fingerprint: <stub>, file descriptors: 75 / 100 (75%)',
      89: 'fingerprint: <stub>, file descriptors: 89 / 100 (89%)',
      90: 'fingerprint: <stub>, file descriptors: 90 / 100 (90%)',
      95: 'fingerprint: <stub>, file descriptors: 95 / 100 (95%)',
      99: 'fingerprint: <stub>, file descriptors: 99 / 100 (99%)',
      100: 'fingerprint: <stub>, file descriptors: 100 / 100 (100%)',
    }

    for fd_used, expected in test_input.items():
      vals = nyx.panel.header.Sampling(
        fingerprint = '<stub>',
        fd_used = fd_used,
        fd_limit = 100,
      )

      self.assertEqual(expected, test.render(nyx.panel.header._draw_fingerprint_and_fd_usage, 0, 0, 80, vals).content)

  @require_curses
  def test_draw_flags(self):
    self.assertEqual('flags: none', test.render(nyx.panel.header._draw_flags, 0, 0, []).content)
    self.assertEqual('flags: Guard', test.render(nyx.panel.header._draw_flags, 0, 0, ['Guard']).content)
    self.assertEqual('flags: Running, Exit', test.render(nyx.panel.header._draw_flags, 0, 0, ['Running', 'Exit']).content)

  @require_curses
  def test_draw_exit_policy(self):
    self.assertEqual('exit policy:', test.render(nyx.panel.header._draw_exit_policy, 0, 0, None).content)
    self.assertEqual('exit policy: reject *:*', test.render(nyx.panel.header._draw_exit_policy, 0, 0, stem.exit_policy.ExitPolicy('reject *:*')).content)
    self.assertEqual('exit policy: accept *:80, accept *:443, reject *:*', test.render(nyx.panel.header._draw_exit_policy, 0, 0, stem.exit_policy.ExitPolicy('accept *:80', 'accept *:443', 'reject *:*')).content)

  @require_curses
  def test_draw_newnym_option(self):
    self.assertEqual("press 'n' for a new identity", test.render(nyx.panel.header._draw_newnym_option, 0, 0, 0).content)
    self.assertEqual('building circuits, available again in 1 second', test.render(nyx.panel.header._draw_newnym_option, 0, 0, 1).content)
    self.assertEqual('building circuits, available again in 5 seconds', test.render(nyx.panel.header._draw_newnym_option, 0, 0, 5).content)

  @require_curses
  @patch('nyx.panel.header.nyx_interface')
  def test_draw_status(self, nyx_interface_mock):
    nyx_interface_mock().get_page.return_value = 1
    nyx_interface_mock().page_count.return_value = 4

    self.assertEqual('page 2 / 4 - m: menu, p: pause, h: page help, q: quit', test.render(nyx.panel.header._draw_status, 0, 0, False, None).content)
    self.assertEqual('Paused', test.render(nyx.panel.header._draw_status, 0, 0, True, None).content)
    self.assertEqual('pepperjack is wonderful!', test.render(nyx.panel.header._draw_status, 0, 0, False, 'pepperjack is wonderful!').content)
