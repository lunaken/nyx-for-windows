# nyx-for-windows
## Nyx (Tor Command-line Monitor) for Windows
### Installation
* Test Environment : Windowns 10 Pro, Python 3.8.1 64-bit
1. Install stem (Dependency Package)
2. Install curses wrapper
    * Download curses https://download.lfd.uci.edu/pythonlibs/s2jqpv5t/curses-2.2.1+utf8-cp38-cp38-win_amd64.whl
    * Find other versions : https://www.lfd.uci.edu/~gohlke/pythonlibs/#curses
    * python -m pip install curses-2.2.1+utf8-cp38-cp38-win_amd64.whl
3. Clone this source
4. python -m setup.py build
5. python -m setup.py install
6. Enjoy!

### Modification from Origin Nyx
1. no module named '_curses' --> Use curses wrapper
2. os.uname() --> platform.uname()
   * need "import platform"
3. os.getuid() --> Disable (Be Comment)
