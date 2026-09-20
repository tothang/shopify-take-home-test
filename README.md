# Shopify Pricing Console: Take-Home Exercise

## The problem

Our merchants run flash sales. During a sale an operator needs to change variant
prices quickly, and decide per variant whether the storefront keeps selling once
available stock reaches zero. Prices also change somewhere else at the same
time: in the Shopify admin, in a bulk editor, or through another application.
When that happens the operator must see the new value without reloading the
page, otherwise two people overwrite each other's work during the busiest hour
of the week.

You are given a running skeleton of that console. Your job is to finish it: make
a merchant able to install the application into their store, read and write
their catalog through the Shopify Admin API, and keep the screen correct while
other people are changing the same data.

## Time box

Plan for seven to eight hours of focused work, and deliver within seven calendar
days. If you run out of time, stop and write down what is missing and how you
would finish it. A smaller submission with clear reasoning scores higher than a
rushed complete one. Tasks are listed in the order we suggest you do them, and
they are worth roughly the effort implied by that order.

## What you need

- Docker and Docker Compose, and Make
- A Shopify Partner account with a development store. It is free and takes about
  ten minutes. See "Connecting a real Shopify store" below.

You do not need Python or Node.js on your machine. Everything runs in
containers.

## Getting started

Do not fork this repository and do not push to it. Press **Use this template**
on its GitHub page, choose **Private**, and work in the copy that creates. A fork
of a public repository is public, so everyone else taking the exercise could
read your work. Then clone your copy:

```
make setup
make up
```

The frontend is on http://localhost:5173, the backend on http://localhost:8000,
and the interactive API documentation on http://localhost:8000/docs.

Out of the box the backend serves an in-memory catalog, so the stack starts
without any Shopify credentials. Tasks 1, 2, 3, 6 and everything the provided
tests check for task 4 run entirely in that mode. Only installing the
application for real, and task 5, need a development store.

```
make test              Run the backend and the frontend test suites
make backend-test      Run the backend test suite
make frontend-test     Run the frontend test suite
make lint              Check backend code style and frontend types
make webhook           Send a signed products/update webhook to the backend
make down              Stop everything
make help              List every command
```

The first time you run `make test` you will see nine backend tests pass and
thirty four fail. That is the starting point, not a broken checkout. The failing
tests are the specification: one group per task, and every failure names the
task it belongs to. Your submission is expected to make all of them pass, with
none of them changed.

## What is already provided

- A FastAPI service with configuration, dependency wiring, the product and
  variant models, error types and the interactive API documentation.
- `InMemoryProductGateway`: a fake catalog with three products, so you can build
  the frontend before touching Shopify.
- `ShopifyGraphQLClient`: the transport to the Shopify Admin GraphQL API,
  including error handling. The queries themselves are yours to write.
- `ShopTokenStore`: somewhere to keep the access token of a shop that installed
  the application. In memory on purpose.
- `EventBroker` and the server-sent event stream at `/api/events/products`,
  which pushes variant updates to every connected browser.
- A React and TypeScript frontend that loads the catalog and renders an editable
  table. The inputs are wired to local state only.
- `backend/scripts/send_product_update_webhook.py`, which sends a correctly
  signed `products/update` webhook, so you can build the webhook path without
  exposing your machine to the internet. Run it with `make webhook`.
- A test suite. Nine tests pass today. The rest describe work you have not done
  yet and fail until you do it. They are the contract, so do not change them.

Every place you need to touch is marked in the source with its task number:

```
grep -rn "Task [0-9]" backend/application frontend/source
```

## The API contract

Application endpoints live under `/api`. Field names are snake case, and money
is carried as a string, the same way Shopify represents it. Identifiers in this
API are numeric strings; Shopify global identifiers such as
`gid://shopify/ProductVariant/45100000000001` do not leave the gateway. Helpers
are in `application/shopify/identifiers.py`.

### `GET /api/products`

```json
[
  {
    "id": "8100000000001",
    "title": "Everyday Cotton T-Shirt",
    "status": "ACTIVE",
    "variants": [
      {
        "id": "45100000000001",
        "product_id": "8100000000001",
        "title": "Small / Black",
        "sku": "COTTON-TEE-S-BLACK",
        "price": "24.00",
        "currency_code": "USD",
        "inventory_quantity": 12,
        "inventory_policy": "DENY",
        "updated_at": "2026-01-15T09:00:00Z"
      }
    ]
  }
]
```

