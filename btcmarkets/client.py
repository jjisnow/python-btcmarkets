"""Small, read-only BTC Markets API v3 client.

Amounts and record IDs retain their API string representation. Private GET
signatures deliberately exclude query parameters, as required by BTC Markets.
"""

import base64
import binascii
import hashlib
import hmac
import math
import os
import re
import time

import requests

BASE_URL = "https://api.btcmarkets.net"


class BTCMarketsError(Exception):
    """A transport, HTTP or response-format failure without request credentials."""

    def __init__(self, message, *, status_code=None, code=None, headers=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.headers = requests.structures.CaseInsensitiveDict(headers or {})


class BTCMarketsClient:
    """Reusable read-only client. Use a context manager to close its session.

    No automatic retries are made. Callers can inspect error.headers for
    x-ratelimit-reset after HTTP 429. Instances are not thread-safe.
    """

    def __init__(self, api_key=None, api_secret=None, *, timeout=15, session=None):
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a positive finite number of seconds")
        if bool(api_key) != bool(api_secret):
            raise ValueError("provide both API key and secret, or neither")
        self._api_key = api_key
        self._secret = None
        if api_secret:
            try:
                self._secret = base64.b64decode(api_secret, validate=True)
            except (binascii.Error, ValueError, TypeError) as exc:
                raise ValueError("API secret must be valid base64") from exc
            if not self._secret:
                raise ValueError("API secret must not be empty")
        self.timeout = timeout
        self._owns_session = session is None
        self._session = session if session is not None else requests.Session()
        self.rate_limit_headers = requests.structures.CaseInsensitiveDict()

    @classmethod
    def from_env(cls, *, private=False, **kwargs):
        """Public calls ignore credentials; private calls require both variables."""
        if not private:
            return cls(**kwargs)
        key = os.environ.get("BTCMARKETS_API_KEY")
        secret = os.environ.get("BTCMARKETS_API_SECRET")
        if not key or not secret:
            raise ValueError("set BTCMARKETS_API_KEY and BTCMARKETS_API_SECRET")
        return cls(key, secret, **kwargs)

    def close(self):
        if self._owns_session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _get(self, path, *, params=None, private=False, expected_type=list):
        headers = {"Accept": "application/json"}
        if private:
            if not self._api_key or self._secret is None:
                raise ValueError("private calls require an API key and secret")
            timestamp = str(time.time_ns() // 1_000_000)
            message = ("GET" + path + timestamp).encode("utf-8")
            signature = base64.b64encode(hmac.new(self._secret, message, hashlib.sha512).digest()).decode("ascii")
            headers.update(
                {
                    "BM-AUTH-APIKEY": self._api_key,
                    "BM-AUTH-TIMESTAMP": timestamp,
                    "BM-AUTH-SIGNATURE": signature,
                }
            )
        try:
            response = self._session.get(
                BASE_URL + path,
                params=params,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            # Exception strings can include URLs/proxy details. Do not echo them.
            raise BTCMarketsError(f"request failed ({type(exc).__name__})") from None
        with response:
            self.rate_limit_headers = requests.structures.CaseInsensitiveDict(
                {key: value for key, value in response.headers.items() if key.lower().startswith("x-ratelimit-")}
            )
            if not 200 <= response.status_code < 300:
                code = None
                try:
                    payload = response.json()
                    if isinstance(payload, dict) and isinstance(payload.get("code"), str):
                        code = payload["code"]
                except ValueError:
                    pass
                # Retain status/code, but never print arbitrary server response bodies.
                raise BTCMarketsError(
                    f"BTC Markets returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    code=code,
                    headers=self.rate_limit_headers,
                )
            try:
                payload = response.json()
            except ValueError:
                raise BTCMarketsError("BTC Markets returned invalid JSON") from None
            if not isinstance(payload, expected_type):
                raise BTCMarketsError("BTC Markets returned an unexpected response shape")
            return payload

    @staticmethod
    def _market_id(market_id):
        if not isinstance(market_id, str) or not re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+", market_id):
            raise ValueError("market ID must have the form BTC-AUD")
        return market_id

    @staticmethod
    def _pagination(limit, before, after):
        if limit is not None and (type(limit) is not int or limit <= 0):
            raise ValueError("limit must be a positive integer")
        if before is not None and after is not None:
            raise ValueError("use either before or after")
        for cursor in (before, after):
            if cursor is not None and (
                isinstance(cursor, bool)
                or not isinstance(cursor, (str, int))
                or not re.fullmatch(r"[0-9]+", str(cursor))
            ):
                raise ValueError("pagination cursor must be a non-negative integer ID")
        return {k: v for k, v in {"limit": limit, "before": before, "after": after}.items() if v is not None}

    def markets(self):
        return self._get("/v3/markets")

    def server_time(self):
        return self._get("/v3/time", expected_type=dict)

    def ticker(self, market_id):
        return self._get(f"/v3/markets/{self._market_id(market_id)}/ticker", expected_type=dict)

    def balances(self):
        return self._get("/v3/accounts/me/balances", private=True)

    def trades(self, *, market_id=None, order_id=None, limit=None, before=None, after=None):
        """Return one page of executed trades, optionally filtered by market/order."""
        if market_id is not None and order_id is not None:
            raise ValueError("market_id and order_id cannot be combined")
        params = self._pagination(limit, before, after)
        if market_id is not None:
            params["marketId"] = self._market_id(market_id)
        if order_id is not None:
            if not isinstance(order_id, str) or not order_id:
                raise ValueError("order_id must be a non-empty string")
            params["orderId"] = order_id
        return self._get("/v3/trades", params=params, private=True)

    def orders(self, *, market_id=None, status="all", limit=None, before=None, after=None):
        """Return one page of all orders, or every open order with status='open'."""
        if status not in ("all", "open"):
            raise ValueError("status must be all or open")
        if status == "open" and any(v is not None for v in (limit, before, after)):
            raise ValueError("open orders do not support pagination")
        params = self._pagination(limit, before, after)
        params["status"] = status
        if market_id is not None:
            params["marketId"] = self._market_id(market_id)
        return self._get("/v3/orders", params=params, private=True)
