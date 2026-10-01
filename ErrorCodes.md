# API v3 errors

The old numeric v1/v2 error notes do not apply to this client. API v3 reports
HTTP failures with JSON fields `code` and `message`. See the
[official error-code table](https://docs.btcmarkets.net/doc/).

`BTCMarketsError` exposes `status_code`, `code`, and rate-limit `headers`.
Transport/JSON/shape failures use the same exception with no HTTP status.
Server bodies and request credentials are not included in exception messages.

| Status / code | Action |
| --- | --- |
| 401 / `InvalidAPIKey`, `InvalidAuthSignature`, `InvalidAuthTimestamp` | Check keys and computer clock; do not print secrets. |
| 403 / `InsufficientAPIPermission` | Check read access for account/trading APIs. |
| 404 / `MarketNotFound` | Check `btcmarkets markets`; old pairs may be unavailable. |
| 429 / `TooManyRequests` | Wait until `x-ratelimit-reset` (Unix seconds); no automatic retries. |
| 5xx | Exchange/server failure; decide when to retry. |

Invalid local settings raise `ValueError` before a request is sent. CLI failures
exit with status 1 and Ctrl+C exits with status 130.
