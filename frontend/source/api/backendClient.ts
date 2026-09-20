import type { Product, ProductVariant, VariantChange } from "../types";

const BASE_PATH = "/api";

export class RequestFailedError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "RequestFailedError";
    this.status = status;
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      return body.detail;
    }
    return JSON.stringify(body);
  } catch {
    return response.statusText;
  }
}

export async function fetchProducts(signal?: AbortSignal): Promise<Product[]> {
  const response = await fetch(`${BASE_PATH}/products`, { signal });
  if (!response.ok) {
    throw new RequestFailedError(response.status, await readError(response));
  }
  return (await response.json()) as Product[];
}

export async function updateVariant(
  productId: string,
  variantId: string,
  change: VariantChange,
): Promise<ProductVariant> {
  const response = await fetch(`${BASE_PATH}/products/${productId}/variants/${variantId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(change),
  });
  if (!response.ok) {
    throw new RequestFailedError(response.status, await readError(response));
  }
  return (await response.json()) as ProductVariant;
}

export const PRODUCT_EVENT_STREAM_PATH = `${BASE_PATH}/events/products`;
