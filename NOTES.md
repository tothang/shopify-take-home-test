# Notes

**Video walkthrough:** https://www.loom.com/share/4f2b308d49784db3b82530a1393a8940

Tasks 1 to 7 are done. `make test` passes (138 backend, 37 frontend) and so
does `make lint`. No dependencies were added. Task 8 is at the end.

The application was installed into a real development store
(`test-thang.myshopify.com`) and every case below was checked against it on
2026-09-22 unless it says otherwise. One case fails, and it is described in
[What still fails](#what-still-fails).

## Verified cases

Checked by hand against the real store, through the Vite proxy the browser
uses. The test variant was the ADIDAS Classic Backpack, OS / black, which
started at 80.00 USD / DENY and was put back to that afterwards.

"UI" means the console in Chrome. Two of the UI checks were driven from a
script in the page, because the tab was in the background and a hidden tab
does not give focus to an input. The script focused the field and dispatched
the same input and Enter events a keyboard would, so the application's own
handlers did all the work.

| # | Case | What I did | Expected | What happened |
|---|---|---|---|---|
| 1 | A price change survives a reload | UI: typed `84`, pressed Enter, reloaded the page. API: `PATCH {"price":"81.50"}`, then a fresh `GET`. | New price stays | UI showed `84.00` at once with the row locked, saved without an error, and still showed `84.00` after the reload. API: `200`, then `81.50` on the fresh read. **Pass** |
| 2 | The toggle survives a reload | UI: clicked the toggle to "Stop at zero", reloaded. API: `PATCH {"inventory_policy":"CONTINUE"}`, then a fresh `GET`. | New policy stays | UI kept "Stop at zero" after the reload. API: `200`, then `CONTINUE`. **Pass** |
| 3 | Changing only the price leaves the policy alone | API: `PATCH {"price":"81.50"}` while the policy was `DENY`. Also the reverse, policy only. | The other field is unchanged | Policy stayed `DENY`. The reverse left the price at `81.50`, and in the UI the toggle change left `84.00` alone. **Pass** |
| 4 | An invalid price | API: `0`, `-1.00`, `12.345`, `abc`, `{}` and policy `SOMETIMES`. UI: typed `0`, `12.345` and `abc`, pressed Enter. | Refused, store unchanged | API: `422` for all six, and the fresh read was unchanged. UI: the field was marked invalid with an error, Enter restored `84.00`, and no request was sent (counted from the browser's resource timings). **Pass.** The message for `12.345` says "Enter an amount above zero", which misleads when the problem is the third decimal place. |
| 5 | An unknown variant | API: a real product with variant `1`; product `1` with a real variant; variant `abc`. | `404` | `404` for all three. The first two came from Shopify's `PRODUCT_VARIANT_DOES_NOT_EXIST` and `PRODUCT_DOES_NOT_EXIST` codes. `abc` is refused without calling Shopify. **Pass** |
| 6 | A valid webhook | `make webhook` with the real product and variant, `--inventory-policy continue`. Then real edits, with Shopify sending webhooks through an ngrok tunnel. | `204`, one event per variant, `"continue"` mapped to `CONTINUE` | `204`, and the stream carried `source: "webhook"` with `inventory_policy: "CONTINUE"`. ngrok recorded 14 deliveries from `Shopify-Captain-Hook`, all answered `204`, so Shopify's real signatures verify. **Pass** |
| 7 | A webhook with a wrong signature | `make webhook ARGUMENTS="--break-signature"` | `401` | `401 {"detail":"The webhook signature did not verify."}`, and the log says `Rejected a webhook whose signature did not verify.` **Pass** |
| 8 | An event updating an open tab | The console was open in Chrome. I saved `84.25` from another client with `curl`, not from the tab. | The tab shows it without a reload | The tab showed `84.25`, the Updated column changed, and the header stayed "Live updates: on". Shopify also sent a real webhook for the change. **Pass** |
| 9 | A failed save rolling back | UI: made the page's next `PATCH` fail as a network error, then entered `90`. | New value at once, then back with a message | `90.00` with the row locked while saving. After the failure it went back to `84.00`, with "Could not save the price of OS / black (90.00): The server could not be reached. The row shows the last saved value." **Pass** |
| 10 | A shop domain that is not Shopify is refused at install | `/auth/install?shop=` with `example.com`, `evil.com/test-thang.myshopify.com` and `test-thang.myshopify.com.evil.com` | `400`; a real domain goes to Shopify | `400` for all three. `test-thang.myshopify.com` gave `302` to `https://test-thang.myshopify.com/admin/oauth/authorize`. **Pass** |
| 11 | Installing into a development store | Opened the install link and approved the scopes. | Token stored, merchant returned to the console | The callback answered `303` to the console, and `/api/health` listed the shop. The read query returned 25 products. **Pass** (2026-09-21) |
| 12 | Webhook registration on `localhost` | Installed with `SHOPIFY_APPLICATION_URL=http://localhost:8000`. | Registration fails and the install still completes | Shopify refused it with "Address protocol http:// is not supported; Address cannot be a Shopify or an internal domain". The failure was logged and the install completed. **Pass** (an expected failure) |
| 13 | Webhook registration through a tunnel | Set the application URL to an ngrok address and reinstalled. | Registration succeeds and real edits arrive | No warning in the log, and deliveries arrived (see 6). **Pass** |
| 14 | The catalog is unreachable | Real mode, pointed at a shop that does not exist. | `502` with a short message, and the cause in the log | `GET` and `PATCH` both `502`. The log shows `ShopifyError: Shopify returned status 404`. Before task 5 the same probe returned `500`. **Pass** (2026-09-21) |

Covered by automated tests but not checked by hand:
- **The "off, retrying" connection state.** Stopping the backend clears the in-memory token, so the store has to be reinstalled afterwards.
- **A signed webhook that is not readable.** It is answered `204` and nothing is published.
- **An empty webhook secret.** It refuses everything.
- **One slow browser.** It cannot make publishing fail.

A note on `make webhook` in real mode: the script sends a fixed timestamp in
January 2026. That is older than any real variant, so an open tab correctly
ignores the event (see [what wins](#task-6-what-wins-and-why)). In mock mode
the seed catalog is older than the script, so the tab updates.

## What still fails

**Shopify's update response carries the previous write's `updatedAt`, and
that can briefly bring back an old value.** Found while checking case 2 and
reproduced four times out of four:

| Change | Save response `updated_at` | Fresh read straight after |
|---|---|---|
| price 82.00 | `04:50:42Z` (the previous write) | `04:51:50Z` |
| price 82.50 | `04:51:50Z` (the previous write) | `04:51:54Z` |

`productVariantsBulkUpdate` returns the new values with the old timestamp. An
immediate re-read returns the right one.

Because the console orders changes by `updated_at`, this lets a webhook bring
back a value that was already replaced:
1. I saved the policy as `CONTINUE`.
2. The save response arrived with the timestamp of the earlier price change.
3. The webhook for that earlier price change then arrived, carrying policy
   `DENY` and the same timestamp. Equal timestamps are accepted, so it was
   applied.
4. About a second later, the webhook for the policy change put `CONTINUE` back.

This was observed on the event stream; an open tab applies whatever the
stream sends it under the same rule. It corrects itself when the next webhook
arrives, so it needs webhooks to be working. On `localhost`, with no webhooks,
it does not occur, because the only events are the save's own echoes.

The fix is to re-read the variant after the mutation and return that: one
extra query per save, and a test with the transport double. I have not made
that change.

## Decisions

### Task 1: an unreachable catalog

The browser gets `502` with "The catalog is unavailable right now. Try again
in a moment." The failure is upstream, and `502` is the status the README
already uses for Shopify being unreachable on the update endpoint. The details
and traceback go to the server log. Only `ShopifyError` is caught, so a bug in
our own code stays a `500` instead of passing as an outage.

### Task 2: updating a variant

The status codes follow the README. `VariantNotFoundError` is caught before
`ShopifyError`, its parent class; in the other order, every unknown variant
would become a `502`.

A successful update is also published on the event stream with
`source: "api"`. In mock mode nothing else would ever tell a second tab about
the change. That rule lives in `services/variant_updates.py`, so the update
endpoint and the webhook both follow it.

### Task 3: the webhook

- **Signature.** Verified against the raw bytes with `hmac.compare_digest`.
  A missing or malformed header is `401`. An empty configured secret refuses
  everything, because anyone can compute an HMAC with an empty key.
- **Signed but unreadable payloads** (not JSON, or the wrong shape) are
  answered `204` and logged. The signature proves Shopify sent those exact
  bytes, so a retry would fail the same way, and repeated retries are worse
  than one entry in the log.
- **One variant that cannot be read is skipped**, and the rest are published.
  An unknown policy value is not guessed as `DENY`, because showing "stop at
  zero" for a variant that keeps selling is worse than showing nothing.
- **The REST payload has no currency.** A shop has one currency and Shopify
  assumes the receiver knows it, so the mapping falls back to USD. With
  several shops, it would come from the shop record.
- `json.loads(parse_float=Decimal)`, so a price that arrives as a JSON number
  never becomes a float.
- **Answering quickly.** The route verifies, maps and publishes, and each
  publish is a non-blocking `put_nowait`. Anything slower would belong behind
  a queue.

### Task 4: where the state is kept, and why

The state is a random value, `secrets.token_urlsafe(32)`. It is kept in an
**httpOnly cookie on the merchant's browser**, scoped to `/auth` and valid for
10 minutes, and it is cleared after one use. The callback only goes ahead
when the returned state matches the cookie.

- **Why a cookie and not a table on the server.** A server table proves the
  application issued the state, but not that the browser returning with it is
  the one it was issued to. Checking that is the point: it stops someone from
  starting an install themselves and tricking a merchant into finishing it.
  The cookie also survives a restart and works across several backend
  processes.
- **`SameSite=Lax`, not `Strict`.** The merchant returns through a redirect
  from Shopify, which is a navigation from another site, and a `Strict` cookie
  would not be sent on it.
- **The shop domain** must fully match
  `[a-z0-9][a-z0-9-]{0,62}\.myshopify\.com`. `fullmatch` is used because a `$`
  anchor also matches before a trailing newline. The token exchange checks the
  domain again before sending the client secret to that host.
- **Order of checks in the callback:** duplicate parameters, then the
  signature, then the shop and the code, then the state. A request that fails
  any of them never reaches the token exchange.

**What registering the webhook needs.** Shopify refuses anything that is not
a public HTTPS address (case 12). To make it work:
1. Put the app behind a public HTTPS address: a tunnel locally (ngrok was used
   here, case 13), or the deployed domain in production.
2. Set that address as `SHOPIFY_APPLICATION_URL`, and add
   `<address>/auth/callback` to the app's allowed redirection URLs.
3. Reinstall, starting from that address. The state cookie belongs to the host
   the install starts on.

In production I would declare the subscription in the app configuration
rather than create it through the API at install. I have not checked how the
Dev Dashboard handles that.

**How the Shopify app has to be set up** for this flow:
- Not embedded.
- "Use legacy install flow" turned on. Otherwise Shopify runs the install
  itself and never sends the merchant to `/auth/callback`.
- App URL set to `/auth/install`, so opening the app from the admin reinstalls
  it.
- Distributed as a custom app, not a public one. Shopify's docs say new public
  apps cannot use non-expiring tokens for the GraphQL Admin API, and existing
  public apps lose them on 2027-01-01. Expiring tokens would need
  `expiring=1`, a refresh token and a refresh job.

### Task 5: the real store

- **Updates** use `productVariantsBulkUpdate`, the current mutation. Only the
  fields that changed are sent. Three `userErrors` codes mean "not found" and
  become `404`: `PRODUCT_DOES_NOT_EXIST`, `PRODUCT_VARIANT_DOES_NOT_EXIST` and
  `MUST_BE_FOR_THIS_PRODUCT`. Any other code becomes
  `VariantUpdateRejectedError`, a `502`.
- **Currency.** A variant's price is in the shop currency, so the currency is
  read from `shop { currencyCode }`. A mutation cannot ask for it, so the
  gateway keeps it, and there is one gateway per shop and token rather than
  one per request.
- **30 variants per product.** Shopify refuses a query that costs more than
  1000 points. 25 products with 100 variants each would cost about 2,500; with
  30 it is about 830. When a product has more, the log says so instead of
  dropping them silently.
- **Identifiers.** They are converted in the gateway and nowhere else. An
  identifier that is not numeric is a `404` without a call to Shopify.
- **Money** is sent as `str(Decimal)`, and the client now parses JSON numbers
  as `Decimal`.

### Task 6: what wins, and why

**The newest state the server has stored wins, by `updated_at`.** Every copy
of a variant goes through the same rule:
- the response to a save,
- the stream's echo of that save,
- a webhook,
- the full reload after a reconnect.

A copy older than the one the table holds is ignored. The server's clock is
the only one every tab shares, so every tab reaches the same answer whatever
order the messages arrive in. The flaw in how Shopify fills in `updated_at`
is described under [What still fails](#what-still-fails).

Edits being saved sit in a separate layer on top of the confirmed state:
- **An event cannot change the value on screen while a save is in flight.** It
  still updates the confirmed state underneath.
- **When the save finishes, the layer is removed.** The row shows the newest
  confirmed state. If someone else stored a later change, theirs wins, because
  overriding it would hide it.
- **A failed save goes back to the latest stored value**, not to the value
  from before the edit.
- **Only the field being saved is held.** A change to the other field shows
  straight away.

Two more rules:
- **A price the operator is typing is not overwritten.** The row says
  "Changed elsewhere to X". Saving replaces their value; Escape takes it.
- **The catalog is reloaded every time the stream connects.** The stream
  cannot replay what was sent while a tab was disconnected. It costs one extra
  `GET` on page load.

The connection state is shown as "on", "connecting" or "off, retrying". The
broker used to drop a browser that fell behind while its stream kept sending
heartbeats, so the header said "on" while nothing arrived. The stream now ends
in that case, and the browser reconnects and reloads.

## Changes to provided code

| File | Change | Why |
|---|---|---|
| `shopify/graphql_client.py` | A `200` whose body is not JSON raises `ShopifyError`; numbers are parsed as `Decimal` | Before, a maintenance page returned by the edge became a `500`, and money could pass through a float |
| `dependencies.py` | One `AdminApiProductGateway` per shop and token | To keep the shop currency between requests |
| `services/event_broker.py`, `routers/events.py` | `is_subscribed`, a warning log, and ending the stream of a dropped subscriber | So the connection state tells the truth (task 6) |
| `components/VariantRow.tsx` | The price draft follows the stored price during render, and typing is protected | The effect ran after paint, so for one frame a rollback message sat next to a value that had not rolled back |
| `settings.py`, `.env.example` | `FRONTEND_URL`, `products_update_webhook_url` | Where the merchant lands after install; the webhook address |

New modules:
- `services/variant_updates.py`
- `shopify/webhook_payload.py`
- `shopify/webhook_subscription.py`
- `hooks/useCatalog.ts`
- `utilities/catalog.ts`

## Tests added

| Task 7 asks for | Where |
|---|---|
| The state check on the callback | `tests/test_installation_flow.py`: a wrong state, the state cookie missing (a different browser), a replayed callback |
| A token exchange that fails | `tests/test_installation_flow.py`: a refusal, a server error, a body that is not JSON, no token, the wrong shape, an unreachable shop, a host that is not Shopify. Nothing is stored in any of them. |
| The webhook payload mapping | `tests/test_webhook_payload.py`, and `tests/test_webhook_hardening.py` for the shapes that used to return `500` |
| The gateway with its transport replaced | `tests/test_admin_api_gateway.py`: a `FakeTransport` for the gateway, and `httpx.MockTransport` for the client |
| At least one frontend test | `App.test.tsx`: optimistic save, rollback, the conflict cases, live updates, connection state, reconnecting, closing on unmount. `utilities/catalog.test.ts` covers the merge rules. |

`tests/test_variant_updates.py` covers the task 1 and 2 cases that the
provided suite leaves out: partial updates in both directions, three decimal
places, a price of exactly zero, `502` mapping, and the `api` event.

## Known limitations

These are the skeleton's own limitations, plus the ones I found:

- **One shop per process.** `ShopTokenStore` can hold several shops, but
  `get_product_gateway` always serves `SHOPIFY_STORE_DOMAIN`. A second
  merchant who installs would see the first merchant's catalog. The request
  has to carry the shop: a signed session cookie set at the callback, or App
  Bridge session tokens once the app is embedded.
- **Tokens are kept in memory.** They disappear on restart, and in development
  on every automatic reload after a saved backend file. They belong encrypted
  in a database.
- **The event broker is inside one process.** More than one instance would
  need a shared bus such as Redis pub/sub, and ideally replay for reconnecting
  tabs.
- **Logging.**
  - INFO logs from the application never appear, because uvicorn leaves the
    root logger at WARNING.
  - The structured `extra` fields only become useful with a JSON formatter.
  - There is no request ID linking a browser error to its log entry.

  I would add a logging configuration and request-ID middleware first.
- **No handling of Shopify's rate limits.** A `THROTTLED` answer becomes a
  `502`. Retrying with backoff, driven by the cost in `extensions`, would be
  next.
- **Pagination.** The first 25 products, and 30 variants each.
- **Untracked stock shows 0**, because the model requires a number.
- **Nothing records who changed a price.**
- **The ngrok address changes** whenever the tunnel restarts on the free plan.
  The steps in [task 4](#task-4-where-the-state-is-kept-and-why) then have to
  be repeated.

## Task 8: per market pricing and translations

Not built. API names checked against the latest Admin API reference on 2026-09-22.

### 1. Reading

Per market prices are not on the variant. `ProductVariant.price` is the shop's base
price. The market price lives in a price list on that market's catalog.

Read what the buyer sees:

    ProductVariant.contextualPricing(context: { country: DE }) {
      price { amount currencyCode }
    }

`ContextualPricingContext` takes `country`, `companyLocationId` or `locationId`. There is
no market ID, so the market selector maps to a country code.

That is not enough on its own. A fixed price and a converted one look the same on screen,
and an operator running a sale needs to know which is which. So also read
`Market.catalogs` → `priceList` → `prices` and use `PriceListPrice.originType`
(`FIXED` or `RELATIVE`) to label the row. `Market.priceList` is deprecated.

New scope: `read_markets`.

### 2. Writing

15.00 EUR in Germany only, into the German catalog's price list:

    priceListFixedPricesAdd(
      priceListId: $germanPriceListId,
      prices: [{ variantId: $variantId, price: { amount: "15.00", currencyCode: EUR } }]
    )

- Replaces any fixed price that variant already has on that list.
- Currency must match the list, or it returns `PRICE_LIST_CURRENCY_MISMATCH`. A new
  gateway method maps that to `VariantUpdateRejectedError`, like the existing one does
  for `userErrors`.
- Scopes: `write_products` and `read_markets`.

The United States and Japan do not move. They resolve from their own price lists, or
from the base price.

Do not use `productVariantsBulkUpdate` here. That is what the gateway calls today, and
it writes the base price, which moves every market that has no fixed price. A German
sale would reprice Japan.

### 3. Translations

Read: `translatableResources(resourceType: PRODUCT)` returns the title and its digest.

Write:

    translationsRegister(resourceId, translations: [{
      key: "title", value, locale: "de", translatableContentDigest
    }])

- Optional `marketId` scopes a translation to one market.
- A market's language comes from its `webPresences`.
- Scopes: `write_translations` and `write_locales`, on top of `read_products`.

The digest pins a translation to the source text. Edit the English title and every
translation of it goes stale. So the row now has to show the locale, whether the title
is a translation or a fallback, and whether it is out of date.

### 4. Real time

Our own writes still work. Everything else breaks.

**What still works.** Tab to tab never went through Shopify. A save publishes through
the broker and the other tabs pick it up. The event just carries the market now:
`(variant, market)`, cache keyed the same way.

**What breaks, part one: ordering.** The `updated_at` guard has nothing left to read.
`PriceListPrice` has no timestamp. Neither does `contextualPricing`. And task 7 found
`productVariantsBulkUpdate` returns the previous write's `updatedAt`, so the variant
timestamp is stale too. The backend has to assign its own version: a counter per
`(variant, market)`, bumped on every write and every re-read. Tabs order by that.

**What breaks, part two: detection.** `products/update` carries the base price and does
not say which market changed. Put that number on a row showing German pricing and it is
true in no market at all.

Most changes fire nothing:

- `WebhookSubscriptionTopic` has no topic for price lists or catalogs.
- `MARKETS_*` topics are about market configuration, not prices.
- `LOCALES_*` topics are about which languages exist, not translated text.

**The mechanism.** Three intakes, one broker, one SSE stream:

| Change | Detected by | Delay |
| --- | --- | --- |
| This console saves | Mutation returned, publish immediately | none |
| Product or variant edited elsewhere | `products/update` arrives → backend re-reads `contextualPricing` for that one product, in the market on screen | < 1s |
| Price list or translation edited elsewhere | Nothing to subscribe to. Backend re-reads the visible rows of the selected market on an interval and on tab focus | one interval |

The backend reads once and publishes. Ten tabs cost what one tab costs, and they all see
the same value at the same time.

**Limits I accept.**

- Outside price list and translation edits are stale for up to one interval. No webhook
  exists, and `PriceList` has no `updatedAt`, so there is no cheap way to ask whether
  anything changed.
- Two outside edits between two reads collapse into one. We see the last value and never
  learn about the first.
- Only visible rows are re-read. A row on another page is unknown until someone opens it.
- Cost scales with rows watched times markets watched, against a rate limit that belongs
  to the shop, not to the viewer. Fine for a few operators per store. Beyond that I would
  stop reading Shopify to serve readers: keep my own read model, fill it from webhooks
  where they exist and `bulkOperationRunQuery` where they do not, and serve the table
  from there. Load then follows edits, not viewers.

**Two things the UI owes the operator.** Show when the data was last re-read, next to the
connection indicator, because a polled number is only eventually correct. And on save,
re-read that one variant first and answer 409 if it moved, because none of the above
prevents an overwrite.

I would drop the polling the day Shopify ships a price list webhook.
