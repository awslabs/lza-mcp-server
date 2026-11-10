#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Smoke test for a built LZA MCP Server image.

Starts the image with no network, sends an MCP initialize and tools/list over
stdio, and fails unless the server answers both.

Usage: smoke_test_image.py <container-runtime> <image>
"""

import json
import subprocess
import sys
import threading

TIMEOUT_SECONDS = 60


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    runtime, image = sys.argv[1], sys.argv[2]
    proc = subprocess.Popen(  # nosec B603
        [runtime, "run", "-i", "--rm", "--network", "none", image],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None and proc.stdout is not None
    responses: dict = {}
    done = threading.Event()

    def read() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict) and msg.get("id") in (1, 2):
                responses[msg["id"]] = msg
            if 2 in responses:
                break
        done.set()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    def send(msg: dict) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "smoke-test", "version": "0"},
            },
        }
    )
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    done.wait(TIMEOUT_SECONDS)
    proc.stdin.close()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    init = responses.get(1, {}).get("result", {})
    tools = responses.get(2, {}).get("result", {}).get("tools", [])
    server = init.get("serverInfo", {})
    print(f"serverInfo: {json.dumps(server)}")
    print(f"protocolVersion: {init.get('protocolVersion')}")
    print(f"tools: {len(tools)}")
    if not server or not tools:
        print("SMOKE TEST FAILED: no initialize result or no tools", file=sys.stderr)
        return 1
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
