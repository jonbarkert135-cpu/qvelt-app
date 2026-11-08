"""Bound message JSON bodies before FastAPI decodes untrusted input."""
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class PrivateResponses:
    """Pure ASGI header policy; no task group around streaming responses."""
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def no_store(message: Message) -> None:
            if (message["type"] == "http.response.start"
                    and scope.get("path") != "/healthz"):
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.lower() != b"cache-control"]
                message = {**message, "headers": [*headers, (b"cache-control", b"no-store")]}
            await send(message)
        await self.app(scope, receive, no_store)


class MessageBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (scope["type"] != "http" or scope["method"] != "POST"
                or not scope["path"].startswith("/chats/")
                or not scope["path"].endswith("/messages")):
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            chunk = await receive()
            if chunk["type"] == "http.disconnect":
                return
            data = chunk.get("body", b"")
            if len(body) + len(data) > 1_048_576:
                await JSONResponse({"detail": "Message body is too large"}, status_code=413)(
                    scope, receive, send,
                )
                return
            body.extend(data)
            if not chunk.get("more_body", False):
                break
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
