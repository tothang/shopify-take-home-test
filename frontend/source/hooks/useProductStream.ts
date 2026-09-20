import type { ProductVariant } from "../types";

export type StreamStatus = "connecting" | "open" | "closed";

/**
 * Task 6: keep the table in step with changes made outside this browser tab.
 *
 * The backend serves a server-sent event stream at the path exported as
 * PRODUCT_EVENT_STREAM_PATH. It sends an event named "ready" once on connect
 * and an event named "variant-updated" for every change, whose data is a JSON
 * object of the shape VariantUpdatedEvent.
 *
 * Things worth handling: closing the connection when the component unmounts,
 * what the operator sees while the connection is down, and what happens to an
 * edit that is still in flight when an event for the same variant arrives.
 */
export function useProductStream(onVariantUpdated: (variant: ProductVariant) => void): StreamStatus {
  void onVariantUpdated;
  return "closed";
}
