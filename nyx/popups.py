# Copyright 2011-2020, Damian Johnson and The Tor Project
# See LICENSE for licensing information

"""
Popup dialogs provided by our interface.

::

  show_help - keybindings provided by the current page
  show_about - basic information about our application
  show_counts - listing of counts with bar graphs
  show_descriptor - presents descriptors for a relay

  select_from_list - selects from a list of options
  select_sort_order - selects attributes by which to sort by
  select_event_types - select from a list of event types

  confirm_save_torrc - confirmation dialog for saving the torrc
"""

from __future__ import absolute_import

import curses
import math
import operator

import nyx
import nyx.arguments
import nyx.curses
import nyx.log
import nyx.panel

from nyx import nyx_interface
from nyx.curses import RED, GREEN, YELLOW, CYAN, WHITE, NORMAL, BOLD, HIGHLIGHT

import stem.control
import stem.util.str_tools

NO_STATS_MSG = "Usage stats aren't available yet, press any key..."

HEADERS = ['Consensus:', 'Microdescriptor:', 'Server Descriptor:']
HEADER_COLOR = CYAN
LINE_NUMBER_COLOR = YELLOW

BLOCK_START, BLOCK_END = '-----BEGIN ', '-----END '

UNRESOLVED_MSG = 'No consensus data available'
ERROR_MSG = 'Unable to retrieve data'


