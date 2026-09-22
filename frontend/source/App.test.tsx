import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { Product, ProductVariant } from "./types";

/** Stands in for the browser's EventSource, which jsdom does not provide. */
class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static instances: FakeEventSource[] = [];

  readyState = FakeEventSource.CONNECTING;
  onerror: (() => void) | null = null;
  isClosed = false;
  private readonly listeners = new Map<string, ((event: MessageEvent) => void)[]>();

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {
    this.isClosed = true;
    this.readyState = FakeEventSource.CLOSED;
  }

  emit(type: string, data: unknown) {
    this.readyState = FakeEventSource.OPEN;
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: JSON.stringify(data) }));
    }
  }

  fail(readyState: number) {
    this.readyState = readyState;
    this.onerror?.();
  }
}

const BASE: ProductVariant = {
  id: "45100000000001",
  product_id: "8100000000001",
  title: "Small / Black",
  sku: "COTTON-TEE-S-BLACK",
  price: "24.00",
  currency_code: "USD",
  inventory_quantity: 12,
  inventory_policy: "DENY",
  updated_at: "2026-01-15T09:00:00Z",
};

function at(time: string, overrides: Partial<ProductVariant>): ProductVariant {
  return { ...BASE, ...overrides, updated_at: `2026-01-15T${time}:00Z` };
}

const PRODUCTS: Product[] = [
  { id: "8100000000001", title: "Everyday Cotton T-Shirt", status: "ACTIVE", variants: [BASE] },
];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

let respondToPatch: () => Promise<Response> | Response;
let getCount: number;

beforeEach(() => {
  FakeEventSource.instances = [];
  getCount = 0;
  respondToPatch = () => json(at("10:00", { price: "18.50" }));
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PATCH") {
        return respondToPatch();
      }
      getCount += 1;
      return json(PRODUCTS);
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stream(): FakeEventSource {
  return FakeEventSource.instances[FakeEventSource.instances.length - 1];
}

function send(variant: ProductVariant) {
  act(() => stream().emit("variant-updated", { source: "webhook", variant }));
}

/** Render the console and wait for the catalog to load. */
async function priceInput(): Promise<HTMLInputElement> {
  render(<App />);
  return (await screen.findByLabelText("Price for Small / Black")) as HTMLInputElement;
}

function commitPrice(input: HTMLInputElement, value: string) {
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value } });
  fireEvent.blur(input);
}

describe("saving", () => {
  it("shows the new price at once, before the server answers", async () => {
    const answer = deferred<Response>();
    respondToPatch = () => answer.promise;
    const input = await priceInput();

    commitPrice(input, "18.5");

    expect(input.value).toBe("18.50");
    expect(input.disabled).toBe(true);

    await act(async () => answer.resolve(json(at("10:00", { price: "18.50" }))));
    await waitFor(() => expect(input.disabled).toBe(false));
    expect(input.value).toBe("18.50");
  });

  it("sends only the field that changed", async () => {
    const input = await priceInput();

    commitPrice(input, "18.50");

    await waitFor(() => expect(input.disabled).toBe(false));
    const patch = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ price: "18.50" });
  });

  it("saves the toggle", async () => {
    respondToPatch = () => json(at("10:00", { inventory_policy: "CONTINUE" }));
    render(<App />);
    const toggle = (await screen.findByLabelText(
      "Continue selling Small / Black when out of stock",
    )) as HTMLInputElement;

    fireEvent.click(toggle);

    expect(toggle.checked).toBe(true);
    await waitFor(() => expect(toggle.disabled).toBe(false));
    expect(toggle.checked).toBe(true);
  });
});

