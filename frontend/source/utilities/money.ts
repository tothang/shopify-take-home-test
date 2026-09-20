const PRICE_PATTERN = /^\d+(\.\d{1,2})?$/;

export function isValidPriceInput(value: string): boolean {
  const trimmed = value.trim();
  if (!PRICE_PATTERN.test(trimmed)) {
    return false;
  }
  return Number(trimmed) > 0;
}

export function normalizePriceInput(value: string): string {
  const trimmed = value.trim();
  const [whole, fraction = ""] = trimmed.split(".");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}

export function formatMoney(amount: string, currencyCode: string): string {
  return `${amount} ${currencyCode}`;
}
