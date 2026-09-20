import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Product } from "../types";
import { ProductTable } from "./ProductTable";

const products: Product[] = [
  {
    id: "8100000000001",
    title: "Everyday Cotton T-Shirt",
    status: "ACTIVE",
    variants: [
      {
        id: "45100000000001",
        product_id: "8100000000001",
        title: "Small / Black",
        sku: "COTTON-TEE-S-BLACK",
        price: "24.00",
        currency_code: "USD",
        inventory_quantity: 12,
        inventory_policy: "DENY",
        updated_at: "2026-01-15T09:00:00Z",
      },
      {
        id: "45100000000002",
        product_id: "8100000000001",
        title: "Medium / Black",
        sku: "COTTON-TEE-M-BLACK",
        price: "24.00",
        currency_code: "USD",
        inventory_quantity: 0,
        inventory_policy: "CONTINUE",
        updated_at: "2026-01-15T09:00:00Z",
      },
    ],
  },
];

afterEach(cleanup);

describe("ProductTable", () => {
  it("shows one row per variant with its price", () => {
    render(
      <ProductTable
        products={products}
        savingVariantIds={new Set()}
        onPriceCommit={vi.fn()}
        onInventoryPolicyChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Everyday Cotton T-Shirt" })).toBeDefined();
    expect(screen.getByLabelText("Price for Small / Black")).toHaveProperty("value", "24.00");
    expect(screen.getByLabelText("Price for Medium / Black")).toHaveProperty("value", "24.00");
  });

  it("reflects the inventory policy of each variant in its toggle", () => {
    render(
      <ProductTable
        products={products}
        savingVariantIds={new Set()}
        onPriceCommit={vi.fn()}
        onInventoryPolicyChange={vi.fn()}
      />,
    );

    const denyToggle = screen.getByLabelText("Continue selling Small / Black when out of stock");
    const continueToggle = screen.getByLabelText("Continue selling Medium / Black when out of stock");

    expect(denyToggle).toHaveProperty("checked", false);
    expect(continueToggle).toHaveProperty("checked", true);
  });

  it("tells the operator when the catalog is empty", () => {
    render(
      <ProductTable
        products={[]}
        savingVariantIds={new Set()}
        onPriceCommit={vi.fn()}
        onInventoryPolicyChange={vi.fn()}
      />,
    );

    expect(screen.getByText(/No products/)).toBeDefined();
  });
});