describe("a failed save", () => {
  it("rolls back and says why", async () => {
    respondToPatch = () => json({ detail: "The change could not be saved. Try again in a moment." }, 502);
    const input = await priceInput();

    commitPrice(input, "18.50");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not save the price of Small / Black (18.50)");
    expect(alert.textContent).toContain("The change could not be saved");
    expect(input.value).toBe("24.00");
  });

  it("rolls back to the latest stored value, not to the one before the edit", async () => {
    const answer = deferred<Response>();
    respondToPatch = () => answer.promise;
    const input = await priceInput();

    commitPrice(input, "18.50");
    send(at("09:30", { price: "22.00" }));
    await act(async () => answer.resolve(json({ detail: "Refused." }, 502)));

    await screen.findByRole("alert");
    expect(input.value).toBe("22.00");
  });

  it("says the server could not be reached when it could not", async () => {
    respondToPatch = () => Promise.reject(new TypeError("Failed to fetch"));
    const input = await priceInput();

    commitPrice(input, "18.50");

    expect((await screen.findByRole("alert")).textContent).toContain("could not be reached");
  });

  it("can be dismissed", async () => {
    respondToPatch = () => json({ detail: "Refused." }, 502);
    commitPrice(await priceInput(), "18.50");

    fireEvent.click(await screen.findByRole("button", { name: "Dismiss" }));

    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("conflicts", () => {
  it("an event carrying an older value while a save is in flight does not bring it back", async () => {
    const answer = deferred<Response>();
    respondToPatch = () => answer.promise;
    const input = await priceInput();

    commitPrice(input, "18.50");
    send(at("09:30", { price: "22.00" }));

    expect(input.value).toBe("18.50");

    await act(async () => answer.resolve(json(at("10:00", { price: "18.50" }))));
    await waitFor(() => expect(input.disabled).toBe(false));
    expect(input.value).toBe("18.50");
  });

  it("a change stored after ours wins once our save settles", async () => {
    const answer = deferred<Response>();
    respondToPatch = () => answer.promise;
    const input = await priceInput();

    commitPrice(input, "18.50");
    send(at("11:00", { price: "30.00" }));
    await act(async () => answer.resolve(json(at("10:00", { price: "18.50" }))));

    await waitFor(() => expect(input.disabled).toBe(false));
    expect(input.value).toBe("30.00");
  });

  it("does not overwrite a price the operator is typing, and says it changed", async () => {
    const input = await priceInput();
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "19" } });

    send(at("10:00", { price: "21.00" }));

    expect(input.value).toBe("19");
    expect(screen.getByText(/Changed elsewhere to 21.00/)).toBeDefined();
  });
});

describe("live updates", () => {
  it("a change made elsewhere appears without a reload", async () => {
    const input = await priceInput();

    send(at("10:00", { price: "21.00" }));

    expect(input.value).toBe("21.00");
  });

  it("tells the operator whether live updates are working", async () => {
    await priceInput();
    const status = screen.getByRole("status");
    expect(status.textContent).toBe("Live updates: connecting");

    act(() => stream().emit("ready", {}));
    expect(status.textContent).toBe("Live updates: on");

    act(() => stream().fail(FakeEventSource.CONNECTING));
    expect(status.textContent).toBe("Live updates: connecting");

    act(() => stream().fail(FakeEventSource.CLOSED));
    expect(status.textContent).toContain("Live updates: off");
  });

  it("reconnects after the browser gives up", async () => {
    vi.useFakeTimers();
    try {
      render(<App />);
      const first = stream();

      act(() => first.fail(FakeEventSource.CLOSED));
      act(() => vi.advanceTimersByTime(1_000));

      expect(first.isClosed).toBe(true);
      expect(stream()).not.toBe(first);
    } finally {
      vi.useRealTimers();
    }
  });

  it("reloads the catalog on every connect, to cover what it missed", async () => {
    await priceInput();
    const before = getCount;

    act(() => stream().emit("ready", {}));

    await waitFor(() => expect(getCount).toBe(before + 1));
  });

  it("closes the connection when the page goes away", async () => {
    const { unmount } = render(<App />);
    const source = stream();

    unmount();

    expect(source.isClosed).toBe(true);
  });
});
