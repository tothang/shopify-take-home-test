import { useCallback } from "react";

import { ProductTable } from "./components/ProductTable";
import { useCatalog } from "./hooks/useCatalog";
import { type StreamStatus, useProductStream } from "./hooks/useProductStream";
import type { InventoryPolicy, ProductVariant } from "./types";

const STREAM_STATUS_TEXT: Record<StreamStatus, string> = {
  open: "Live updates: on",
  connecting: "Live updates: connecting",
  closed: "Live updates: off, retrying. Changes made elsewhere will not appear until this reconnects.",
};

export function App() {
  const catalog = useCatalog();
  const streamStatus = useProductStream(catalog.applyServerVariant, catalog.reload);

  const { saveChange } = catalog;

  const handlePriceCommit = useCallback(
    (variant: ProductVariant, price: string) => {
      void saveChange(variant, { price });
    },
    [saveChange],
  );

  const handleInventoryPolicyChange = useCallback(
    (variant: ProductVariant, policy: InventoryPolicy) => {
      void saveChange(variant, { inventory_policy: policy });
    },
    [saveChange],
  );

  return (
    <main className="page">
      <header className="page-header">
        <h1>Pricing console</h1>
        <p className="stream-status" data-status={streamStatus} role="status">
          {STREAM_STATUS_TEXT[streamStatus]}
        </p>
      </header>

      {catalog.notices.length > 0 ? (
        <div className="notice-list">
          {catalog.notices.map((notice) => (
            <div key={notice.id} className="error-banner notice" role="alert">
              <span>{notice.message}</span>
              <button type="button" className="notice-dismiss" onClick={() => catalog.dismissNotice(notice.id)}>
                Dismiss
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {catalog.loadError ? <p className="error-banner">{catalog.loadError}</p> : null}
      {catalog.isLoading ? <p className="loading-state">Loading the catalog</p> : null}

      {!catalog.isLoading && !catalog.loadError ? (
        <ProductTable
          products={catalog.products}
          savingVariantIds={catalog.savingVariantIds}
          onPriceCommit={handlePriceCommit}
          onInventoryPolicyChange={handleInventoryPolicyChange}
        />
      ) : null}
    </main>
  );
}
