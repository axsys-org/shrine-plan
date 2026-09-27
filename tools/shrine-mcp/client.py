"""Small authenticated MCP client shared by hooks and integration checks."""
from contextlib import asynccontextmanager
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class Client:
    """Synchronous SDK for the same nine operations exposed through MCP."""
    def __init__(self, connection_file):
        self.connection = json.loads(Path(connection_file).read_text())
        if self.connection.get("protocol_version") != 5:
            raise RuntimeError("Connection is not Shrine protocol 5; use the archived compatible client")

    def call(self, method, **arguments):
        url = self.connection["url"].removesuffix("/mcp") + "/rpc"
        request = Request(url, data=json.dumps({"method": method, "arguments": arguments}).encode(),
            headers={"Authorization": "Bearer " + self.connection["token"], "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=300) as response:
                result = json.load(response)
        except HTTPError as error:
            try:
                detail = json.load(error)
            except ValueError:
                detail = {"rpc_error": str(error)}
            raise RuntimeError(detail.get("rpc_error", str(detail))) from error
        if "rpc_error" in result:
            raise RuntimeError(result["rpc_error"])
        return result

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@asynccontextmanager
async def connect(connection_file):
    connection = json.loads(Path(connection_file).read_text())
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + connection["token"]},
                                 timeout=20) as http:
        async with streamable_http_client(connection["url"], http_client=http) as streams:
            async with ClientSession(streams[0], streams[1]) as client:
                await client.initialize()
                yield client


async def call(client, name, arguments):
    result = await client.call_tool(name, arguments)
    if result.is_error:
        raise RuntimeError(str(result.content))
    return result.structured_content or json.loads(result.content[0].text)