### `PATCH /api/products/{product_id}/variants/{variant_id}`

Body, with at least one of the two fields:

```json
{ "price": "18.50", "inventory_policy": "CONTINUE" }
```

| Situation | Status |
| --- | --- |
| The change was applied | 200, with the stored variant as the body |
| Empty body, price not above zero, more than two decimal places, or an unknown policy | 422 |
| The product or the variant does not exist | 404 |
| Shopify refused the change or is unreachable | 502 |

A field absent from the body is left untouched. Sending only a price must not
reset the inventory policy.

### `GET /api/events/products`

A server-sent event stream. Provided and working. It sends one event named
`ready` on connect, then one named `variant-updated` per change:

```json
{ "source": "webhook", "variant": { "id": "45100000000001", "...": "..." } }
```

### `POST /webhooks/shopify/products-update`

| Situation | Status |
| --- | --- |
| Signature verifies | 200, 202 or 204 |
| Signature missing, malformed or wrong | 401 |

Shopify sends the REST shaped payload to webhooks, even when the rest of your
integration uses GraphQL:

```json
{
  "id": 8100000000001,
  "variants": [
    {
      "id": 45100000000001,
      "product_id": 8100000000001,
      "price": "17.25",
      "inventory_policy": "continue",
      "inventory_quantity": 12
    }
  ]
}
```

## Your tasks

### Task 1: serve the catalog

`GET /api/products` returns products through the injected gateway. Decide what
the browser sees when the catalog is unreachable. A stack trace in the browser
console is not an answer.

Done when `test_list_products_returns_products_with_variants` passes.

### Task 2: update a variant

`PATCH /api/products/{product_id}/variants/{variant_id}` applies the change and
returns the stored variant, respecting the status codes above. An unknown
variant is a client error, not a server error.

Done when every test in `tests/test_products_api.py` passes.

### Task 3: accept the webhook

Implement `verify_webhook_signature` and the webhook route.

- Shopify signs the raw request body with the application secret and sends the
  result base64 encoded in the `X-Shopify-Hmac-Sha256` header.
- Verify against the raw bytes. A parsed and re-serialized body will not match.
- Compare in constant time.
- Answer quickly. Shopify gives you a short window and retries anything slow.
- Map the REST payload onto the application models, including the lower case
  inventory policy values.
- Publish one event per variant in the payload through `event_broker.publish`,
  with `source` set to `"webhook"`.

Test it with `make webhook`, while the stack is up. Add
`ARGUMENTS="--price 19.99"` to change the payload, or `ARGUMENTS="--break-signature"` to check that you reject an invalid
request.

Done when `tests/test_webhook_signature.py` and `tests/test_webhook_endpoint.py`
pass.

### Task 4: let a merchant install the application

Nobody should have to paste an access token into a file. Implement the
installation flow in `application/shopify/oauth.py` and
`application/routers/authentication.py`, so that opening
`/auth/install?shop=their-store.myshopify.com` ends with the application holding
a working access token for that shop.

- The shop domain arrives from anyone who can open a link, and everything after
  it builds a URL the application then calls. Decide what a shop domain is
  allowed to look like.
- The callback signature is not the webhook signature. Read the documentation
  rather than reusing your task 3 code.
- Carry a state value across the two requests and check it when the merchant
  returns. Say in your notes where you kept it and why.
- A request that fails verification must not reach the token exchange.
- Save the token in `shop_token_store`, then register the `products/update`
  webhook subscription. Shopify will not accept a callback address it cannot
  reach, so with an application URL of `http://localhost:8000` this call does
  not succeed. Write it anyway, make sure its failure does not break the
  installation, and say in your notes what it would take to make it work.

Done when `tests/test_oauth.py` and `tests/test_authentication_endpoints.py`
pass, and you can install the application into your own development store.

### Task 5: talk to a real Shopify store

Implement `AdminApiProductGateway` and the two documents in
`graphql_documents.py`, then run with `USE_MOCK_SHOPIFY=false` against your own
development store.

