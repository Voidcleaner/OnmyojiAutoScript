"""Authenticated, loopback-only capture bridge for CrossOver's Onmyoji windows."""
import argparse
import hmac
import json
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def find_window(windows, title):
    matches = [w['id'] for w in windows if w['title'] == title]
    if len(matches) != 1:
        raise ValueError('Window title must identify exactly one game window')
    return matches[0]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not hmac.compare_digest(self.headers.get('Authorization', ''),
                                   'Bearer ' + self.server.token):
            self.send_error(403)
            return
        request = urlsplit(self.path)
        if request.path != '/capture':
            self.send_error(404)
            return
        try:
            title = parse_qs(request.query).get('title', [''])[0]
            if not title:
                raise ValueError('An exact, unique window title is required')
            result = subprocess.run([str(self.server.helper)], check=True,
                                    capture_output=True, timeout=5)
            window = find_window(json.loads(result.stdout), title)
            with tempfile.TemporaryDirectory(prefix='oas-capture-') as directory:
                path = Path(directory) / 'frame.png'
                subprocess.run(['/usr/sbin/screencapture', '-x', '-o', '-l',
                                str(window), str(path)], check=True,
                               capture_output=True, timeout=5)
                image = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(image)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(image)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            self.send_error(503, str(exc)[:200])

    def do_POST(self):
        if not hmac.compare_digest(self.headers.get('Authorization', ''),
                                   'Bearer ' + self.server.token):
            self.send_error(403)
            return
        if self.path != '/launch' or not self.server.launch_config:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024:
                raise ValueError('Invalid launch request size')
            title = json.loads(self.rfile.read(length))['title']
            configurations = json.loads(self.server.launch_config.read_text())
            entry = configurations[title]
            # Only an administrator-supplied local map determines executable,
            # bottle and profile. Never accept executable paths from HTTP.
            wine = Path(entry['wine'])
            exe = Path(entry['exe'])
            profile = Path(entry['profile'])
            if not wine.is_file() or not exe.is_file() or not profile.is_dir():
                raise ValueError('Configured launch paths are unavailable')
            import os
            env = os.environ.copy()
            env.update(entry.get('env', {}))
            process = subprocess.Popen([str(wine), '--bottle', entry['bottle'],
                                       '--wait', '--workdir', str(profile), str(exe)],
                                      env=env, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      start_new_session=True)
            # This is a macOS PID, NOT a Wine PID. OAS must bind the new window.
            body = json.dumps({'started': True}).encode()
            self.send_response(202)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (KeyError, ValueError, OSError) as exc:
            self.send_error(503, str(exc)[:200])

    def log_message(self, *args):
        pass  # Do not log tokens, account names or screenshots.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--port', type=int, default=22271)
    parser.add_argument('--launch-config', type=Path, help='Optional trusted local title-to-launch map')
    args = parser.parse_args()
    token = args.token_file.read_text().strip()
    if len(token) < 32:
        parser.error('Token must contain at least 32 characters')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.launch_config = args.launch_config.resolve() if args.launch_config else None
    server.token = token
    server.helper = args.helper.resolve()
    server.serve_forever()


if __name__ == '__main__':
    main()
