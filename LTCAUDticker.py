#!/usr/bin/env python3
"""Legacy filename forwarding to the API v3 CLI."""

from btcmarkets.cli import legacy_main

if __name__ == "__main__":
    raise SystemExit(legacy_main("ticker", "LTC-AUD"))