- Read products with their variants, including price, inventory policy and
  available stock.
- Update price and inventory policy in one mutation.
- A mutation that returns entries in `userErrors` has failed, whatever the
  transport status code says. Turn it into `VariantUpdateRejectedError`.
- Convert between numeric and global identifiers at this boundary, nowhere else.
- Keep money out of floating point numbers, in both directions.

There are no provided tests here, because they would need your store. Write your
own, with the transport replaced by a test double.

### Task 6: finish the frontend

In `App.tsx` and `hooks/useProductStream.ts`:

- Saving. Committing a price or flipping the toggle calls the backend.
- Optimistic update. The new value appears at once, and rolls back with a
  visible message when the request fails.
- Live updates. The table follows the event stream, so a change made in the
  Shopify admin, or in a second browser tab, appears without a reload.
- Connection state. The operator can tell whether live updates are working.
- Conflicts. An event that arrives while an edit for the same variant is in
  flight must not resurrect the old value. Decide what wins and say why.

We are not assessing visual design. A plain table that behaves correctly beats a
beautiful one that lies about the state of the store.

### Task 7: prove it works

- Add backend tests where the provided suite does not already cover what you
  wrote: the state check on the callback, a token exchange that fails, the
  webhook payload mapping, and the gateway with its transport replaced by a test
  double.
- Add at least one frontend test for the behavior you added.
- `make test` and `make lint` pass.
- In `NOTES.md`, list the cases you verified, as a table of what you did, what
  you expected and what happened. Include the ones you checked by hand, and the
  ones that still fail. At minimum cover: a price change surviving a reload;
  the toggle surviving a reload; changing only the price leaving the policy
  alone; an invalid price; an unknown variant; a valid webhook; a webhook with a
  wrong signature; an event updating an open tab; a failed save rolling back; a
  shop domain that is not Shopify being refused at install.

### Task 8: per market pricing and translations, in writing

Written, not built. Answer in `NOTES.md`, half a page to a page, and do not
build any of it.

The merchant now sells in three Shopify markets: the United States, Germany and
Japan. Each has its own currency, and the merchant wants different prices per
market rather than an automatic conversion. Product titles have to appear in the
language of the market. The operator wants to run a sale in one market only,
from this same screen.

Answer these four, in order, with the same numbering:

1. **Reading.** The operator picks a market at the top of the screen. Where does
   the price on each row now come from? Name the part of the Admin API you would
   call.
2. **Writing.** The operator drops one variant to 15.00 euro in Germany only.
   What do you write, and what happens to the price in the United States and
   Japan?
3. **Translations.** Titles must appear in the market language. What do you
   write, which access scope does it need, and what does the operator need to
   see on screen that they do not need today?
4. **Real time.** Does your task 3 webhook design still keep this screen correct
   once prices are per market? If it does, say why. If it does not, say what
   breaks and what you would do instead.

We read this for named APIs and for an honest answer to question 4. Length is
not the point. "I do not know, and here is how I would find out in an hour" is
better than something invented.

## Out of scope

Do not spend time on these. We would rather discuss them in the live interview.

- Embedding the application in the Shopify admin with App Bridge and Polaris.
- Storing tokens anywhere other than the provided in-memory store.
- Building anything from task 8.
- Bulk editing, pagination beyond the first page, search and filters.
- User accounts, permissions, audit logs, deployment and continuous integration.

## Known limitations of the skeleton

Deliberate. We want to hear what you would do about them, not see them fixed.

- The event broker lives inside one process. A second instance of the backend
  would only reach the browsers connected to itself.
- Access tokens disappear when the process restarts.
- The in-memory catalog has no rate limits and never fails, so it hides the
  failure modes of a real store.
- Nothing records who changed a price, or when, beyond the variant timestamp.

## Connecting a real Shopify store

### 1. Create a Partner account and a development store

1. Sign up at https://partners.shopify.com.
2. Open **Stores** and create a development store, with test data so it comes
   with products.
3. Note the domain. It looks like `your-store.myshopify.com`.

### 2. Create the application

In the Partner dashboard, open **Apps** and create an application. You need:

- the client identifier and the client secret, which go into
  `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET`
