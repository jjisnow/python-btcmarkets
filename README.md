# Python BTC Markets

Small **read-only** Python client and CLI for [BTC Markets API v3](https://docs.btcmarkets.net/doc/).
Fetch tickers, active markets, server time, account balances, executed trades and
order history. Python 3.10 or newer is required.

## Install

From a checkout:

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead:
# .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
```

For development use `python -m pip install -e .`. Requests is the sole runtime
dependency; the minimum is 2.32.5 and compatible newer 2.x versions are allowed.

## Public commands

No API keys are needed for these commands:

```sh
btcmarkets ticker BTC-AUD
btcmarkets ticker ETH-AUD --interval 5
btcmarkets ticker BTC-AUD --one-line
btcmarkets ticker BTC-AUD --json
btcmarkets markets
btcmarkets time
btcmarkets --timeout 30 ticker BTC-AUD
```

`python -m btcmarkets` is equivalent to `btcmarkets`. Stop polling with Ctrl+C.
Market IDs use `BASE-QUOTE`, such as `BTC-AUD`. Use `markets` to check availability;
legacy pairs such as `LTC-BTC` may no longer be active.

## Private commands

Generate an API key with only the necessary **read** permissions for account and
trading data. The secret is the base64 string supplied by BTC Markets. Username,
email, write access and withdrawal access are not required by this toolkit.

Set environment variables in the shell running the commands. For example, read
keys without putting their values into command history:

Linux/macOS Bash:

```sh
read -r -s -p 'API key: ' BTCMARKETS_API_KEY; echo
read -r -s -p 'API secret: ' BTCMARKETS_API_SECRET; echo
export BTCMARKETS_API_KEY BTCMARKETS_API_SECRET
```

Windows PowerShell 7:

```powershell
$env:BTCMARKETS_API_KEY = Read-Host 'API key' -MaskInput
$env:BTCMARKETS_API_SECRET = Read-Host 'API secret' -MaskInput
```

```sh
btcmarkets balances
btcmarkets balances --json
btcmarkets trades --market ETH-AUD --limit 20
btcmarkets trades --order-id YOUR_ORDER_ID
btcmarkets trades --market ETH-AUD --limit 20 --before 123456
btcmarkets orders --market BTC-AUD --status all --limit 20
btcmarkets orders --status open
```

History commands return **one page**, not a complete account export. Use `before`
or `after` according to the exchange's pagination rules; these cursors must be
numeric IDs. Trade records use `id`; order records use `orderId`. `before` and
`after` cannot be combined. Market and order filters cannot be combined for
trades. Open orders return all currently open orders and do not support pagination.

Prices, amounts and record IDs retain their API string values. Balances are in
asset units, **not** legacy integer units scaled by 100,000,000. `locked` covers
funds locked for orders/pending withdrawals; it replaces the old display's
`pendingFunds`, with v3 semantics. Ticker spreads use `Decimal` and timestamps
include timezone offsets.

## Python usage

```python
from btcmarkets import BTCMarketsClient, BTCMarketsError

with BTCMarketsClient.from_env() as client:
    print(client.ticker("BTC-AUD"))

with BTCMarketsClient.from_env(private=True) as client:
    try:
        print(client.trades(market_id="ETH-AUD", limit=20))
    except BTCMarketsError as exc:
        print(exc.status_code, exc.code)
        if exc.status_code == 429:
            print("Rate limit resets at", exc.headers.get("x-ratelimit-reset"))
```

Methods: `markets()`, `server_time()`, `ticker(market_id)`, `balances()`,
`trades(market_id=None, order_id=None, limit=None, before=None, after=None)` and
`orders(market_id=None, status='all', limit=None, before=None, after=None)`.
History arguments are keyword-only. Private clients can also be constructed with
`BTCMarketsClient(api_key, api_secret)`. Public `from_env()` ignores credentials.

Requests verify TLS, have a default 15-second connect/read timeout, and do not
follow redirects or retry automatically. Requests' timeout is an inactivity
limit, not a strict total-duration deadline. The base URL is fixed to the official
HTTPS endpoint. `rate_limit_headers` contains the last response's `x-ratelimit-*`
headers, including the July 2026 additions. Instances are not thread-safe. An
injected `requests.Session` is caller-owned and must be closed by the caller;
use an unconfigured session to avoid sending unrelated default credentials.

Failures raise `BTCMarketsError`; invalid configuration or arguments raise
`ValueError`. The CLI prints a concise error and exits 1; Ctrl+C exits 130.
See [ErrorCodes.md](ErrorCodes.md) for troubleshooting. Keep the system clock
accurate for authenticated requests. Credentials are never printed by the client;
private command output still contains your financial records.

## Existing script filenames

Run these from the checkout after installing dependencies:

| Filename | Current command / default |
| --- | --- |
| `BTCAUDticker.py` | `ticker BTC-AUD` |
| `LTCAUDticker.py` | `ticker LTC-AUD` |
| `LTCBTCticker.py` | `ticker LTC-BTC` (if active) |
| `ETHAUDTicker.py` | `ticker ETH-AUD --interval 5` |
| `tickerlineBTCAUD.py` | `ticker BTC-AUD --one-line` |
| `AccountBalance.py` | `balances` |
| `OrderHistory.py` | `trades --market ETH-AUD --limit 3` |

For example `python OrderHistory.py --market BTC-AUD --limit 20` overrides those
history defaults. Filename compatibility does not preserve legacy helper
functions or response shapes. `OrderHistory.py` continues to display **executed
trades**; use `btcmarkets orders` for submitted orders, including unfilled ones.
The old `config.py` is now an environment-backed compatibility shim; credentials
hardcoded in a previous copy must be moved to environment variables. `.env` files
are ignored by Git but are **not automatically loaded**.

## Verification and API audit

```sh
python -m unittest discover -s tests -v
python -m compileall -q btcmarkets tests *.py
```

Tests are offline and require no keys. See [docs/API_AUDIT.md](docs/API_AUDIT.md)
for findings, endpoint mappings, evidence and the remaining live-check steps.
The maintained client intentionally covers read-only REST operations; trading,
withdrawals, WebSocket and FIX functionality are outside its scope.

## Licence

GPL version 3 or later; see [Licenses/LICENSE_GPLv3.txt](Licenses/LICENSE_GPLv3.txt).
The licence remains unchanged from the original project.
