import { useEffect, useRef, useState } from "react";

import { PRODUCT_EVENT_STREAM_PATH } from "../api/backendClient";
import type { ProductVariant, VariantUpdatedEvent } from "../types";

/**
 * - open: receiving events
 * - connecting: connecting, or the browser is retrying on its own
 * - closed: the browser gave up; this hook will retry later
 */
export type StreamStatus = "connecting" | "open" | "closed";

// Our own retry delays, used once the browser stops retrying (e.g. on an HTTP error).
const RETRY_DELAYS_MILLISECONDS = [1_000, 2_000, 5_000, 10_000, 30_000];

/**
 * Keep the table in sync with changes made outside this tab.
 *
 * - onConnected runs on every "ready", including the first.
 * - The stream cannot replay missed events, so the caller reloads the
 *   catalog on each connect.
 */
export function useProductStream(
  onVariantUpdated: (variant: ProductVariant) => void,
  onConnected?: () => void,
): StreamStatus {
  const [status, setStatus] = useState<StreamStatus>("connecting");

  // Read callbacks through a ref so a new callback does not reopen the connection.
  const handlers = useRef({ onVariantUpdated, onConnected });
  useEffect(() => {
    handlers.current = { onVariantUpdated, onConnected };
  });

  useEffect(() => {
    let source: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let disposed = false;

    const connect = () => {
      setStatus("connecting");
      source = new EventSource(PRODUCT_EVENT_STREAM_PATH);

      source.addEventListener("ready", () => {
        attempt = 0;
        setStatus("open");
        handlers.current.onConnected?.();
      });

      source.addEventListener("variant-updated", (message) => {
        let event: VariantUpdatedEvent;
        try {
          event = JSON.parse((message as MessageEvent<string>).data) as VariantUpdatedEvent;
        } catch {
          return;
        }
        handlers.current.onVariantUpdated(event.variant);
      });

      source.onerror = () => {
        if (disposed || source === null) {
          return;
        }
        if (source.readyState === EventSource.CLOSED) {
          source.close();
          setStatus("closed");
          const delay = RETRY_DELAYS_MILLISECONDS[Math.min(attempt, RETRY_DELAYS_MILLISECONDS.length - 1)];
          attempt += 1;
          retryTimer = setTimeout(connect, delay);
        } else {
          setStatus("connecting");
        }
      };
    };

    connect();

    // Close on unmount, or StrictMode's double mount would open two connections.
    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      source?.close();
    };
  }, []);

  return status;
}
