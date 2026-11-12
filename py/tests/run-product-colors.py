"""Run the real product-color browser checks using Chrome and Python's stdlib."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import base64
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time
import urllib.request

CHROME = Path('C:/Program Files/Google/Chrome/Application/chrome.exe')


class BrowserConnection:
    def __init__(self, url):
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        self.socket = socket.create_connection((parsed.hostname, parsed.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f'GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\n'
                   f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                   f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n')
        self.socket.sendall(request.encode())
        response = b''
        while b'\r\n\r\n' not in response:
            response += self.socket.recv(1)
        if b' 101 ' not in response.splitlines()[0]:
            raise RuntimeError(response.decode())
        self.next_id = 0

    def read(self, count):
        result = b''
        while len(result) < count:
            chunk = self.socket.recv(count - len(result))
            if not chunk:
                raise RuntimeError('Browser closed the connection')
            result += chunk
        return result

    def call(self, method, params=None):
        self.next_id += 1
        message = json.dumps({'id': self.next_id, 'method': method, 'params': params or {}}).encode()
        mask = os.urandom(4)
        size = len(message)
        header = bytes([0x81, 0x80 | size]) if size < 126 else bytes([0x81, 0xfe]) + struct.pack('!H', size)
        self.socket.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(message)))
        fragments = b''
        while True:
            first, second = self.read(2)
            length = second & 127
            if length == 126:
                length = struct.unpack('!H', self.read(2))[0]
            elif length == 127:
                length = struct.unpack('!Q', self.read(8))[0]
            payload = self.read(length)
            if first & 15 == 8:
                raise RuntimeError('Browser closed the websocket')
            fragments += payload
            if not first & 0x80:
                continue
            response = json.loads(fragments)
            fragments = b''
            if response.get('id') == self.next_id:
                if 'error' in response:
                    raise RuntimeError(response['error'])
                return response.get('result', {})


def main():
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    profile = ROOT / 'tmp' / 'color-browser-profile'
    profile.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen([
        str(CHROME), '--headless', '--disable-gpu', '--no-first-run',
        '--no-default-browser-check', '--allow-file-access-from-files',
        f'--remote-debugging-port={port}', f'--user-data-dir={profile}', 'about:blank',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    connection = None
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=1) as response:
                    pages = json.load(response)
                page = next(p for p in pages if p['type'] == 'page')
                break
            except (OSError, StopIteration):
                if time.monotonic() > deadline:
                    raise RuntimeError('Chrome did not start')
                time.sleep(.1)
        connection = BrowserConnection(page['webSocketDebuggerUrl'])
        connection.call('Network.enable')
        connection.call('Network.setBlockedURLs', {'urls': ['*fonts.googleapis.com*', '*fonts.gstatic.com*']})
        connection.call('Page.navigate', {'url': (ROOT / 'py/tests' / 'product-colors.html').as_uri()})
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            response = connection.call('Runtime.evaluate', {
                'expression': 'document.querySelector("#results")?.textContent || "Loading"',
                'returnByValue': True,
            })
            result = response.get('result', {}).get('value', '')
            if result.startswith(('PASS:', 'FAIL:')):
                (ROOT / 'tmp' / 'product-color-check-results.txt').write_text(result, encoding='utf-8')
                print(result.splitlines()[0])
                if result.startswith('FAIL:'):
                    print(result)
                    raise SystemExit(1)
                return
            time.sleep(.1)
        raise RuntimeError('Product-color checks timed out')
    finally:
        if connection:
            connection.socket.close()
        process.terminate()
        process.wait(timeout=10)


if __name__ == '__main__':
    main()
