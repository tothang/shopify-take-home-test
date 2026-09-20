import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from application.schemas import VariantUpdatedEvent


class EventBroker:
    """In-process fan-out of variant updates to every connected browser.

    One queue per subscriber. A subscriber that stops reading is dropped once
    its queue is full, so a slow browser cannot block the webhook handler.
    """

    def __init__(self, queue_size: int = 100) -> None:
        self._queue_size = queue_size
        self._subscribers: set[asyncio.Queue[VariantUpdatedEvent]] = set()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[VariantUpdatedEvent]]:
        queue: asyncio.Queue[VariantUpdatedEvent] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    async def publish(self, event: VariantUpdatedEvent) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


event_broker = EventBroker()
