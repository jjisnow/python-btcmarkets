"""Command-line tools shared by the original script entry points."""

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .client import BTCMarketsClient, BTCMarketsError


def positive_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return seconds


def format_ticker(ticker, *, one_line=False):
    """Use ISO timestamps and timezone-aware local time; preserve decimal prices."""
    market = ticker["marketId"]
    bid, ask, last = (Decimal(ticker[k]) for k in ("bestBid", "bestAsk", "lastPrice"))
    if not all(price.is_finite() for price in (bid, ask, last)):
        raise ValueError("non-finite ticker price")
    timestamp = datetime.fromisoformat(ticker["timestamp"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("ticker timestamp is missing its timezone")
    utc = timestamp.astimezone(timezone.utc).isoformat()
    local = timestamp.astimezone().isoformat()
    age = max(0, (datetime.now(timezone.utc) - timestamp).total_seconds())
    fields = [
        f"BTC Markets {market}",
        f"Best bid: {bid}",
        f"Best ask: {ask}",
        f"Spread: {ask - bid}",
        f"Last trade: {last}",
        f"UTC: {utc}",
        f"Local: {local}",
        f"Age: {age:.1f} seconds",
    ]
    return (" | " if one_line else "\n").join(fields)


def format_balances(balances):
    # Asset identity comes from each record, never its position in the response.
    return (
        "\n".join(
            f"{item['assetName']}: balance {item['balance']}, available {item['available']}, locked {item['locked']}"
            for item in balances
        )
        or "No balances returned."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only BTC Markets API v3 tools")
    parser.add_argument("--timeout", type=positive_seconds, default=15, help="request timeout in seconds (default: 15)")
    commands = parser.add_subparsers(dest="command", required=True)
    ticker = commands.add_parser("ticker", help="get a market ticker")
    ticker.add_argument("market", nargs="?", default="BTC-AUD")
    ticker.add_argument("--one-line", action="store_true")
    ticker.add_argument("--interval", type=positive_seconds, help="poll until Ctrl+C")
    ticker.add_argument("--json", action="store_true")
    balance = commands.add_parser("balances", help="get account balances")
    balance.add_argument("--json", action="store_true")
    for name in ("trades", "orders"):
        history = commands.add_parser(name, help=f"get one page of account {name}")
        history.add_argument("--market")
        history.add_argument("--limit", type=int)
        cursors = history.add_mutually_exclusive_group()
        cursors.add_argument("--before")
        cursors.add_argument("--after")
        if name == "trades":
            history.add_argument("--order-id")
        else:
            history.add_argument("--status", choices=("all", "open"), default="all")
    commands.add_parser("markets", help="list active markets")
    commands.add_parser("time", help="get server time")
    args = parser.parse_args(argv)
    try:
        with BTCMarketsClient.from_env(
            private=args.command in ("balances", "trades", "orders"), timeout=args.timeout
        ) as client:
            while True:
                if args.command == "ticker":
                    result = client.ticker(args.market)
                    output = (
                        json.dumps(result, indent=2) if args.json else format_ticker(result, one_line=args.one_line)
                    )
                elif args.command == "balances":
                    result = client.balances()
                    output = json.dumps(result, indent=2) if args.json else format_balances(result)
                elif args.command in ("trades", "orders"):
                    kwargs = {"market_id": args.market, "limit": args.limit, "before": args.before, "after": args.after}
                    if args.command == "trades":
                        result = client.trades(order_id=args.order_id, **kwargs)
                    else:
                        result = client.orders(status=args.status, **kwargs)
                    output = json.dumps(result, indent=2)
                else:
                    result = client.markets() if args.command == "markets" else client.server_time()
                    output = json.dumps(result, indent=2)
                print(output, flush=True)
                if args.command != "ticker" or args.interval is None:
                    break
                time.sleep(args.interval)
        return 0
    except KeyboardInterrupt:
        return 130
    except BTCMarketsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if exc.status_code == 429:
            reset = exc.headers.get("x-ratelimit-reset")
            print(
                f"Rate limited; retry after Unix time {reset}." if reset else "Rate limited; wait before retrying.",
                file=sys.stderr,
            )
        return 1
    except (ValueError, KeyError, TypeError, InvalidOperation):
        # Validation errors are local and do not contain key/secret values.
        print("Error: invalid configuration, arguments or API response; see README.md.", file=sys.stderr)
        return 1


def legacy_main(command, *defaults):
    """Keep old filenames usable while forwarding options to the shared CLI."""
    return main([command, *defaults, *sys.argv[1:]])
