# API compatibility and code audit

Reviewed 2 October 2026 against the official API v3 documentation and BTC Markets'
official Python authentication example. Repository baseline: `2342d21`.

## Evidence

- [Current API v3 reference](https://docs.btcmarkets.net/doc/): authentication,
  market data, account balances, orders, trades and rate-limit response headers.
- [Official Python v3 sample](https://github.com/BTCMarkets/api-v3-client-python/blob/master/btcmarkets_client.py):
  method/path/timestamp signing and base64 HMAC-SHA512 headers.
- [Official API repository](https://github.com/BTCMarkets/API): identifies v1/v2 as legacy.
- [Exchange upgrade guidance](https://support.btcmarkets.net/hc/en-us/articles/900006618523-Upgrade-to-API-v3):
  recommends v3 and states there is currently no plan to decommission v1/v2.

This migration does not assume that every legacy endpoint has stopped working.
It replaces them with the exchange's recommended contract.

## Endpoint mapping

| Original operation | Legacy endpoint | Current GET endpoint |
| --- | --- | --- |
| Ticker | `/market/{instrument}/{currency}/tick` | `/v3/markets/{marketId}/ticker` |
| Balances | `/account/balance` | `/v3/accounts/me/balances` |
| Executed trade history | POST `/order/trade/history` | `/v3/trades` |
| Submitted order history (new read helper) | Not implemented | `/v3/orders?status=all` |
| Market discovery (new read helper) | Not implemented | `/v3/markets` |
| Server time (new read helper) | Not implemented | `/v3/time` |

Private GET authentication signs `GET + path + timestamp`, without separators,
request body or query string. The secret is base64-decoded, then used with
HMAC-SHA512; the resulting signature is base64-encoded. Headers are
`BM-AUTH-APIKEY`, `BM-AUTH-TIMESTAMP`, `BM-AUTH-SIGNATURE`.

API v3 amounts/prices are decimal strings and timestamps are ISO 8601. The
client preserves response values. Balances use `assetName`, `balance`,
`available`, `locked`, with `balance = available + locked`.

## Findings and changes

| Severity | Finding | Resolution |
| --- | --- | --- |
| High | Trade history signed compact JSON but Requests independently serialised the body, producing different signed/transmitted bytes. | History now uses the documented v3 GET contract, signed without body/query. Fixed signature vector tests use an independent Node.js HMAC calculation. |
| High | Balance output assigned AUD/BTC/LTC/ETH by array position and divided every amount by 1e8. | Output uses asset identity and preserves v3 decimal strings for all returned assets. |
| Medium | Authentication helpers ignored passed arguments and used globals; duplicated implementations drifted. | One client handles all private authentication and transport. |
| Medium | No timeouts or consistent HTTP/JSON failure handling. | Bounded connect/read waits, typed errors, explicit HTTP/redirect rejection and JSON/shape checks. |
| Medium | Keys were expected in tracked config; history printed the public key and signing payload. | Environment credentials, no credential/request-body debug printing, ignored local secret files. Historical exposure is not established by this audit. |
| Medium | Ticker scripts made requests on import; ETH ticker entered an infinite loop on import. | All script entry points are guarded; polling is explicit and interruptible. |
| Medium | One-line ticker crashed at UTC due to invalid format placeholders; manual offsets mishandled negative/fractional zones. | Timezone-aware datetime formatting, exact Decimal spread, UTC and fractional-offset regression tests. |
| Medium | Vendor samples contained Python 2 syntax, invalid indentation and ignored caller arguments. | Removed obsolete copies and linked current official samples. |
| Low | No supported installation metadata, tests or clear operating instructions. | Python 3.10+ package, Requests dependency range, CLI, offline tests and migration/troubleshooting docs. |

The API documentation's July 2026 rate-limit header additions are exposed on the
client and errors. HTTP 429 handling reports the reset timestamp; no implicit
retry loop is added. May 2026 withdrawal beneficiary changes do not affect this
read-only toolkit. No new order-placement or fund-transfer capability is added.

## Validation and remaining limits

- 21 offline regression tests pass on Python 3.12, covering signatures, routes,
  query filters, asset identity, decimal preservation, timestamps, timeouts,
  rate limits, credentials, session cleanup and import safety.
- The fixed signature vector was cross-checked with Node.js `crypto.createHmac`.
- Installation and console-entry-point checks are run locally. No hosted CI
  workflow is added by this update.
- A public live ticker attempt in the audit environment returned a non-JSON
  response. The environment also returned a site-unavailable HTML page for the
  official documentation. This does **not** establish an exchange outage. API
  compatibility is verified against retrieved official documentation and samples,
  not a successful end-to-end live response.
- No private live calls are tested: account credentials are unavailable.
- No automated dependency vulnerability scan or multi-version Python matrix is
  claimed. The Requests minimum is raised to 2.32.5; latest compatible 2.x releases
  can be installed. This is not a guarantee of future vulnerability-free dependencies.

After merge, check from your own machine:

```sh
btcmarkets time
btcmarkets markets
btcmarkets ticker BTC-AUD --json
# With a read-only API key configured:
btcmarkets balances --json
btcmarkets trades --limit 3
btcmarkets orders --status open
```

Compare balances by asset against the website, verify the clock if authentication
fails, and confirm history is the expected first page. Do not infer that a small
page is a complete account history. Use the returned IDs with the documented
pagination parameters to retrieve further pages.
