"""Own a real isolated API/schema while Playwright owns its Vite/browser processes.

Run from backend: uv run --locked python ../scripts/test_frontend_e2e.py
Requires a prepared localhost *_test database and installed Playwright Chromium.
No development credentials or bearer tokens are passed in arguments or written to reports.
"""

import argparse
import logging
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time

import uvicorn

from serve_frontend_check import browser_fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Never attach the tests to an unrelated existing server.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 8766))
    options = argparse.Namespace(read_delay_ms=0, extra_tickets=24, session_minutes=30,
                                 lose_first_write_response=False, write_delay_ms=0)
    with browser_fixture(options) as app:
        # Request logs remain redacted, but are not needed in routine test output.
        logging.getLogger('supportops.requests').setLevel(logging.WARNING)
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8766,
                                proxy_headers=False, access_log=False, log_level='warning'))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 30
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError('The owned E2E API failed to start')
                time.sleep(0.05)
            node = shutil.which('node')
            if not node:
                raise RuntimeError('Node.js is required for Playwright')
            cli = ROOT / 'frontend' / 'node_modules' / '@playwright' / 'test' / 'cli.js'
            result = subprocess.run([node, str(cli), 'test', *sys.argv[1:]], cwd=ROOT / 'frontend', check=False)
            return result.returncode
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            if thread.is_alive():
                raise RuntimeError('The owned E2E API did not stop; inspect before cleanup')
    # The fixture context drops only its generated schema, including on test failure.


if __name__ == '__main__':
    raise SystemExit(main())
