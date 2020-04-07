# Copyright 2013-2020, Damian Johnson and The Tor Project
# See LICENSE for licensing information

"""
Commandline argument parsing for nyx.
"""

import collections
import getopt
import os

import nyx
import nyx.log

import stem.util.connection

DEFAULT_ARGS = {
  'control_port': ('127.0.0.1', 'default'),
  'control_socket': '/var/run/tor/control',
  'config': os.path.join(os.path.expanduser('~/.nyx'), 'config'),
  'debug_path': None,
  'logged_events': 'NOTICE,WARN,ERR,NYX_NOTICE,NYX_WARNING,NYX_ERROR',
  'print_version': False,
  'print_help': False,
}

OPT = 'i:s:c:d:l:vh'

OPT_EXPANDED = [
  'interface=',
  'socket=',
  'config=',
  'debug=',
  'log=',
  'version',
  'help',
]

HELP_OUTPUT = """
Usage nyx [OPTION]
Terminal status monitor for Tor relays.

  -i, --interface [ADDRESS:]PORT  change control interface from {address}:{port}
  -s, --socket SOCKET_PATH        attach using unix domain socket if present,
                                    SOCKET_PATH defaults to: {socket}
  -c, --config CONFIG_PATH        loaded configuration options, CONFIG_PATH
                                    defaults to: {config_path}
  -d, --debug LOG_PATH            writes all nyx logs to the given location
  -l, --log EVENTS                comma separated list of events to log
  -v, --version                   provides version information
  -h, --help                      presents this help

Example:
nyx -i 1643             attach to control port 1643
nyx -l we -c /tmp/cfg   use this configuration file with 'WARN'/'ERR' events
""".strip()


def parse(argv):
  """
  Parses our arguments, providing a named tuple with their values.

  :param list argv: input arguments to be parsed

  :returns: a **named tuple** with our parsed arguments

  :raises: **ValueError** if we got an invalid argument
  """

  args = dict(DEFAULT_ARGS)

  try:
    recognized_args, unrecognized_args = getopt.getopt(argv, OPT, OPT_EXPANDED)

    if unrecognized_args:
      error_msg = "aren't recognized arguments" if len(unrecognized_args) > 1 else "isn't a recognized argument"
      raise getopt.GetoptError("'%s' %s" % ("', '".join(unrecognized_args), error_msg))
  except getopt.GetoptError as exc:
    raise ValueError('%s (for usage provide --help)' % exc)

  has_port_arg, has_socket_arg = False, False

  for opt, arg in recognized_args:
    if opt in ('-i', '--interface'):
      address = None

      if ':' in arg:
        address, port = arg.split(':', 1)
      else:
        port = arg

      if address:
        if not stem.util.connection.is_valid_ipv4_address(address):
          raise ValueError("'%s' isn't a valid IPv4 address" % address)
      else:
        address = args['control_port'][0]

      if not stem.util.connection.is_valid_port(port):
        raise ValueError("'%s' isn't a valid port number" % port)

      args['control_port'] = (address, int(port))
      has_port_arg = True
    elif opt in ('-s', '--socket'):
      args['control_socket'] = arg
      has_socket_arg = True
    elif opt in ('-c', '--config'):
      args['config'] = arg
    elif opt in ('-d', '--debug'):
      args['debug_path'] = os.path.expanduser(arg)
    elif opt in ('-l', '--log'):
      args['logged_events'] = arg
    elif opt in ('-v', '--version'):
      args['print_version'] = True
    elif opt in ('-h', '--help'):
      args['print_help'] = True

  # If the user explicitely specified an endpoint then just try to connect to
  # that.

  if has_socket_arg and not has_port_arg:
    args['control_port'] = None
  elif has_port_arg and not has_socket_arg:
    args['control_socket'] = None

  # translates our args dict into a named tuple

  Args = collections.namedtuple('Args', args.keys())
  return Args(**args)


def get_help():
  """
  Provides our --help usage information.

  :returns: **str** with our usage information
  """

  return HELP_OUTPUT.format(
    address = DEFAULT_ARGS['control_port'][0],
    port = DEFAULT_ARGS['control_port'][1],
    socket = DEFAULT_ARGS['control_socket'],
    config_path = DEFAULT_ARGS['config'],
  )


def get_version():
  """
  Provides our --version information.

  :returns: **str** with our versioning information
  """

  return 'nyx version %s (released %s)\n' % (nyx.__version__, nyx.__release_date__)
