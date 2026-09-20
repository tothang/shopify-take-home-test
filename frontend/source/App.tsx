import { useCallback, useEffect, useState } from "react";

import { fetchProducts } from "./api/backendClient";
import { ProductTable } from "./components/ProductTable";
import { useProductStream } from "./hooks/useProductStream";
import type { InventoryPolicy, Product, ProductVariant } from "./types";

export function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [savingVariantIds] = useState<ReadonlySet<string>>(new Set());

  useEffect(() => {
    const controller = new AbortController();
    fetchProducts(controller.signal)
      .then((loaded) => {
        setProducts(loaded);
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setLoadError(error instanceof Error ? error.message : "The catalog could not be loaded.");
      })
      .finally(() => setIsLoading(false));
    return () => controller.abort();
  }, []);

  const applyVariant = useCallback((updated: ProductVariant) => {
    setProducts((current) =>
      current.map((product) =>
        product.id !== updated.product_id
          ? product
          : {
              ...product,
              variants: product.variants.map((variant) =>
                variant.id === updated.id ? updated : variant,
              ),
            },
      ),
    );
  }, []);

  const streamStatus = useProductStream(applyVariant);

  /**
   * Task 6: send the change to the backend and keep the table honest.
   *
   * Show the new value straight away, roll it back when the request fails,
   * tell the operator what went wrong, and make sure a later event from the
   * stream does not resurrect a value the operator has already replaced.
   */
  const handlePriceCommit = useCallback((variant: ProductVariant, price: string) => {
    void variant;
    void price;
  }, []);

  const handleInventoryPolicyChange = useCallback(
    (variant: ProductVariant, policy: InventoryPolicy) => {
      void variant;
      void policy;
    },
    [],
  );

  return (
    <main className="page">
      <header className="page-header">
        <h1>Pricing console</h1>
        <p className="stream-status" data-status={streamStatus}>
          Live updates: {streamStatus}
        </p>
      </header>

      {loadError ? <p className="error-banner">{loadError}</p> : null}
      {isLoading ? <p className="loading-state">Loading the catalog</p> : null}

      {!isLoading && !loadError ? (
        <ProductTable
          products={products}
          savingVariantIds={savingVariantIds}
          onPriceCommit={handlePriceCommit}
          onInventoryPolicyChange={handleInventoryPolicyChange}
        />
      ) : null}
    </main>
  );
}
