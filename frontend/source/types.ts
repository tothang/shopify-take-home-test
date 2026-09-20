export type InventoryPolicy = "DENY" | "CONTINUE";

/**
 * Field names match the backend response exactly. Prices arrive as strings so
 * that no value passes through a floating point number on the way to the
 * screen.
 */
export interface ProductVariant {
  id: string;
  product_id: string;
  title: string;
  sku: string | null;
  price: string;
  currency_code: string;
  inventory_quantity: number;
  inventory_policy: InventoryPolicy;
  updated_at: string;
}

export interface Product {
  id: string;
  title: string;
  status: string;
  variants: ProductVariant[];
}

export interface VariantChange {
  price?: string;
  inventory_policy?: InventoryPolicy;
}

export interface VariantUpdatedEvent {
  source: string;
  variant: ProductVariant;
}
