import contextlib
import io
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from btcmarkets import BTCMarketsError
from btcmarkets.cli import format_balances, format_ticker, main


class CLITests(unittest.TestCase):
    def test_balances_use_asset_identity_and_no_integer_scaling(self):
        output = format_balances(
            [
                {"assetName": "NEW", "balance": "1.00000001", "available": "1", "locked": "0.00000001"},
                {"assetName": "AUD", "balance": "200", "available": "190", "locked": "10"},
            ]
        )
        self.assertIn("NEW: balance 1.00000001", output)
        self.assertIn("AUD: balance 200", output)
        self.assertEqual(format_balances([]), "No balances returned.")

    def test_ticker_decimal_spread_and_utc_timestamp(self):
        ticker = {
            "marketId": "BTC-AUD",
            "bestBid": "0.1",
            "bestAsk": "0.3",
            "lastPrice": "0.20000001",
            "timestamp": "2026-01-01T00:00:00.123456Z",
        }
        output = format_ticker(ticker, one_line=True)
        self.assertIn("Spread: 0.2 |", output)
        self.assertIn("Last trade: 0.20000001", output)
        self.assertIn("UTC: 2026-01-01T00:00:00.123456+00:00", output)
        self.assertNotIn("\n", output)
        ticker["timestamp"] = "2026-01-01T00:00:00"
        with self.assertRaises(ValueError):
            format_ticker(ticker)

    def test_local_time_handles_negative_and_fractional_offsets(self):
        from datetime import timedelta

        class TestDateTime(datetime):
            def astimezone(self, tz=None):
                return super().astimezone(tz or timezone(timedelta(hours=-3, minutes=-30)))

        ticker = {
            "marketId": "BTC-AUD",
            "bestBid": "1",
            "bestAsk": "2",
            "lastPrice": "1.5",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        with patch("btcmarkets.cli.datetime", TestDateTime):
            output = format_ticker(ticker)
        self.assertIn("Local: 2025-12-31T20:30:00-03:30", output)

    def test_private_cli_without_credentials_fails_cleanly(self):
        with patch.dict("os.environ", {}, clear=True), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["balances"]), 1)
        self.assertIn("Error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_cli_trades_options_and_json(self):
        with patch("btcmarkets.cli.BTCMarketsClient.from_env") as factory:
            client = factory.return_value.__enter__.return_value
            client.trades.return_value = [{"id": "123", "price": "0.10000001"}]
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(["trades", "--market", "ETH-AUD", "--limit", "3", "--before", "456"]), 0)
            client.trades.assert_called_once_with(market_id="ETH-AUD", order_id=None, limit=3, before="456", after=None)
            self.assertIn('"price": "0.10000001"', out.getvalue())

    def test_cli_rate_limit_and_keyboard_interrupt(self):
        with patch("btcmarkets.cli.BTCMarketsClient.from_env") as factory:
            client = factory.return_value.__enter__.return_value
            client.markets.side_effect = BTCMarketsError(
                "HTTP 429", status_code=429, headers={"x-ratelimit-reset": "123"}
            )
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(["markets"]), 1)
            self.assertIn("123", err.getvalue())
            client.markets.side_effect = KeyboardInterrupt
            self.assertEqual(main(["markets"]), 130)

    def test_polling_stops_on_interrupt(self):
        with (
            patch("btcmarkets.cli.BTCMarketsClient.from_env") as factory,
            patch("btcmarkets.cli.time.sleep", side_effect=KeyboardInterrupt),
        ):
            client = factory.return_value.__enter__.return_value
            client.ticker.return_value = {"marketId": "ETH-AUD"}
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["ticker", "ETH-AUD", "--json", "--interval", "5"]), 130)
            client.ticker.assert_called_once_with("ETH-AUD")

    def test_invalid_interval_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for value in ("0", "-1", "nan", "inf"):
                with self.subTest(value=value), self.assertRaises(SystemExit):
                    main(["ticker", "--interval", value])
