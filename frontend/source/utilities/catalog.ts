import type { Product, ProductVariant, VariantChange } from "../types";

/**
 * The rules that decide what the table shows. Kept free of React so they can
 * be tested on their own.
 *
 * What wins: the newest state the server has stored, by updated_at. Every
 * copy of a variant that reaches the browser passes through isAtLeastAsNew:
 * the response to a save, the echo of that save on the event stream, a
 * webhook for somebody else's edit, a full reload after a reconnect. The
 * server is the only clock anybody shares, so ordering by its timestamps is
 * the one rule that gives every open tab the same answer, whatever order the
 * messages happened to arrive in.
 */
export function isAtLeastAsNew(incoming: ProductVariant, current: ProductVariant): boolean {
  const incomingTime = Date.parse(incoming.updated_at);
  const currentTime = Date.parse(current.updated_at);
  if (Number.isNaN(incomingTime) || Number.isNaN(currentTime)) {
    return true;
  }
  // A tie is accepted: it is the same stored state arriving twice, typically
  // the save response and its own echo on the stream.
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

/**
 * Take a freshly loaded catalog, keeping any variant the table already holds
 * a newer copy of. A reload can be slower than an event that overtook it.
 */
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
 * Lay edits that are still being saved over what the server has confirmed.
 *
 * Only the fields being changed are laid over. A change somebody else makes
 * to the other field of the same variant still shows while the save runs.
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