def show_help():
  """
  Presents a popup with the current page's hotkeys.

  :returns: :class:`~nyx.curses.KeyInput` that was pressed to close the popup
    if it's one panels should act upon, **None** otherwise
  """

  interface = nyx_interface()
  handlers = []

  for panel in reversed(interface.page_panels()[1:]):
    handlers += [handler for handler in panel.key_handlers() if handler.description]

  def _render(subwindow):
    subwindow.box()
    subwindow.addstr(0, 0, 'Page %i Commands:' % (interface.get_page() + 1), HIGHLIGHT)

    for i, option in enumerate(handlers):
      if i // 2 >= subwindow.height - 2:
        break

      # Entries are shown in the form '<key>: <description>[ (<selection>)]',
      # such as...
      #
      #   u: duplicate log entries (hidden)

      x = 2 if i % 2 == 0 else 41
      y = (i // 2) + 1

      x = subwindow.addstr(x, y, option.key, BOLD)
      x = subwindow.addstr(x, y, ': ' + option.description)

      if option.current:
        x = subwindow.addstr(x, y, ' (')
        x = subwindow.addstr(x, y, option.current, BOLD)
        x = subwindow.addstr(x, y, ')')

    # tells user to press a key if the lower left is unoccupied

    if len(handlers) < 13 and subwindow.height == 9:
      subwindow.addstr(2, 7, 'Press any key...')

  with nyx.curses.CURSES_LOCK:
    nyx.curses.draw(_render, top = _top(), width = 80, height = 9)
    keypress = nyx.curses.key_input()

  if keypress.is_selection() or keypress.is_scroll() or keypress.match('left', 'right'):
    return None
  else:
    return keypress


def show_about():
  """
  Presents a popup with author and version information.
  """

  def _render(subwindow):
    subwindow.box()
    subwindow.addstr(0, 0, 'About:', HIGHLIGHT)
    subwindow.addstr(2, 1, 'Nyx, version %s (released %s)' % (nyx.__version__, nyx.__release_date__), BOLD)
    subwindow.addstr(4, 2, 'Written by Damian Johnson (atagar@torproject.org)')
    subwindow.addstr(4, 3, 'Project page: %s' % nyx.__url__)
    subwindow.addstr(2, 5, 'Released under the GPL v3 (http://www.gnu.org/licenses/gpl.html)')
    subwindow.addstr(2, 7, 'Press any key...')

  with nyx.curses.CURSES_LOCK:
    nyx.curses.draw(_render, top = _top(), width = 80, height = 9)
    nyx.curses.key_input()


def show_counts(title, counts, fill_char = ' '):
  """
  Provides a dialog with bar graphs and percentages for the given set of
  counts. Pressing any key closes the dialog.

  :param str title: dialog title
  :param dict counts: mapping of labels to their value
  :param str fill_char: character to use for rendering the bar graph
  """

  def _render_no_stats(subwindow):
    subwindow.box()
    subwindow.addstr(0, 0, title, HIGHLIGHT)
    subwindow.addstr(2, 1, NO_STATS_MSG, CYAN, BOLD)

  def _render_stats(subwindow):
    key_width, val_width, value_total = 3, 1, 0

    for k, v in counts.items():
      key_width = max(key_width, len(k))
      val_width = max(val_width, len(str(v)))
      value_total += v

    subwindow.box()
    subwindow.addstr(0, 0, title, HIGHLIGHT)

    graph_width = subwindow.width - key_width - val_width - 11  # border, extra spaces, and percentage column
    sorted_counts = sorted(counts.items(), key = operator.itemgetter(1), reverse = True)

    for y, (k, v) in enumerate(sorted_counts):
      label = '%s %s (%-2i%%)' % (k.ljust(key_width), str(v).rjust(val_width), v * 100 // value_total)
      x = subwindow.addstr(2, y + 1, label, GREEN, BOLD)

      for j in range(graph_width * v // value_total):
        subwindow.addstr(x + j + 1, y + 1, fill_char, RED, HIGHLIGHT)

    subwindow.addstr(2, subwindow.height - 2, 'Press any key...')

  with nyx.curses.CURSES_LOCK:
    if not counts:
      nyx.curses.draw(_render_no_stats, top = _top(), width = len(NO_STATS_MSG) + 4, height = 3)
    else:
      nyx.curses.draw(_render_stats, top = _top(), width = 80, height = 4 + max(1, len(counts)))

    nyx.curses.key_input()


def show_descriptor(fingerprint, color, is_close_key):
  """
  Provides a dialog showing descriptors for a relay.

  :param str fingerprint: fingerprint of the relay to be shown
  :param str color: text color of the dialog
  :param function is_close_key: method to indicate if a key should close the
    dialog or not

  :returns: :class:`~nyx.curses.KeyInput` for the keyboard input that
    closed the dialog
  """

  if fingerprint:
    title = 'Consensus Descriptor (%s):' % fingerprint
    lines = _descriptor_text(fingerprint)
    show_line_numbers = True
  else:
    title = 'Consensus Descriptor:'
    lines = [UNRESOLVED_MSG]
    show_line_numbers = False

  scroller = nyx.curses.Scroller()
  line_number_width = int(math.log10(len(lines))) + 1 if show_line_numbers else 0

  def _render(subwindow):
    in_block = False   # flag indicating if we're currently in crypto content
    y, offset = 1, line_number_width + 3 if show_line_numbers else 2

    for i, line in enumerate(lines):
      keyword, value = line, ''
      line_color = color

      if line in HEADERS:
        line_color = HEADER_COLOR
      elif line.startswith(BLOCK_START):
        in_block = True
      elif line.startswith(BLOCK_END):
        in_block = False
      elif in_block:
        keyword, value = '', line
      elif ' ' in line and line != UNRESOLVED_MSG and line != ERROR_MSG:
        keyword, value = line.split(' ', 1)
        keyword = keyword + ' '

      if i < scroller.location():
        continue

      if show_line_numbers:
        subwindow.addstr(2, y, str(i + 1).rjust(line_number_width), LINE_NUMBER_COLOR, BOLD)

      x, y = subwindow.addstr_wrap(3 + line_number_width, y, keyword, subwindow.width - 2, offset, line_color, BOLD)
      x, y = subwindow.addstr_wrap(x, y, value, subwindow.width - 2, offset, line_color)
      y += 1

      if y > subwindow.height - 2:
        break

    subwindow.box()
    subwindow.addstr(0, 0, title, HIGHLIGHT)

  width, height = len(title), len(lines) + 2
  screen_size = nyx.curses.screen_size()

  for line in lines:
    width = min(screen_size.width, max(width, len(line) + line_number_width + 5))
    height += len(line) // (screen_size.width - line_number_width - 5)  # extra lines due to text wrap

  with nyx.curses.CURSES_LOCK:
    nyx.curses.draw(lambda subwindow: subwindow.addstr(0, 0, ' ' * 500), top = _top(), height = 1)  # hides title below us
    nyx.curses.draw(_render, top = _top(), width = width, height = height)
    popup_height = min(screen_size.height - _top(), height)

    while True:
      key = nyx.curses.key_input()

      if key.is_scroll():
        is_changed = scroller.handle_key(key, len(lines), popup_height - 2)

        if is_changed:
          nyx.curses.draw(_render, top = _top(), width = width, height = height)
      elif is_close_key(key):
        return key


def _descriptor_text(fingerprint):
  """
  Provides the descriptors for a relay.

  :param str fingerprint: relay fingerprint to be looked up

  :returns: **list** with the lines that should be displayed in the dialog
  """

  controller = nyx.tor_controller()
  router_status_entry = controller.get_network_status(fingerprint, None)
  microdescriptor = controller.get_microdescriptor(fingerprint, None)
  server_descriptor = controller.get_server_descriptor(fingerprint, None)

  description = 'Consensus:\n\n%s' % (router_status_entry if router_status_entry else ERROR_MSG)

  if server_descriptor:
    description += '\n\nServer Descriptor:\n\n%s' % server_descriptor

  if microdescriptor:
    description += '\n\nMicrodescriptor:\n\n%s' % microdescriptor

  return description.split('\n')


def select_from_list(title, options, previous_selection):
  """
  Provides list of items the user can choose from.

  :param str title: dialog title
  :param list options: options that can be selected from
  :param str previous_selection: previously selected option

  :returns: **str** of selection or **previous_selection** if dialog is canceled
  """

  selected_index = options.index(previous_selection) if previous_selection in options else 0

  def _render(subwindow):
    subwindow.box()
    subwindow.addstr(0, 0, title, HIGHLIGHT)

    for i, option in enumerate(options):
      if option == previous_selection:
        subwindow.addstr(2, i + 1, '> ')

      attr = HIGHLIGHT if i == selected_index else NORMAL
      subwindow.addstr(4, i + 1, ' %s ' % option, attr)

  with nyx.curses.CURSES_LOCK:
    while True:
      nyx.curses.draw(lambda subwindow: subwindow.addstr(0, 0, ' ' * 500), top = _top(), height = 1)  # hides title below us
      nyx.curses.draw(_render, top = _top(), width = max(map(len, options)) + 9, height = len(options) + 2)
      key = nyx.curses.key_input()

      if key.match('up'):
        selected_index = max(0, selected_index - 1)
      elif key.match('down'):
        selected_index = min(len(options) - 1, selected_index + 1)
      elif key.is_selection():
        return options[selected_index]
      elif key.match('esc'):
        return previous_selection


def select_sort_order(title, options, previous_order, option_colors):
  """
  Provides sorting dialog of the form...

    Current Order: <previous order>
    New Order: <selected options>

    <option 1>    <option 2>    <option 3>   Cancel

  :param str title: dialog title
  :param list options: sort options to be provided
  :param list previous_order: previous ordering
  :param dict option_colors: mapping of options to their color

  :returns: **list** of the new sort order or **None** if dialog is canceled
  """

  new_order = []
  cursor_index = 0
  shown_options = list(options) + ['Cancel']

  def _draw_selection(subwindow, y, label, selection):
    x = subwindow.addstr(2, y, label, BOLD)

    for i, option in enumerate(selection):
      x = subwindow.addstr(x, y, option, option_colors.get(option, WHITE), BOLD)

      if i < len(selection) - 1:
        x = subwindow.addstr(x, y, ', ', BOLD)

  def _render(subwindow):
    subwindow.box()
    subwindow.addstr(0, 0, title, HIGHLIGHT)

    _draw_selection(subwindow, 1, 'Current Order: ', previous_order)
    _draw_selection(subwindow, 2, 'New Order: ', new_order)

    # presents remaining options, each row having up to four options

    for i, option in enumerate(shown_options):
      attr = HIGHLIGHT if i == cursor_index else NORMAL
      subwindow.addstr((i % 4) * 19 + 2, (i // 4) + 4, option, attr)

  with nyx.curses.CURSES_LOCK:
    while len(new_order) < len(previous_order):
      nyx.curses.draw(_render, top = _top(), width = 80, height = 9)
      key = nyx.curses.key_input()

      if key.match('left'):
        cursor_index = max(0, cursor_index - 1)
      elif key.match('right'):
        cursor_index = min(len(shown_options) - 1, cursor_index + 1)
      elif key.match('up'):
        cursor_index = max(0, cursor_index - 4)
      elif key.match('down'):
        cursor_index = min(len(shown_options) - 1, cursor_index + 4)
      elif key.is_selection():
        selection = shown_options[cursor_index]

        if selection == 'Cancel':
          return None
        else:
          new_order.append(selection)
          shown_options.remove(selection)
          cursor_index = min(cursor_index, len(shown_options) - 1)
      elif key.match('esc'):
        return None

  return new_order


def select_event_types(initial_selection):
  """
  Presents chart of events for the user to select from.

  :param list initial_selection: initial events to be checked

  :returns: **set** of event types the user has selected or **None** if dialog
    is canceled
  """

  event_names = nyx.tor_controller().get_info('events/names', None)

  if not event_names:
    return

  selection = 0
  selected_events = list(initial_selection)
  events = [event for event in event_names.split() if event not in nyx.log.TOR_RUNLEVELS]

  def _render(subwindow):
    subwindow.box()
    subwindow.addstr(0, 0, 'Event Types:', HIGHLIGHT)

    if selection < 10:
      description = stem.control.event_description(nyx.log.TOR_RUNLEVELS[selection % 5])
    elif selection < (len(events) + 10):
      description = stem.control.event_description(events[selection - 10])
    else:
      description = None

    if description:
      subwindow.addstr_wrap(1, 1, description, subwindow.width - 1, 1, GREEN, BOLD)

    subwindow.hline(1, 3, 78)
    subwindow._addch(0, 3, curses.ACS_LTEE)
    subwindow._addch(79, 6, curses.ACS_RTEE)

    x = subwindow.addstr(1, 4, 'Tor Runlevel:')

    for i, event in enumerate(nyx.log.TOR_RUNLEVELS):
      x = subwindow.addstr(x + 4, 4, '[X]' if event in selected_events else '[ ]')
      x = subwindow.addstr(x + 1, 4, event, HIGHLIGHT if selection == i else NORMAL)

    x = subwindow.addstr(1, 5, 'Nyx Runlevel:')

    for i, event in enumerate(nyx.log.NYX_RUNLEVELS):
      x = subwindow.addstr(x + 4, 5, '[X]' if event in selected_events else '[ ]')
      x = subwindow.addstr(x + 1, 5, nyx.log.TOR_RUNLEVELS[i], HIGHLIGHT if selection == (i + 5) else NORMAL)

    subwindow.hline(1, 6, 78)
    subwindow._addch(0, 6, curses.ACS_LTEE)
    subwindow._addch(79, 6, curses.ACS_RTEE)

    for i, event in enumerate(events):
      x = subwindow.addstr((i % 3) * 25 + 1, i // 3 + 7, '[X]' if event in selected_events else '[ ]')
      x = subwindow.addstr(x + 1, i // 3 + 7, event, HIGHLIGHT if selection == (i + 10) else NORMAL)

    x = subwindow.width - 14

    for i, option in enumerate(['Ok', 'Cancel']):
      x = subwindow.addstr(x, subwindow.height - 2, '[')
      x = subwindow.addstr(x, subwindow.height - 2, option, BOLD, HIGHLIGHT if selection == len(events) + 10 + i else NORMAL)
      x = subwindow.addstr(x, subwindow.height - 2, ']') + 1

  with nyx.curses.CURSES_LOCK:
    while True:
      nyx.curses.draw(_render, top = _top(), width = 80, height = (len(events) // 3) + 10)
      key = nyx.curses.key_input()

      if key.match('up'):
        if selection < 5:
          pass
        elif selection < 10:
          selection -= 5
        elif selection < 13:
          selection = 5
        elif selection < len(events) + 10:
          selection -= 3
        else:
          selection = len(events) + 9
      elif key.match('down'):
        if selection < 10:
          selection = min(selection + 5, 10)
        elif selection < len(events) + 10:
          selection = min(selection + 3, len(events) + 10)
      elif key.match('left'):
        selection = max(selection - 1, 0)
      elif key.match('right'):
        selection = min(selection + 1, len(events) + 11)
      elif key.is_selection():
        if selection < 5:
          selected_event = nyx.log.TOR_RUNLEVELS[selection]
        elif selection < 10:
          selected_event = nyx.log.NYX_RUNLEVELS[selection - 5]
        elif selection == len(events) + 10:
          return set(selected_events)  # selected 'Ok'
        elif selection == len(events) + 11:
          return None  # selected 'Cancel'
        else:
          selected_event = events[selection - 10]

        if selected_event in selected_events:
          selected_events.remove(selected_event)
        else:
          selected_events.append(selected_event)
      elif key.match('esc'):
        return None


def confirm_save_torrc(torrc):
  """
  Provides a confirmation dialog for saving tor's current configuration.

  :param str torrc: torrc that would be saved

  :returns: **True** if the torrc should be saved and **False** otherwise
  """

  torrc_lines = torrc.splitlines() if torrc else []
  selection = 1

  def _render(subwindow):
    for i, full_line in enumerate(torrc_lines):
      line = stem.util.str_tools.crop(full_line, subwindow.width - 2)
      option, arg = line.split(' ', 1) if ' ' in line else (line, '')

      subwindow.addstr(1, i + 1, option, GREEN, BOLD)
      subwindow.addstr(len(option) + 2, i + 1, arg, CYAN, BOLD)

    x = subwindow.width - 16

    for i, option in enumerate(['Save', 'Cancel']):
      x = subwindow.addstr(x, subwindow.height - 2, '[')
      x = subwindow.addstr(x, subwindow.height - 2, option, BOLD, HIGHLIGHT if i == selection else NORMAL)
      x = subwindow.addstr(x, subwindow.height - 2, '] ')

    subwindow.box()
    subwindow.addstr(0, 0, 'Torrc to save:', HIGHLIGHT)

  with nyx.curses.CURSES_LOCK:
    while True:
      nyx.curses.draw(_render, top = _top(), height = len(torrc_lines) + 2)
      key = nyx.curses.key_input()

      if key.match('left'):
        selection = max(0, selection - 1)
      elif key.match('right'):
        selection = min(1, selection + 1)
      elif key.is_selection():
        return selection == 0
      elif key.match('esc'):
        return False  # esc - cancel


def _top():
  return nyx_interface().header_panel().get_height()
