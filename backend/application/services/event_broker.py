import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from application.schemas import VariantUpdatedEvent

logger = logging.getLogger(__name__)


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
        """Send the event to every subscriber.

        - Never raises for a slow subscriber.
        - A subscriber with a full queue is dropped, not just skipped.
        - Its stream ends, the browser reconnects and reloads the catalog,
          so it never keeps showing a stale value.
        """
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self._subscribers.discard(queue)
                logger.warning(
                    "Dropped an event stream subscriber that fell behind.",
                    extra={"queue_size": self._queue_size, "variant_id": event.variant.id},
                )

    def is_subscribed(self, queue: asyncio.Queue[VariantUpdatedEvent]) -> bool:
        """False once publish has dropped this queue for falling behind."""
        return queue in self._subscribers

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


event_broker = EventBroker()
