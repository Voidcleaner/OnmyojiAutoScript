#!/bin/sh
# Run on the macOS host, not inside CrossOver.
set -eu
cd "$(dirname "$0")/../.."
mkdir -p .macos-runtime
if [ ! -x .macos-runtime/window-helper ] || [ deploy/macos/windows.swift -nt .macos-runtime/window-helper ]; then
    swiftc deploy/macos/windows.swift -o .macos-runtime/window-helper
fi
if [ ! -f .macos-runtime/capture.token ]; then
    python3 -c 'import pathlib,secrets; p=pathlib.Path(".macos-runtime/capture.token"); p.write_text(secrets.token_hex(32)); p.chmod(0o600)'
fi
exec python3 deploy/macos/capture_bridge.py --helper .macos-runtime/window-helper --token-file .macos-runtime/capture.token
