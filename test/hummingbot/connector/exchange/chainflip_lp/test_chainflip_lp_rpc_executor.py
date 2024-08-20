import asyncio
import re
from typing import Awaitable, Union
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from substrateinterface.exceptions import SubstrateRequestException

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor import RPCQueryExecutor


class RPCQueryExecutorTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset_dict = {"chain": "Ethereum", "asset": "ETH"}
        cls.quote_asset_dict = {"chain": "Ethereum", "asset": "USDC"}

    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.log_records = []

    def tearDown(self) -> None:
        super().tearDown()
        self.async_loop.stop()
        self.async_loop.close()
        asyncio.set_event_loop(self._original_async_loop)
        self._logs_event = None

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def is_logged(self, log_level: str, message: Union[str, re.Pattern]) -> bool:
        expression = (
            re.compile(
                f"^{message}$".replace(".", r"\.")
                .replace("?", r"\?")
                .replace("/", r"\/")
                .replace("(", r"\(")
                .replace(")", r"\)")
                .replace("[", r"\[")
                .replace("]", r"\]")
            )
            if isinstance(message, str)
            else message
        )
        return any(
            record.levelname == log_level and expression.match(record.getMessage()) is not None
            for record in self.log_records
        )

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_execute_api_request_successful(self, mock_response: MagicMock):
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        response_data = [{"chain": "Ethereum", "asset": "USDT"}]
        mock_response.return_value = response_data
        response = self.async_run_with_timeout(rpc_executor._execute_api_request(MagicMock()))
        mock_response.assert_called_once()
        self.assertIn("data", response)
        self.assertIn("status", response)
        self.assertTrue(response["status"])
        self.assertEqual(response["data"], response_data)
        self.assertTrue(isinstance(response["data"], list))

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_execute_api_request_handles_exceptions(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        response = self.async_run_with_timeout(rpc_executor._execute_api_request(MagicMock()))
        self.assertIn("data", response)
        self.assertIn("status", response)
        self.assertFalse(response["status"])
        self.assertEqual(response["data"], return_data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_execute_rpc_request_successful(self, mock_response: MagicMock):
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        response_data = [{"chain": "Ethereum", "asset": "USDT"}]
        mock_response.return_value = response_data
        response = self.async_run_with_timeout(rpc_executor._execute_rpc_request(MagicMock()))
        mock_response.assert_called_once()
        self.assertIn("data", response)
        self.assertIn("status", response)
        self.assertTrue(response["status"])
        self.assertTrue(isinstance(response["data"], list))

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_execute_rpc_request_handles_exceptions(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        response = self.async_run_with_timeout(rpc_executor._execute_rpc_request(MagicMock()))
        self.assertIn("data", response)
        self.assertIn("status", response)
        self.assertFalse(response["status"])
        self.assertEqual(response["data"], return_data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.websockets_connect")
    def test_subscribe_to_rpc_event(self, mock_socket: MagicMock):
        session_mock = AsyncMock()
        session_mock.recv.__aenter__.return_value = {"chain": "Ethereum", "asset": "USDT"}
        mock_socket.return_value.__aenter__.return_value = session_mock
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        self.async_run_with_timeout(rpc_executor._subscribe_to_rpc_event("stream", []))
        session_mock.send.assert_called_once()
        session_mock.recv.assert_called_once()

    def test_calculate_ticks(self):
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        base_asset = {"chain": "Ethereum", "asset": "USDT"}
        quote_asset = {"chain": "Ethereum", "asset": "USDT"}
        tick = rpc_executor._calculate_tick(2000.00, base_asset, quote_asset)
        self.assertLessEqual(tick, CONSTANTS.UPPER_TICK_BOUND)
        self.assertGreaterEqual(tick, CONSTANTS.LOWER_TICK_BOUND)

    def test_listen_to_order_fills(self):
        pass

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.SubstrateInterface")
    def test_start_instance(self, mock_interface: MagicMock):
        mock_interface.return_value = MagicMock()
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._start_instance(MagicMock())
        mock_interface.assert_called_once()

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.SubstrateInterface")
    def test_start_instance_raises_error(self, mock_interface: MagicMock):
        error_data = {"code": -23000, "detail": "Method not found"}
        mock_interface.side_effect = SubstrateRequestException(error_data)

        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(SubstrateRequestException):
            rpc_executor._start_instance(MagicMock())
            self.assertTrue(self.is_logged("ERROR", str(error_data)))

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_all_asset_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.all_assets())
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_all_market_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.all_markets())
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor._execute_api_request")
    def test_connection_status_fail_when_one_request_is_false(self, mock_response: MagicMock):
        mock_response.return_value = {"status": False, "data": []}
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.check_connection_status())
        self.assertFalse(data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor._execute_rpc_request")
    def test_get_market_price_exception_returns_none(self, mock_response: MagicMock):
        mock_response.return_value = {"status": False, "data": []}
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.get_market_price(self.base_asset_dict, self.quote_asset_dict))
        self.assertIsNone(data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_all_balances_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.get_all_balances())
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_get_open_orders_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.get_open_orders(self.base_asset_dict, self.quote_asset_dict))
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_place_limit_order_exception_returns_False(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(
            rpc_executor.place_limit_order(self.base_asset_dict, self.quote_asset_dict, "11", 122000.00, "buy", 12000)
        )
        self.assertFalse(data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_cancel_order_exception_returns_False(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(
            rpc_executor.cancel_order(self.base_asset_dict, self.quote_asset_dict, "11", "buy")
        )
        self.assertFalse(data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_get_account_order_fills_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        return_asset_data = [self.base_asset_dict, self.base_asset_dict]
        mock = AsyncMock()
        mock.return_value = return_asset_data
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.get_account_order_fills())
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)
