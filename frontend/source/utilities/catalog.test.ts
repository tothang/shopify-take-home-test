import { describe, expect, it } from "vitest";

import type { Product, ProductVariant } from "../types";
import { isAtLeastAsNew, mergeCatalog, mergeVariant, withPendingChanges } from "./catalog";

function variant(overrides: Partial<ProductVariant> = {}): ProductVariant {
  return {
    id: "45100000000001",
    product_id: "8100000000001",
    title: "Small / Black",
    sku: "COTTON-TEE-S-BLACK",
    price: "24.00",
    currency_code: "USD",
    inventory_quantity: 12,
    inventory_policy: "DENY",
    updated_at: "2026-01-15T09:00:00Z",
    ...overrides,
  };
}

function catalog(...variants: ProductVariant[]): Product[] {
  return [{ id: "8100000000001", title: "Everyday Cotton T-Shirt", status: "ACTIVE", variants }];
}

describe("isAtLeastAsNew", () => {
  it("orders by the server's timestamp, across time zones", () => {
    const earlier = variant({ updated_at: "2026-01-15T09:00:00Z" });
    const later = variant({ updated_at: "2026-01-15T05:30:00-05:00" });

    expect(isAtLeastAsNew(later, earlier)).toBe(true);
    expect(isAtLeastAsNew(earlier, later)).toBe(false);
  });

  it("accepts a tie, which is the same stored state arriving twice", () => {
    expect(isAtLeastAsNew(variant(), variant())).toBe(true);
  });
});

describe("mergeVariant", () => {
  it("applies a newer copy", () => {
    const merged = mergeVariant(catalog(variant()), variant({ price: "18.50", updated_at: "2026-01-15T10:00:00Z" }));

    expect(merged[0].variants[0].price).toBe("18.50");
  });

  it("ignores an older copy that arrives late", () => {
    const current = catalog(variant({ price: "18.50", updated_at: "2026-01-15T10:00:00Z" }));

    const merged = mergeVariant(current, variant({ price: "24.00", updated_at: "2026-01-15T09:00:00Z" }));

    expect(merged[0].variants[0].price).toBe("18.50");
    expect(merged).toBe(current);
  });

  it("leaves other products untouched, so they do not re-render", () => {
    const other: Product = { id: "8100000000002", title: "Bottle", status: "ACTIVE", variants: [] };
    const current = [...catalog(variant()), other];

    const merged = mergeVariant(current, variant({ price: "18.50", updated_at: "2026-01-15T10:00:00Z" }));

    expect(merged[1]).toBe(other);
  });
});

describe("mergeCatalog", () => {
  it("keeps a variant the table holds a newer copy of than the reload", () => {
    const current = catalog(variant({ price: "18.50", updated_at: "2026-01-15T10:00:00Z" }));

    const merged = mergeCatalog(current, catalog(variant()));

    expect(merged[0].variants[0].price).toBe("18.50");
  });

  it("follows the reload for anything added or removed", () => {
    const removed = variant({ id: "45100000000009" });
    const added = variant({ id: "45100000000002" });

    const merged = mergeCatalog(catalog(variant(), removed), catalog(variant(), added));

    expect(merged[0].variants.map((entry) => entry.id)).toEqual(["45100000000001", "45100000000002"]);
  });
});

describe("withPendingChanges", () => {
  it("lays only the fields being saved over the confirmed state", () => {
    const confirmed = catalog(variant({ inventory_policy: "CONTINUE" }));

    const shown = withPendingChanges(confirmed, new Map([["45100000000001", { price: "18.50" }]]));

    expect(shown[0].variants[0].price).toBe("18.50");
    expect(shown[0].variants[0].inventory_policy).toBe("CONTINUE");
  });

  it("returns the same catalog when nothing is being saved", () => {
    const confirmed = catalog(variant());

    expect(withPendingChanges(confirmed, new Map())).toBe(confirmed);
  });
});
