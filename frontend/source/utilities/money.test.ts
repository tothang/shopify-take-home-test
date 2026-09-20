import { describe, expect, it } from "vitest";

import { formatMoney, isValidPriceInput, normalizePriceInput } from "./money";

describe("isValidPriceInput", () => {
  it("accepts an amount with two decimal places", () => {
    expect(isValidPriceInput("24.00")).toBe(true);
  });

  it("accepts an amount without decimal places", () => {
    expect(isValidPriceInput("24")).toBe(true);
  });

  it("rejects an empty value", () => {
    expect(isValidPriceInput("")).toBe(false);
  });

  it("rejects zero", () => {
    expect(isValidPriceInput("0")).toBe(false);
  });

  it("rejects a negative amount", () => {
    expect(isValidPriceInput("-3.00")).toBe(false);
  });

  it("rejects more than two decimal places", () => {
    expect(isValidPriceInput("24.005")).toBe(false);
  });

  it("rejects anything that is not a number", () => {
    expect(isValidPriceInput("twenty")).toBe(false);
  });
});

describe("normalizePriceInput", () => {
  it("pads a whole amount to two decimal places", () => {
    expect(normalizePriceInput("24")).toBe("24.00");
  });

  it("pads a single decimal place", () => {
    expect(normalizePriceInput("24.5")).toBe("24.50");
  });
});

describe("formatMoney", () => {
  it("shows the amount next to the currency", () => {
    expect(formatMoney("24.00", "USD")).toBe("24.00 USD");
  });
});
