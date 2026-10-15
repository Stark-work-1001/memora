"""Optional MCP Streamable HTTP gateway. Loopback; place behind an authenticated TLS tunnel for remote clients."""
import os
import secrets

from .errors import InvalidInput


class BearerGate:
    def __init__(self, app, token):
        if not isinstance(token,str) or len(token)<32:raise InvalidInput('MM_BRIDGE_TOKEN must contain at least 32 characters')
        self.app,self.token=app,token

    async def __call__(self, scope, receive, send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[])); supplied=headers.get(b'authorization',b'').decode('latin1')
        # A web page is not an MCP client. Prevent browser-origin credential forwarding.
        if b'origin' in headers or not secrets.compare_digest(supplied,'Bearer '+self.token):
            await send({'type':'http.response.start','status':401,'headers':[(b'content-type',b'application/json'),(b'cache-control',b'no-store')]})
            await send({'type':'http.response.body','body':b'{"error":"authorized MCP client required"}'})
            return
        return await self.app(scope,receive,send)


def run(store, service, port):
    import uvicorn
    from .server import create_server
    token=os.environ.get('MM_BRIDGE_TOKEN','')
    if len(token)<32:raise InvalidInput('set MM_BRIDGE_TOKEN (32+ characters); never put it in source or URLs')
    server=create_server(store,service)
    server.settings.stateless_http=True
    uvicorn.run(BearerGate(server.streamable_http_app(),token),host='127.0.0.1',port=port,access_log=False)
