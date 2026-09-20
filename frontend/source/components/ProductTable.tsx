import type { InventoryPolicy, Product, ProductVariant } from "../types";
import { VariantRow } from "./VariantRow";

interface ProductTableProperties {
  products: Product[];
  savingVariantIds: ReadonlySet<string>;
  onPriceCommit: (variant: ProductVariant, price: string) => void;
  onInventoryPolicyChange: (variant: ProductVariant, policy: InventoryPolicy) => void;
}

export function ProductTable({
  products,
  savingVariantIds,
  onPriceCommit,
  onInventoryPolicyChange,
}: ProductTableProperties) {
  if (products.length === 0) {
    return <p className="empty-state">No products were returned by the catalog.</p>;
  }

  return (
    <div className="product-list">
      {products.map((product) => (
        <section key={product.id} className="product-card">
          <header className="product-header">
            <h2>{product.title}</h2>
            <span className="product-status">{product.status}</span>
          </header>
          <table className="variant-table">
            <thead>
              <tr>
                <th scope="col">Variant</th>
                <th scope="col" className="numeric">
                  Available
                </th>
                <th scope="col">Price</th>
                <th scope="col">When out of stock</th>
                <th scope="col">Updated</th>
              </tr>
            </thead>
            <tbody>
              {product.variants.map((variant) => (
                <VariantRow
                  key={variant.id}
                  variant={variant}
                  isSaving={savingVariantIds.has(variant.id)}
                  onPriceCommit={onPriceCommit}
                  onInventoryPolicyChange={onInventoryPolicyChange}
                />
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}
