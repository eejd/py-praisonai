"""Exercise real MCP 2 stdio and streamable HTTP transports."""
import os
import socket
import subprocess
import sys
import time

import pytest

SERVER = '''\nimport sys\nfrom praisonaiagents.mcp.mcp_server import ToolsMCPServer\nserver = ToolsMCPServer("regression")\ndef add(a: int, b: int) -> int:\n    return a + b\nserver.register_tool(add)\nif sys.argv[1] == "stdio":\n    server.run("stdio")\nelse:\n    server.get_fastmcp().run(transport="streamable-http", host="127.0.0.1", port=int(sys.argv[2]))\n'''

@pytest.fixture
def server_script(tmp_path):
    path = tmp_path / 'server.py'
    path.write_text(SERVER)
    return path


def test_stdio_mcp2(server_script):
    from praisonaiagents.mcp.mcp import MCP
    client = MCP(sys.executable, args=[str(server_script), 'stdio', '0'], timeout=15)
    try:
        tool = next(t for t in client.get_tools() if t.__name__ == 'add')
        assert '42' in str(tool(a=19, b=23))
        assert '3' in str(tool(a=1, b=2))
    finally:
        client.shutdown()


def test_streamable_http_mcp2(server_script):
    from praisonaiagents.mcp.mcp_http_stream import HTTPStreamMCPClient
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen([sys.executable, str(server_script), 'streamable-http', str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                    break
            except OSError:
                if proc.poll() is not None:
                    pytest.fail('MCP server exited before readiness')
                time.sleep(.05)
        else:
            pytest.fail('MCP server did not become ready')
        client = HTTPStreamMCPClient(f'http://127.0.0.1:{port}/mcp', timeout=15)
        try:
            tool = next(t for t in client.tools if t.name == 'add')
            assert '42' in str(tool(a=19, b=23))
            assert '3' in str(tool(a=1, b=2))
        finally:
            client.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
