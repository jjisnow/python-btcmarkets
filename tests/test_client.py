"""Offline protocol and failure regression tests; never use account credentials."""

import base64
import importlib
import json
import unittest
from unittest.mock import Mock, patch

import requests

from btcmarkets import BTCMarketsClient, BTCMarketsError
from btcmarkets.client import BASE_URL


def response(payload=None, status=200, headers=None, raw=None):
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result._content = raw if raw is not None else json.dumps(payload).encode()
    return result


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock(spec=requests.Session)
        self.session.get.return_value = response([])
        self.client = BTCMarketsClient("test-key", base64.b64encode(b"secret").decode(), session=self.session)

    def test_private_signature_matches_fixed_v3_vector_and_excludes_query(self):
        # Fixed vector cross-checked with Node.js crypto.createHmac, not client helpers.
        with patch("btcmarkets.client.time.time_ns", return_value=1_600_000_000_000_000_000):
            self.client.orders(market_id="BTC-AUD", limit=3, before="123")
        call = self.session.get.call_args
        self.assertEqual(call.args, (BASE_URL + "/v3/orders",))
        self.assertEqual(call.kwargs["params"], {"marketId": "BTC-AUD", "status": "all", "limit": 3, "before": "123"})
        self.assertEqual(call.kwargs["headers"]["BM-AUTH-TIMESTAMP"], "1600000000000")
        self.assertEqual(call.kwargs["headers"]["BM-AUTH-APIKEY"], "test-key")
        self.assertEqual(
            call.kwargs["headers"]["BM-AUTH-SIGNATURE"],
            "/WfwrvpTJh4BBugxjVTT/nW59+QQu/q9UsBMb3NgfnzDKED6hsV0mQxAqijdm/cehwARwbyOb2vTGukgQl5YiA==",
        )
        self.assertEqual(call.kwargs["timeout"], 15)
        self.assertFalse(call.kwargs["allow_redirects"])

    def test_public_ticker_does_not_send_credentials_or_convert_prices(self):
        payload = {"marketId": "BTC-AUD", "bestAsk": "123.00000001"}
        self.session.get.return_value = response(payload)
        self.assertEqual(self.client.ticker("BTC-AUD"), payload)
        self.assertEqual(self.session.get.call_args.args[0], BASE_URL + "/v3/markets/BTC-AUD/ticker")
        self.assertEqual(self.session.get.call_args.kwargs["headers"], {"Accept": "application/json"})

    def test_read_only_routes(self):
        for method, path, kwargs, payload in (
            ("markets", "/v3/markets", {}, []),
            ("server_time", "/v3/time", {}, {"timestamp": "2026-01-01T00:00:00Z"}),
            ("balances", "/v3/accounts/me/balances", {}, [{"assetName": "ETH", "balance": "1.07583642"}]),
            ("trades", "/v3/trades", {"market_id": "ETH-AUD", "limit": 3}, []),
            ("orders", "/v3/orders", {"status": "open"}, []),
        ):
            with self.subTest(method=method):
                self.session.get.return_value = response(payload)
                self.assertEqual(getattr(self.client, method)(**kwargs), payload)
                self.assertEqual(self.session.get.call_args.args[0], BASE_URL + path)

    def test_order_ids_remain_strings_and_are_query_parameters(self):
        self.client.trades(order_id="client/id?x=1")
        self.assertEqual(self.session.get.call_args.kwargs["params"], {"orderId": "client/id?x=1"})

    def test_local_validation_sends_no_requests(self):
        for invoke in (
            lambda: self.client.ticker("BTC/AUD"),
            lambda: self.client.ticker("../accounts/me/balances"),
            lambda: self.client.trades(market_id="BTC-AUD", order_id="123"),
            lambda: self.client.trades(limit=0),
            lambda: self.client.trades(limit=True),
            lambda: self.client.trades(before="abc"),
            lambda: self.client.trades(before="1", after="2"),
            lambda: self.client.orders(status="invalid"),
            lambda: self.client.orders(status="open", limit=3),
            lambda: BTCMarketsClient(session=self.session).balances(),
        ):
            with self.subTest(invoke=invoke), self.assertRaises(ValueError):
                invoke()
        self.session.get.assert_not_called()

    def test_invalid_config(self):
        for kwargs in (
            {"api_key": "key"},
            {"api_secret": "c2VjcmV0"},
            {"api_key": "key", "api_secret": "not base64!"},
            {"timeout": 0},
            {"timeout": float("nan")},
            {"timeout": float("inf")},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                BTCMarketsClient(**kwargs)

    def test_environment_credentials_required_only_for_private_clients(self):
        with patch.dict("os.environ", {"BTCMARKETS_API_SECRET": "bad!"}, clear=True):
            with BTCMarketsClient.from_env():
                pass
            with self.assertRaises(ValueError):
                BTCMarketsClient.from_env(private=True)
        with (
            patch.dict("os.environ", {"BTCMARKETS_API_KEY": "key", "BTCMARKETS_API_SECRET": "c2VjcmV0"}, clear=True),
            BTCMarketsClient.from_env(private=True) as client,
        ):
            self.assertEqual(client._secret, b"secret")

    def test_http_error_exposes_status_code_and_rate_limit(self):
        self.session.get.return_value = response(
            {"code": "TooManyRequests", "message": "sensitive response"},
            status=429,
            headers={"X-RateLimit-Reset": "1600000010", "X-RateLimit-Remaining": "0"},
        )
        with self.assertRaises(BTCMarketsError) as caught:
            self.client.balances()
        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(caught.exception.code, "TooManyRequests")
        self.assertEqual(caught.exception.headers["x-ratelimit-reset"], "1600000010")
        self.assertNotIn("sensitive", str(caught.exception))
        self.session.get.assert_called_once()

    def test_html_http_error_and_redirect_are_rejected(self):
        for status in (401, 500, 302):
            with self.subTest(status=status):
                self.session.get.return_value = response(status=status, raw=b"<html>error</html>")
                with self.assertRaises(BTCMarketsError) as caught:
                    self.client.balances()
                self.assertEqual(caught.exception.status_code, status)

    def test_invalid_json_and_wrong_response_shape(self):
        for res in (response(raw=b"not json"), response({"unexpected": "object"})):
            self.session.get.return_value = res
            with self.assertRaises(BTCMarketsError):
                self.client.balances()

    def test_timeout_and_connection_error_are_sanitized_without_retries(self):
        for exception in (requests.Timeout, requests.ConnectionError):
            self.session.get.reset_mock()
            self.session.get.side_effect = exception("credential secret URL")
            with self.assertRaises(BTCMarketsError) as caught:
                self.client.balances()
            self.assertNotIn("credential", str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)
            self.session.get.assert_called_once()

    def test_session_ownership(self):
        self.client.close()
        self.session.close.assert_not_called()
        with patch("btcmarkets.client.requests.Session") as factory:
            with BTCMarketsClient():
                pass
            factory.return_value.close.assert_called_once()

    def test_legacy_scripts_are_safe_to_import(self):
        with patch("requests.sessions.Session.request", side_effect=AssertionError("network on import")):
            for name in (
                "AccountBalance",
                "OrderHistory",
                "BTCAUDticker",
                "LTCAUDticker",
                "LTCBTCticker",
                "ETHAUDTicker",
                "tickerlineBTCAUD",
            ):
                importlib.import_module(name)
