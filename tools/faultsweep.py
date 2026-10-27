#!/usr/bin/env python3
"""Run wermit scenarios with one library call failing at a time.

The sweep preloads tests/faultinj.c into wermit.  For each scenario and
each failing function it first counts the calls, then reruns the
scenario with call N failing, for a sample of N.  Each run is classified:

  signal    wermit died from a signal (a crash).
  hang      wermit did not exit within the time limit.
  ok        wermit exited and printed the scenario's success marker.
  fail      wermit exited without the success marker.

"signal" and "hang" are defects.  "ok" after a failed call can be a
silent success and is listed for review.

Usage: faultsweep.py WERMIT OUTDIR [SCENARIO ...]
"""
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'tests', 'faultinj.c')
FUNCS = ('malloc', 'open', 'read', 'readeof', 'write')
MARK = 'SWEEP-OK'
TIMEOUT = 20


def build_lib(outdir):
    """Compile faultinj.c into OUTDIR and return the library path."""
    lib = os.path.join(outdir, 'faultinj.so')
    subprocess.run(['cc', '-O1', '-shared', '-fPIC', '-o', lib, SRC,
                    '-ldl'], check=True)
    return lib


def free_port():
    """Return a TCP port that is free now."""
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Quiet(http.server.SimpleHTTPRequestHandler):
    """Serve files from the scenario directory without logging."""

    def log_message(self, *args):
        pass


def http_server(root):
    """Start an HTTP server on root.  Return (server, port)."""
    port = free_port()

    def handler(*a, **k):
        return Quiet(*a, directory=root, **k)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def telnet_server():
    """Start a peer that sends a banner and echoes.  Return (sock, port)."""
    port = free_port()
    ls = socket.socket()
    ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ls.bind(('127.0.0.1', port))
    ls.listen(8)

    def serve():
        while True:
            try:
                c, _ = ls.accept()
            except OSError:
                return
            c.settimeout(5)
            try:
                c.sendall(b'\xff\xfb\x01\xff\xfb\x03login: ')
                while True:
                    d = c.recv(4096)
                    if not d:
                        break
                    c.sendall(d)
            except OSError:
                pass
            c.close()
    threading.Thread(target=serve, daemon=True).start()
    return ls, port


def scenario(name, work, wermit):
    """Return (command string, cleanup) for a scenario in work."""
    with open(os.path.join(work, 'f.txt'), 'w') as f:
        f.write('line one\nline two\n' * 200)
    if name == 'script':
        return ('declare \\&a[20], for \\%i 1 20 1 { .\\&a[\\%i] := x\\%i }, '
                'define sweepmac '
                '{ .r := \\fsubstr(\\%1,2,3)\\flength(\\%2) }, '
                'sweepmac abcdef, .s := \\fjoin(&a,:), '
                'if equal \\fword(a b c,2) b echo ' + MARK, None)
    if name == 'file':
        return ('cd ' + work + ', copy f.txt g.txt, type /head:2 g.txt, '
                'directory, grep /array:&g line f.txt, '
                'if > \\fdim(&g) 300 echo ' + MARK, None)
    if name == 'transfer':
        srv = os.path.join(work, 'srv.ksc')
        os.makedirs(os.path.join(work, 's'), exist_ok=True)
        with open(srv, 'w') as f:
            f.write('cd %s/s\nset delay 0\nserver\n' % work)
        return ('cd ' + work + ', set delay 0, set host '
                '/network-type:pseudoterminal ' + wermit + ' ' + srv +
                ', send f.txt, if success echo ' + MARK +
                ', finish, close', None)
    if name == 'http':
        srv, port = http_server(work)
        return ('cd ' + work + ', http open 127.0.0.1 %d, '
                'http get /f.txt out.txt, if success echo %s, http close'
                % (port, MARK), srv.shutdown)
    if name == 'telnet':
        ls, port = telnet_server()
        return ('set host 127.0.0.1 %d /telnet, if fail exit 1, '
                'output hello\\13, input 5 hello, if success echo %s, '
                'close' % (port, MARK), ls.close)
    raise ValueError(name)


def run(wermit, lib, name, func, n, outdir):
    """Run one scenario with call n of func failing.

    Return (classification, number of calls counted).
    """
    work = tempfile.mkdtemp(prefix='fs-', dir=outdir)
    try:
        cmd, cleanup = scenario(name, work, wermit)
        report = os.path.join(work, 'count')
        env = dict(os.environ, LD_PRELOAD=lib, FAULT_FUNC=func,
                   FAULT_N=str(n), FAULT_REPORT=report, HOME=work)
        try:
            p = subprocess.run([wermit, '-H', '-Y', '-Q', '-C',
                                cmd + ', exit 0'], cwd=work, env=env,
                               stdin=subprocess.DEVNULL,
                               capture_output=True, timeout=TIMEOUT)
            if p.returncode < 0:
                cls = 'signal%d' % -p.returncode
            elif MARK.encode() in p.stdout:
                cls = 'ok'
            else:
                cls = 'fail'
        except subprocess.TimeoutExpired:
            cls = 'hang'
        if cleanup:
            cleanup()
        calls = 0
        try:
            with open(report) as f:
                calls = int(f.read().strip() or 0)
        except (OSError, ValueError):
            pass
        return cls, calls
    finally:
        shutil.rmtree(work, ignore_errors=True)


def sample(total):
    """Return the call numbers to fail for a scenario with total calls."""
    if total <= 120:
        return list(range(1, total + 1))
    first = list(range(1, 41))
    step = max(1, (total - 40) // 80)
    return first + list(range(41, total + 1, step))


def main():
    wermit, outdir = os.path.abspath(sys.argv[1]), sys.argv[2]
    names = sys.argv[3:] or ['script', 'file', 'transfer', 'http',
                             'telnet']
    os.makedirs(outdir, exist_ok=True)
    lib = build_lib(outdir)
    results = {}
    for name in names:
        for func in FUNCS:
            base, total = run(wermit, lib, name, func, 0, outdir)
            rows = []
            for n in sample(total):
                cls, _ = run(wermit, lib, name, func, n, outdir)
                rows.append((n, cls))
            key = '%s/%s' % (name, func)
            results[key] = {'baseline': base, 'calls': total,
                            'runs': rows}
            bad = [r for r in rows if r[1].startswith(('signal', 'hang'))]
            print('%-18s base=%-5s calls=%-6d runs=%-4d bad=%s' %
                  (key, base, total, len(rows), bad[:8]), flush=True)
    with open(os.path.join(outdir, 'results.json'), 'w') as f:
        json.dump(results, f, indent=1)


if __name__ == '__main__':
    main()
