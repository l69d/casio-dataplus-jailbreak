#!/usr/bin/env python3
"""Read-only crawler for a Casio EX-word, driving libexword's `exword` shell.

Connects in one mode, walks every storage medium and folder the device lets
it enter, and copies every readable file to dumps/<mode>/<medium>/...
Only read-only commands can be sent (SAFE); anything else raises.

    ./crawl.py [library|text|cd]    # transcript on stdout
    ./crawl.py --selftest           # parser check, no device needed
"""
import os
import re
import select
import subprocess
import sys

SAFE = {'connect', 'list', 'capacity', 'model', 'setpath', 'get', 'disconnect'}
HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, 'libexword', 'src', 'exword')
MAX_DEPTH = 8


def parse_list(text):
    """`list` output -> (dirs, files). Dirs are <name>; a leading * marks a unicode name.
    Anything but a successful listing (e.g. "Forbidden") yields nothing."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines or lines[-1] != 'OK, Success':
        return [], []
    dirs, files = [], []
    for line in lines[:-1]:
        m = re.fullmatch(r'<\*?(.+)>', line)
        if m:
            dirs.append(m.group(1))
        else:
            files.append(line.lstrip('*'))
    return dirs, files


class Shell:
    def __init__(self):
        self.p = subprocess.Popen([EXE], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._read()  # banner + first prompt

    def _read(self, timeout=120):
        fd, buf = self.p.stdout.fileno(), b''
        while not buf.endswith(b'>> '):
            if not select.select([fd], [], [], timeout)[0]:
                raise TimeoutError(buf.decode('utf-8', 'replace'))
            chunk = os.read(fd, 4096)
            if not chunk:
                raise EOFError(buf.decode('utf-8', 'replace'))
            buf += chunk
        return buf.decode('utf-8', 'replace')

    def run(self, cmd):
        if cmd.split()[0] not in SAFE:
            raise ValueError(f'refusing non-read-only command: {cmd}')
        self.p.stdin.write((cmd + '\n').encode())
        self.p.stdin.flush()
        out = self._read()
        sys.stdout.write(out)
        sys.stdout.flush()
        return '\n'.join(out.split('\n')[1:-1])  # drop echoed command and next prompt


def crawl(sh, path, local, depth=0):
    if sh.run(f'setpath raw://{path}').strip():  # setpath prints nothing on success
        return
    dirs, files = parse_list(sh.run('list'))
    if files:
        os.makedirs(local, exist_ok=True)
    for f in files:  # before recursing: get reads from the device's current folder
        sh.run(f'get {os.path.join(local, f)}')
    if depth < MAX_DEPTH:
        for d in dirs:
            crawl(sh, f'{path}\\{d}', os.path.join(local, d), depth + 1)


def main(mode):
    sh = Shell()
    if 'done' not in sh.run(f'connect {mode}'):
        sh.p.kill()
        sys.exit('connect failed')
    try:
        sh.run('model')
        sh.run('setpath raw://')
        dirs, files = parse_list(sh.run('list'))
        for medium in dirs + files:
            crawl(sh, '\\' + medium, os.path.join(HERE, 'dumps', mode, medium))
        sh.run('setpath raw://\\_INTERNAL_00')
        sh.run('list')  # unlocks capacity (auth quirk)
        sh.run('capacity')
    finally:
        try:
            sh.run('disconnect')
        finally:
            sh.p.kill()


def selftest():
    sample = '<sys_bak>\nfav.inf\n<*uni dir>\n*uni.txt\nOK, Success\n'
    assert parse_list(sample) == (['sys_bak', 'uni dir'], ['fav.inf', 'uni.txt']), parse_list(sample)
    assert parse_list('Forbidden') == ([], [])
    assert parse_list('_INTERNAL_00\nOK, Success') == ([], ['_INTERNAL_00'])
    try:
        Shell.run(None, 'delete fav.inf')
        raise AssertionError('unsafe command was not refused')
    except ValueError:
        pass
    print('selftest ok')


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else 'library'
    if arg == '--selftest':
        selftest()
    elif arg in ('library', 'text', 'cd'):
        main(arg)
    else:
        sys.exit(__doc__)
