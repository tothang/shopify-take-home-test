import { useState } from "react";

import type { InventoryPolicy, ProductVariant } from "../types";
import { isValidPriceInput, normalizePriceInput } from "../utilities/money";

interface VariantRowProperties {
  variant: ProductVariant;
  isSaving: boolean;
  onPriceCommit: (variant: ProductVariant, price: string) => void;
  onInventoryPolicyChange: (variant: ProductVariant, policy: InventoryPolicy) => void;
}

export function VariantRow({
  variant,
  isSaving,
  onPriceCommit,
  onInventoryPolicyChange,
}: VariantRowProperties) {
  const [priceDraft, setPriceDraft] = useState(variant.price);
  // The price when the operator started typing, or null when they are not.
  const [priceWhenEditingStarted, setPriceWhenEditingStarted] = useState<string | null>(null);
  const isEditing = priceWhenEditingStarted !== null;

  // Follow the stored price, but not over what the operator is typing: an
  // event arriving mid-edit would otherwise wipe their input without a word.
  // Done during render rather than in an effect, so the input changes in the
  // same paint as everything else. An effect runs after the paint, and would
  // show a rollback message beside a value that has not rolled back yet.
  const [followedPrice, setFollowedPrice] = useState(variant.price);
  if (variant.price !== followedPrice && !isEditing) {
    setFollowedPrice(variant.price);
    setPriceDraft(variant.price);
  }

  const changedWhileEditing = isEditing && variant.price !== priceWhenEditingStarted;

  const hasValidPrice = isValidPriceInput(priceDraft);
  const hasPendingChange = normalizePriceInput(priceDraft) !== variant.price;

  const commitPrice = () => {
    if (!hasValidPrice || !hasPendingChange) {
      setPriceDraft(variant.price);
      return;
    }
    onPriceCommit(variant, normalizePriceInput(priceDraft));
  };

  return (
    <tr className={isSaving ? "variant-row is-saving" : "variant-row"}>
      <td>
        <span className="variant-title">{variant.title}</span>
        <span className="variant-sku">{variant.sku ?? "no stock keeping unit"}</span>
      </td>
      <td className="numeric">{variant.inventory_quantity}</td>
      <td>
        <div className="price-field">
          <input
            aria-label={`Price for ${variant.title}`}
            className={hasValidPrice ? "price-input" : "price-input is-invalid"}
            value={priceDraft}
            disabled={isSaving}
            onChange={(event) => setPriceDraft(event.target.value)}
            onFocus={() => setPriceWhenEditingStarted(variant.price)}
            onBlur={() => {
              setPriceWhenEditingStarted(null);
              commitPrice();
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.currentTarget.blur();
              }
              if (event.key === "Escape") {
                setPriceDraft(variant.price);
                setPriceWhenEditingStarted(variant.price);
              }
            }}
          />
          <span className="currency-code">{variant.currency_code}</span>
        </div>
        {!hasValidPrice ? <span className="field-error">Enter an amount above zero</span> : null}
        {changedWhileEditing ? (
          <span className="field-note">
            Changed elsewhere to {variant.price}. Saving will replace it; Escape takes theirs.
          </span>
        ) : null}
      </td>
      <td>
        <label className="policy-toggle">
          <input
            type="checkbox"
            aria-label={`Continue selling ${variant.title} when out of stock`}
            checked={variant.inventory_policy === "CONTINUE"}
            disabled={isSaving}
            onChange={(event) =>
              onInventoryPolicyChange(variant, event.target.checked ? "CONTINUE" : "DENY")
            }
          />
          <span>{variant.inventory_policy === "CONTINUE" ? "Continue selling" : "Stop at zero"}</span>
        </label>
      </td>
      <td className="timestamp">{new Date(variant.updated_at).toLocaleTimeString()}</td>
    </tr>
  );
}
