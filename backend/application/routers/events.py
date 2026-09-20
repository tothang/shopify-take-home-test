import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from application.services.event_broker import event_broker

router = APIRouter(prefix="/api/events", tags=["events"])

HEARTBEAT_INTERVAL_SECONDS = 15.0


@router.get("/products")
async def stream_product_events(request: Request) -> StreamingResponse:
    """Server-sent event stream of variant updates.

    This endpoint is provided and works. It emits one "ready" event when the
    browser connects, then one "variant-updated" event for every update
    published to the broker, plus a comment line as a heartbeat so idle
    connections are not closed by proxies.
    """

    async def generate_events() -> AsyncIterator[str]:
        async with event_broker.subscribe() as queue:
            yield "event: ready\ndata: {}\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                yield f"event: variant-updated\ndata: {event.model_dump_json()}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
