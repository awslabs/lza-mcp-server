#!/usr/bin/env python3
"""
Simple test script to verify the MCP server is working correctly.
"""

import json
import subprocess
import sys
import time


def test_mcp_server():
    """Test the MCP server with basic initialization."""

    # Initialize message
    init_message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }

    # Initialized notification
    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }

    # List tools message
    list_tools_message = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }

    try:
        # Start the server process
        process = subprocess.Popen(
            ["poetry", "run", "python", "-u", "server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/Users/vmayberr/xdev/mte/lza-mcp-server/src/lza-mcp-server",
        )

        # Send initialization message
        init_input = json.dumps(init_message) + "\n"
        process.stdin.write(init_input)
        process.stdin.flush()

        # Read initialization response
        init_response = process.stdout.readline()
        if init_response:
            init_result = json.loads(init_response)
            print("✓ Initialization successful")
            print(f"  Server: {init_result['result']['serverInfo']['name']}")
            print(f"  Version: {init_result['result']['serverInfo']['version']}")
        else:
            print("✗ No initialization response")
            return False

        # Send initialized notification
        initialized_input = json.dumps(initialized_notification) + "\n"
        process.stdin.write(initialized_input)
        process.stdin.flush()

        # Small delay to let the server process the notification
        time.sleep(0.1)

        # Send list tools message
        tools_input = json.dumps(list_tools_message) + "\n"
        process.stdin.write(tools_input)
        process.stdin.flush()

        # Read tools response
        tools_response = process.stdout.readline()
        if tools_response:
            tools_result = json.loads(tools_response)
            if "result" in tools_result:
                tools = tools_result["result"]["tools"]
                print(f"✓ Tools list retrieved: {len(tools)} tools available")
                for tool in tools[:5]:  # Show first 5 tools
                    print(f"  - {tool['name']}: {tool['description'][:50]}...")
                if len(tools) > 5:
                    print(f"  ... and {len(tools) - 5} more tools")
            else:
                print(
                    "✗ Tools list failed:", tools_result.get("error", "Unknown error")
                )
                return False
        else:
            print("✗ No tools response")
            return False

        # Clean up
        process.terminate()
        process.wait(timeout=5)

        print("✓ MCP server test completed successfully")
        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        if "process" in locals():
            process.terminate()
        return False


if __name__ == "__main__":
    success = test_mcp_server()
    sys.exit(0 if success else 1)
