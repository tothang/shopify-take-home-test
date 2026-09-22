import { useEffect, useRef, useState } from "react";

import { PRODUCT_EVENT_STREAM_PATH } from "../api/backendClient";
import type { ProductVariant, VariantUpdatedEvent } from "../types";

/**
 * open: events are arriving. connecting: not yet, or the browser is retrying
 * a dropped connection by itself. closed: the browser gave up, and this hook
 * is waiting to try again. Only open means the table is following the store.
 */
export type StreamStatus = "connecting" | "open" | "closed";

// Used after the browser gives up on its own, which it does when the server
// answers with an error rather than dropping the connection.
const RETRY_DELAYS_MILLISECONDS = [1_000, 2_000, 5_000, 10_000, 30_000];

/**
 * Keep the table in step with changes made outside this browser tab.
 *
 * onConnected runs on every "ready", the first included. Events sent while
 * the connection was down are gone, and the stream cannot replay them, so the
 * only way to be sure the table is current after a gap is to load it again.
 * That costs one extra request on page load, which is cheaper than showing a
 * price that is no longer the price.
 */
export function useProductStream(
  onVariantUpdated: (variant: ProductVariant) => void,
  onConnected?: () => void,
): StreamStatus {
  const [status, setStatus] = useState<StreamStatus>("connecting");

  // The connection is opened once, and reads the latest callbacks through a
  // ref, so a new callback does not tear it down and open another.
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

    // Closing matters: StrictMode mounts twice in development, and without
    // this every event would arrive twice over two open connections.
    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      source?.close();
    };
  }, []);

  return status;
}
