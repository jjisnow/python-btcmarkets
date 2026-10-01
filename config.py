"""Compatibility names for external scripts; configure credentials via environment.

The maintained scripts use BTCMarketsClient.from_env() directly. Never put
credentials in this tracked file. Username is unnecessary for API v3.
"""

import os

username = ""
apikey_public = os.environ.get("BTCMARKETS_API_KEY", "")
apikey_secret = os.environ.get("BTCMARKETS_API_SECRET", "")
domain = "https://api.btcmarkets.net"