- an allowed redirect URL of `http://localhost:8000/auth/callback`
- the access scopes `read_products`, `write_products` and `read_inventory`

The client secret is also what signs webhooks, so `SHOPIFY_WEBHOOK_SECRET` is
that same value once you are talking to a real store. It is not the access
token, and mixing those two up is a common first hour.

### 3. Point the project at the store

In `.env`:

```
USE_MOCK_SHOPIFY=false
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_API_KEY=your-client-identifier
SHOPIFY_API_SECRET=your-client-secret
SHOPIFY_WEBHOOK_SECRET=your-client-secret
SHOPIFY_APPLICATION_URL=http://localhost:8000
```

Then `make restart`, and open
`http://localhost:8000/auth/install?shop=your-store.myshopify.com`.
`http://localhost:8000/api/health` reports which mode the backend is in.

Never commit these values. `.env` is in `.gitignore` and must stay there.

Receiving real webhooks needs a tunnel to port 8000 and an application URL to
match. That is welcome but not required: `make webhook` covers the same path.

### Running without Docker

```
cd backend
python -m venv .venv
source .venv/bin/activate
pip install --requirement requirements.txt --requirement requirements-development.txt
uvicorn application.main:application --reload
pytest

cd frontend
npm install
npm run start
npm run test
```

## What to submit

1. **Your code**, in the private copy you made from the template, on a branch
   named `submission/<your-name>`, with a pull request opened against `main` of
   that same copy. Do not push to `main`. Add the reviewers named in your
   invitation email as collaborators, so they can read and comment on the pull
   request.
2. **`NOTES.md`**, which you create, containing:
   - a link to your recording, at the top
   - what you completed, task by task, and what you did not
   - the three decisions you would defend in a code review, and what you
     rejected
   - what wins when an incoming event meets an in-flight edit, and why
   - your task 7 table of verified cases, including failures
   - your task 8 answer
   - where you used an AI assistant, and one thing it produced that was wrong or
     unsuitable, how you noticed and what you did
3. **A screen recording**, ten minutes or less, as a link we can open without an
   account.

The recording should show, in this order: the project starting from
`make setup && make up`; a price change and the toggle surviving a reload; a
live update arriving, through two browser tabs or `make webhook` or the Shopify
admin; one failure path, such as a broken signature or the backend stopped;
`make test` running. Spend the last three minutes on decisions rather than on
code.

Before you send it: `make test` and `make lint` pass, `git status` is clean, no
`.env` is committed, and a fresh clone of your branch starts with
`make setup && make up`.

## How we assess

| Area | Weight |
| --- | --- |
| Shopify correctness: Admin API usage, webhooks, inventory policy, identifiers | 25 |
| Installation flow: what it has to defend against, and does | 15 |
| Backend quality: contracts, failure handling, structure | 15 |
| Frontend behavior: optimistic updates, live updates, conflicts, error states | 15 |
| The written answer on per market pricing and translations | 10 |
| Testing and the list of verified cases | 12 |
| Notes and recording | 8 |

Things that end an application early: code you cannot explain in the live
interview; a submission that does not start with `make setup && make up`;
secrets or a `.env` committed; provided tests removed, weakened or skipped to
make the suite go green; a claim in your notes that does not match the code.

Things we do not care about: visual design, added databases or queues, and new
dependencies without a reason.

## Using AI assistants

You may use them. We use them every day. Two conditions:

1. Say where you used them, in `NOTES.md`. Being specific counts in your favor.
2. Be able to defend every line you submit. In the live interview we will pick
   parts of your code and ask why they are the way they are. "The assistant
   wrote it" ends that conversation badly.

## Conventions in this repository

- Everything is written in English.
- Names are spelled out. We do not abbreviate our own identifiers. Names that
  come from the Shopify API or from a tool keep their original spelling.
- Our own API uses snake case field names, matching the Python models, so no
  translation layer sits between the backend and the browser. The Shopify Admin
  API uses camel case, and that conversion happens inside the gateway.
- Money is a decimal everywhere and is carried as a string. It never becomes a
  floating point number.

## Questions

Ask. Send them to the address in your invitation email. A good question about an
ambiguous requirement is a positive signal. Assuming quietly and being wrong is
not. If you do not get an answer in time, write the assumption down in your
notes and move on.
