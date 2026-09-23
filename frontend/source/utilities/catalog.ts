import type { Product, ProductVariant, VariantChange } from "../types";

/**
 * Rules for what the table shows, kept free of React for testing.
 *
 * - The newest server state wins, by updated_at.
 * - Every variant update (save response, stream event, reload) goes through
 *   this check.
 * - So all tabs agree, whatever order updates arrive in.
 */
export function isAtLeastAsNew(incoming: ProductVariant, current: ProductVariant): boolean {
  const incomingTime = Date.parse(incoming.updated_at);
  const currentTime = Date.parse(current.updated_at);
  if (Number.isNaN(incomingTime) || Number.isNaN(currentTime)) {
    return true;
  }
  // Accept ties: usually the save response and its echo on the stream.
  return incomingTime >= currentTime;
}

/** Apply one variant from the server, unless what the table holds is newer. */
export function mergeVariant(products: Product[], incoming: ProductVariant): Product[] {
  let anyChanged = false;
  const next = products.map((product) => {
    if (product.id !== incoming.product_id) {
      return product;
    }
    let productChanged = false;
    const variants = product.variants.map((variant) => {
      if (variant.id !== incoming.id || !isAtLeastAsNew(incoming, variant)) {
        return variant;
      }
      productChanged = true;
      return incoming;
    });
    anyChanged ||= productChanged;
    return productChanged ? { ...product, variants } : product;
  });
  return anyChanged ? next : products;
}

/** Use a freshly loaded catalog, but keep variants we already have newer copies of. */
export function mergeCatalog(current: Product[], loaded: Product[]): Product[] {
  const held = new Map<string, ProductVariant>();
  for (const product of current) {
    for (const variant of product.variants) {
      held.set(variant.id, variant);
    }
  }
  return loaded.map((product) => ({
    ...product,
    variants: product.variants.map((variant) => {
      const existing = held.get(variant.id);
      return existing && !isAtLeastAsNew(variant, existing) ? existing : variant;
    }),
  }));
}

/**
 * Apply in-flight edits on top of the confirmed catalog.
 *
 * - Only the edited fields are overridden.
 * - Other fields can still update during a save.
 */
export function withPendingChanges(
  products: Product[],
  pending: ReadonlyMap<string, VariantChange>,
): Product[] {
  if (pending.size === 0) {
    return products;
  }
  return products.map((product) => {
    if (!product.variants.some((variant) => pending.has(variant.id))) {
      return product;
    }
    return {
      ...product,
      variants: product.variants.map((variant) => {
        const change = pending.get(variant.id);
        return change ? { ...variant, ...change } : variant;
      }),
    };
  });
}
