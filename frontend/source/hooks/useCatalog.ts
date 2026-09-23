import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchProducts, RequestFailedError, updateVariant } from "../api/backendClient";
import type { Product, ProductVariant, VariantChange } from "../types";
import { mergeCatalog, mergeVariant, withPendingChanges } from "../utilities/catalog";

export interface Notice {
  id: number;
  variantId: string | null;
  message: string;
}

export interface Catalog {
  /** Confirmed state with in-flight edits applied on top. */
  products: Product[];
  savingVariantIds: ReadonlySet<string>;
  isLoading: boolean;
  loadError: string | null;
  notices: Notice[];
  dismissNotice: (id: number) => void;
  saveChange: (variant: ProductVariant, change: VariantChange) => Promise<void>;
  /** Apply a variant pushed by the event stream. */
  applyServerVariant: (variant: ProductVariant) => void;
  /** Reload the catalog, keeping any variant newer than the reload. */
  reload: () => Promise<void>;
}

function describe(error: unknown): string {
  if (error instanceof RequestFailedError) {
    return error.message;
  }
  return "The server could not be reached.";
}

function describeChange(variant: ProductVariant, change: VariantChange): string {
  if (change.price !== undefined && change.inventory_policy !== undefined) {
    return `the price and stock setting of ${variant.title}`;
  }
  if (change.price !== undefined) {
    return `the price of ${variant.title} (${change.price})`;
  }
  return `the stock setting of ${variant.title}`;
}

/**
 * The catalog as the operator sees it, in two layers:
 * - confirmed: what the server has stored (only moves forward in time)
 * - pending: edits still being saved, shown on top
 *
 * - Events keep updating the confirmed layer during a save.
 * - When the save ends, the pending edit is removed and the newest confirmed
 *   value shows. This makes rollback simple.
 */
export function useCatalog(): Catalog {
  const [confirmed, setConfirmed] = useState<Product[]>([]);
  const [pending, setPending] = useState<ReadonlyMap<string, VariantChange>>(new Map());
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notices, setNotices] = useState<Notice[]>([]);
  const nextNoticeId = useRef(1);

  const addNotice = useCallback((variantId: string | null, message: string) => {
    const id = nextNoticeId.current++;
    setNotices((current) => [
      ...current.filter((notice) => variantId === null || notice.variantId !== variantId),
      { id, variantId, message },
    ]);
  }, []);

  const dismissNotice = useCallback((id: number) => {
    setNotices((current) => current.filter((notice) => notice.id !== id));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchProducts(controller.signal)
      .then((loaded) => {
        setConfirmed((current) => mergeCatalog(current, loaded));
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoadError(error instanceof RequestFailedError ? error.message : "The catalog could not be loaded.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  const applyServerVariant = useCallback((variant: ProductVariant) => {
    setConfirmed((current) => mergeVariant(current, variant));
  }, []);

  const reload = useCallback(async () => {
    try {
      const loaded = await fetchProducts();
      setConfirmed((current) => mergeCatalog(current, loaded));
      setLoadError(null);
      setIsLoading(false);
    } catch (error: unknown) {
      // Keep the current (possibly stale) table and warn the operator.
      addNotice(null, `The catalog could not be refreshed: ${describe(error)} Values may be out of date.`);
    }
  }, [addNotice]);

  const saveChange = useCallback(
    async (variant: ProductVariant, change: VariantChange) => {
      setNotices((current) => current.filter((notice) => notice.variantId !== variant.id));
      setPending((current) => new Map(current).set(variant.id, { ...current.get(variant.id), ...change }));
      try {
        const stored = await updateVariant(variant.product_id, variant.id, change);
        applyServerVariant(stored);
      } catch (error: unknown) {
        addNotice(
          variant.id,
          `Could not save ${describeChange(variant, change)}: ${describe(error)} The row shows the last saved value.`,
        );
      } finally {
        // Either way, drop the pending edit to reveal the latest confirmed value.
        setPending((current) => {
          const next = new Map(current);
          next.delete(variant.id);
          return next;
        });
      }
    },
    [addNotice, applyServerVariant],
  );

  const products = useMemo(() => withPendingChanges(confirmed, pending), [confirmed, pending]);
  const savingVariantIds = useMemo(() => new Set(pending.keys()), [pending]);

  return {
    products,
    savingVariantIds,
    isLoading,
    loadError,
    notices,
    dismissNotice,
    saveChange,
    applyServerVariant,
    reload,
  };
}
