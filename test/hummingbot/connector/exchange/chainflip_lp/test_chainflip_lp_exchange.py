import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch
from functools import partial


from aioresponses import aioresponses
from aioresponses.core import RequestCall
from substrateinterface import Keypair
from bidict import bidict

from test.hummingbot.connector.exchange.chainflip_lp.mock_rpc_executor import MockRPCExecutor

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_exchange import ChainflipLpExchange
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import  TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent, OrderFilledEvent

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)


class ChainflipLpExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    client_order_id_prefix = "0x"
    exchange_order_id_prefix = "0x"
    @property
    def all_symbols_url(self):
        raise NotImplementedError

    @property
    def latest_prices_url(self):
        raise NotImplementedError

    @property
    def network_status_url(self):
        raise NotImplementedError

    @property
    def trading_rules_url(self):
        raise NotImplementedError

    @property
    def order_creation_url(self):
        raise NotImplementedError

    @property
    def balance_url(self):
        raise NotImplementedError
    
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls._address = Keypair.create_from_mnemonic(
            "hollow crack grain grab equal rally ceiling manage goddess grass negative canal"  # noqa: mock
        ).ss58_address
        cls._eth_chain = CONSTANTS.DEFAULT_CHAIN_CONFIG['ETH']
        cls._usdc_chain = CONSTANTS.DEFAULT_CHAIN_CONFIG['USDC']
        cls.base_asset_dict = {"chain":"Ethereum", "asset":"ETH"}
        cls.quote_asset_dict = {"chain": "Ethereum","asset":"USDC"}
        cls.base_asset = "ETH"
        cls.quote_asset = "USDC"
        cls.trading_pair = f'{cls.base_asset}-{cls.quote_asset}'
        cls.ex_trading_pair = f'{cls.base_asset}-{cls.quote_asset}'


    def setUp(self):
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        self._logs_event: Optional[asyncio.Event] = None
        self.exchange._data_source.logger().setLevel(1)
        self.exchange._data_source.logger().addHandler(self)
        self.exchange._set_trading_pair_symbol_map(bidict({self.exchange_trading_pair: self.trading_pair}))


    def tearDown(self) -> None:
        super().tearDown()
        self.async_loop.stop()
        self.async_loop.close()
        asyncio.set_event_loop(self._original_async_loop)
        self._logs_event = None

    def handle(self, record):
        super().handle(record=record)
        if self._logs_event is not None:
            self._logs_event.set()

    def reset_log_event(self):
        if self._logs_event is not None:
            self._logs_event.clear()

    async def wait_for_a_log(self):
        if self._logs_event is not None:
            await self._logs_event.wait()

    @property
    def all_assets_mock_response(self):
        return [
            {"chain": "Ethereum", "asset": self.quote_asset},
            {"chain": "Ethereum", "asset": self.base_asset},
        ]
    @property
    def all_symbols_request_mock_response(self):
        response = {
            "result": {
                "fees": {
                    "Ethereum": {
                        self.base_asset: {
                            "limit_order_fee_hundredth_pips": 500,
                            "range_order_fee_hundredth_pips": 500,
                            "range_order_total_fees_earned": {
                                "base": "0x3d4a754fc1d2302",
                                "quote": "0x3689782a",
                            },
                            "limit_order_total_fees_earned": {
                                "base": "0x83c94dd54804790a",
                                "quote": "0x670a76ae0",
                            },
                            "range_total_swap_inputs": {
                                "base": "0x1dc18b046dde67f2b0",
                                "quote": "0x1a774f80e62",
                            },
                            "limit_total_swap_inputs": {
                                "base": "0x369c2e5bafeffddab46",
                                "quote": "0x2be491b4d31d",
                            },
                            "quote_asset": {"chain": "Ethereum", "asset": self.quote_asset},
                        },
                        
                    }
                }   
            }
        }
        return response


    @property
    def latest_prices_request_mock_response(self):
        response = {
            'result': {
                'base_asset': {
                    'chain': 'Ethereum', 'asset': 'ETH'
                }, 
                'quote_asset': {
                    'chain': 'Ethereum', 'asset': 'USDC'
                }, 
                'sell': '0x3bc9b4d35fc93990865a6', 
                'buy': '0x3baddb29af3e837abc358', 
                'range_order': '0x3bc9b4d35fc93990865a6'
                }
        }
        
        return response
    

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "result": {
                "fees": {
                    "Ethereum": {
                        self.base_asset: {
                            "limit_order_fee_hundredth_pips": 500,
                            "range_order_fee_hundredth_pips": 500,
                            "range_order_total_fees_earned": {
                                "base": "0x3d4a754fc1d2302",
                                "quote": "0x3689782a",
                            },
                            "limit_order_total_fees_earned": {
                                "base": "0x83c94dd54804790a",
                                "quote": "0x670a76ae0",
                            },
                            "range_total_swap_inputs": {
                                "base": "0x1dc18b046dde67f2b0",
                                "quote": "0x1a774f80e62",
                            },
                            "limit_total_swap_inputs": {
                                "base": "0x369c2e5bafeffddab46",
                                "quote": "0x2be491b4d31d",
                            },
                            "quote_asset": {"chain": "Ethereum", "asset": self.quote_asset},
                        },
                        "INVALID": {
                            "limit_order_fee_hundredth_pips": 500,
                            "range_order_fee_hundredth_pips": 500,
                            "range_order_total_fees_earned": {
                                "base": "0x3d4a754fc1d2302",
                                "quote": "0x3689782a",
                            },
                            "limit_order_total_fees_earned": {
                                "base": "0x83c94dd54804790a",
                                "quote": "0x670a76ae0",
                            },
                            "range_total_swap_inputs": {
                                "base": "0x1dc18b046dde67f2b0",
                                "quote": "0x1a774f80e62",
                            },
                            "limit_total_swap_inputs": {
                                "base": "0x369c2e5bafeffddab46",
                                "quote": "0x2be491b4d31d",
                            },
                            "quote_asset": {"chain": "Ethereum", "asset": "PAIR"},
                        },
                        
                    }
                }   
            }
        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return True

    @property
    def trading_rules_request_mock_response(self):
        raise NotImplementedError

    @property
    def trading_rules_request_erroneous_mock_response(self):
        raise NotImplementedError

    @property
    def order_creation_request_successful_mock_response(self):
        response = {
            "result": {
                "tx_details": {
                    "tx_hash": "0x3cb78cdbbfc34634e33d556a94ee7438938b65a5b852ee523e4fc3c0ec3f8151",
                    "response": [
                        {
                            "base_asset": self.base_asset,
                            "quote_asset": self.quote_asset,
                            "side": "buy",
                            "id": "0x11",
                            "tick": 50,
                            "sell_amount_total": "0x100000",
                            "collected_fees": "0x0",
                            "bought_amount": "0x0",
                            "sell_amount_change": {
                                "increase": "0x100000"
                            }
                        }
                    ]
                }
            },
        }
        return response

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        response = {
            "result": {
                "Ethereum": [
                    {
                        "asset": self.base_asset,
                        "balance": "0x2386f26fc0bda2"
                    },
                    {
                        "asset": self.quote_asset,
                        "balance": "0x8bb50bca00"
                    }
                ]
            },
        }
        return response

    @property
    def balance_request_mock_response_only_base(self):
        response = {
            "result": {
                "Ethereum": [
                    {
                        "asset": self.base_asset,
                        "balance": "0x2386f26fc0bda2"
                    }
                ]
            }
        }
        return response

    @property
    def balance_event_websocket_update(self):
        response = {
            "result": {
                "Ethereum": [
                    {
                        "asset": self.base_asset,
                        "balance": "0x2386f26fc0bda2"
                    },
                    {
                        "asset": self.quote_asset,
                        "balance": "0x8bb50bca00"
                    }
                ]
            },
        }
        return response


    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT]

    @property
    def expected_trading_rule(self):
        raise NotImplementedError

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["symbols"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return hex(28)

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return NotImplementedError

    @property
    def expected_fill_trade_id(self) -> str:
        return NotImplementedError
    @property
    def expected_exchange_order_id(self):
        return "0x1b99cba5555ad0ba890756fe16e499cb884b46a165b89bdce77ee8913b55ffff"  # noqa: mock
    
    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange =  ChainflipLpExchange(
            client_config_map=client_config_map,
            chainflip_lp_api_url="",
            chainflip_lp_address= self._address,
            chainflip_eth_chain=self._eth_chain,
            chainflip_usdc_chain= self._usdc_chain,
            trading_pairs=[self.trading_pair],
        )
        exchange._data_source._rpc_executor = MockRPCExecutor()
        return exchange
    def validate_auth_credentials_present(self, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def configure_no_fills_trade_response(self):
        order_fills_response = []
        self.exchange._data_source._rpc_executor._order_fills_responses.put_nowait(order_fills_response)

    def configure_all_symbols_response(
        self, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        response = self.all_symbols_request_mock_response
        self.exchange._data_source._rpc_executor._all_markets_responses.put_nowait(response)
        return ""

    def configure_successful_creation_order_status_response(
        self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        creation_response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._data_source._rpc_executor._place_order_responses = mock_queue
        return ""

    def configure_erroneous_creation_order_status_response(
        self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        creation_response = None
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._data_source._rpc_executor._place_order_responses = mock_queue
        return ""
    def configure_successful_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._rpc_executor._cancel_order_responses = mock_queue
        return ""

    def configure_erroneous_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = {}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._rpc_executor._cancel_order_responses = mock_queue
        return ""

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        data = self.build_order_event_websocket_update(
            order=order,
            filled_quantity=Decimal("0"),
            filled_price=Decimal("0"),
            fee=Decimal("0"),
            status="OPEN",
        )
        return data

    def order_event_for_partially_filled_websocket_update(self, order: InFlightOrder):
        data = self.build_order_event_websocket_update(
            order=order,
            filled_quantity=self.expected_partial_fill_amount,
            filled_price=self.expected_partial_fill_price,
            fee=Decimal("0"),
            status="OPEN",
        )
        return data

    def order_event_for_partially_canceled_websocket_update(self, order: InFlightOrder):
        data = self.build_order_event_websocket_update(
            order=order,
            filled_quantity=self.expected_partial_fill_amount,
            filled_price=self.expected_partial_fill_price,
            fee=Decimal("0"),
            status="CANCELLED",
        )
        return data

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        data = self.build_order_event_websocket_update(
            order=order,
            filled_quantity=Decimal("0"),
            filled_price=Decimal("0"),
            fee=Decimal("0"),
            status="CANCELLED",
        )
        return data

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        data = self.build_order_event_websocket_update(
            order=order,
            filled_quantity=order.amount,
            filled_price=order.price,
            fee=Decimal("0"),
            status="CLOSED",
        )
        return data

    def build_order_event_websocket_update(
        self,
        order: InFlightOrder,
        filled_quantity: Decimal,
        filled_price: Decimal,
        fee: Decimal,
        status: str,
    ):
        data = {
            "type": "Order",
            "stid": 50133,
            "client_order_id": order.client_order_id,
            "avg_filled_price": str(filled_price),
            "fee": str(fee),
            "filled_quantity": str(filled_quantity),
            "status": status,
            "id": order.exchange_order_id,
            "user": "5EqHNNKJWA4U6dyZDvUSkKPQCt6PGgrAxiSBRvC6wqz2xKXU",  # noqa: mock
            "pair": {"base": {"asset": self.base_asset}, "quote": {"asset": "1"}},
            "side": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "order_type": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
            "qty": str(order.amount),
            "price": str(order.price),
            "timestamp": 1682480373,
        }

        return {"websocket_streams": {"data": json.dumps(data)}}

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        data = self.build_trade_event_websocket_update(
            order=order,
            filled_quantity=order.amount,
            filled_price=order.price,
        )
        return data

    def trade_event_for_partial_fill_websocket_update(self, order: InFlightOrder):
        data = self.build_trade_event_websocket_update(
            order=order,
            filled_quantity=self.expected_partial_fill_amount,
            filled_price=self.expected_partial_fill_price,
        )
        return data

    def build_trade_event_websocket_update(
        self,
        order: InFlightOrder,
        filled_quantity: Decimal,
        filled_price: Decimal,
    ) -> Dict[str, Any]:
        data = {
            "type": "TradeFormat",
            "stid": 50133,
            "p": str(filled_price),
            "q": str(filled_quantity),
            "m": self.exchange_trading_pair,
            "t": str(self.exchange.current_timestamp),
            "cid": str(order.client_order_id),
            "order_id": str(order.exchange_order_id),
            "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "trade_id": self.expected_fill_trade_id,
        }

        return {"websocket_streams": {"data": json.dumps(data)}}

    @aioresponses()
    def test_check_network_success(self, mock_api):
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)

        network_status = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, network_status)

    

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    

    @aioresponses()
    def test_check_network_success(self, mock_api):
        self.exchange._data_source._rpc_executor.__check_connection_response.put_nowait(True)

        network_status = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, network_status)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        self.exchange._data_source._rpc_executor.__check_connection_response.put_nowait(False)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.exchange._data_source._rpc_executor._all_assets_responses = mock_queue

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        response = self.latest_prices_request_mock_response
        self.exchange._data_source._rpc_executor._get_market_price_responses.put_nowait(response)

        latest_prices: Dict[str, float] = self.async_run_with_timeout(
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(1, len(latest_prices))
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

    @aioresponses()
    def test_invalid_trading_pair_not_in_all_trading_pairs(self, mock_api):
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        invalid_pair, response = self.all_symbols_including_invalid_pair_mock_response
        self.exchange._data_source._rpc_executor._all_markets_responses.put_nowait(response)

        all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertNotIn(invalid_pair, all_trading_pairs)

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        self.exchange._data_source._assets_map = None
        queue_mock = AsyncMock()
        queue_mock.get.side_effect = Exception
        self.exchange._data_source._rpc_executor._all_assets_responses = queue_mock

        result: List[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))


    def test_is_exception_related_to_time_synchronizer_returns_false(self):
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(request_exception=None))

    def test_create_user_stream_tracker_task(self):
        self.assertIsNone(self.exchange._create_user_stream_tracker_task())
    @aioresponses()
    def test_update_trading_rues(self, mock_api):
        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        trading_rule: TradingRule = self.exchange.trading_rules[self.trading_pair]

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(trading_rule))

        trading_rule_with_default_values = TradingRule(trading_pair=self.trading_pair)

        # The following element can't be left with the default value because that breaks quantization in Cython
        self.assertNotEqual(trading_rule_with_default_values.min_base_amount_increment,
                            trading_rule.min_base_amount_increment)
        self.assertNotEqual(trading_rule_with_default_values.min_price_increment,
                            trading_rule.min_price_increment)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        pass

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertIn(order_id, self.exchange.in_flight_orders)

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} {self.trading_pair}.",
            )
        )
    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        pass

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_successful_cancelation_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_pending_cancel_confirmation)

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
        pass

    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        pass

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        pass

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        formmatted_data = DataFormatter.format_balance_response(response)
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(formmatted_data[self.base_asset], available_balances[self.base_asset])
        self.assertEqual(formmatted_data[self.quote_asset], available_balances[self.quote_asset])
        self.assertEqual(formmatted_data[self.base_asset], total_balances[self.base_asset])
        self.assertEqual(formmatted_data[self.base_asset], total_balances[self.quote_asset])

        response = self.balance_request_mock_response_only_base

        self._configure_balance_response(response=response, mock_api=mock_api)
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn(self.quote_asset, available_balances)
        self.assertNotIn(self.quote_asset, total_balances)
        self.assertEqual(formmatted_data[self.base_asset], available_balances[self.base_asset])
        self.assertEqual(formmatted_data[self.base_asset], total_balances[self.base_asset])

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_canceled(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed(self, mock_api):
        pass
    @aioresponses()
    def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        pass
    @aioresponses()
    def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self, mock_api):
        pass

    def test_user_stream_update_for_new_order(self):
        pass
    def test_user_stream_update_for_canceled_order(self):
        pass

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
       pass

    def test_user_stream_balance_update(self):
        pass

    def test_user_stream_raises_cancel_exception(self):
        pass

    def test_user_stream_logs_errors(self):
        pass
    @aioresponses()
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        pass

    @aioresponses()
    def test_cancel_lost_order_successfully(self, mock_api):
       pass

    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_api):
        pass       
    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        pass

    def test_lost_order_removed_after_cancel_status_user_event_received(self):
        pass

    @aioresponses()
    def test_lost_order_user_stream_full_fill_events_are_processed(self, mock_api):
        pass

    def _configure_balance_response(
        self,
        response: Dict[str, Any],
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        all_assets_mock_response = self.all_assets_mock_response
        self.exchange._data_source._rpc_executor._all_assets_responses.put_nowait(all_assets_mock_response)
        self.exchange._data_source._rpc_executor._balances_responses.put_nowait(response)
        return ""

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {"cancel_order": True}


    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return [self._orders_status_response(order=order)]

    def _orders_status_response(self, order: InFlightOrder) -> Any:
        return {
            "afp": "0",
            "cid": "0x" + order.client_order_id.encode("utf-8").hex(),
            "fee": "0",
            "fq": "0",
            "id": order.exchange_order_id,
            "isReverted": False,
            "m": self.exchange_trading_pair,
            "ot": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
            "p": str(order.price),
            "q": str(order.amount),
            "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "sid": 1,
            "st": "OPEN",
            "t": 160001112.223,
            "u": "",
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "afp": "0",
            "cid": "0x" + order.client_order_id.encode("utf-8").hex(),
            "fee": "0",
            "fq": "0",
            "id": order.exchange_order_id,
            "isReverted": False,
            "m": self.exchange_trading_pair,
            "ot": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
            "p": str(order.price),
            "q": str(order.amount),
            "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "sid": 1,
            "st": "CANCELLED",
            "t": 160001112.223,
            "u": "",
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "afp": str(order.price),
            "cid": "0x" + order.client_order_id.encode("utf-8").hex(),
            "fee": str(self.expected_fill_fee.flat_fees[0].amount),
            "fq": str(order.amount),
            "id": order.exchange_order_id,
            "isReverted": False,
            "m": self.exchange_trading_pair,
            "ot": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
            "p": str(order.price),
            "q": str(order.amount),
            "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "sid": int(self.expected_fill_trade_id),
            "st": "CLOSED",
            "t": 160001112.223,
            "u": "",
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "afp": str(self.expected_partial_fill_price),
            "cid": "0x" + order.client_order_id.encode("utf-8").hex(),
            "fee": str(self.expected_partial_fill_fee.flat_fees[0].amount),
            "fq": str(self.expected_partial_fill_amount),
            "id": order.exchange_order_id,
            "isReverted": False,
            "m": self.exchange_trading_pair,
            "ot": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
            "p": str(order.price),
            "q": str(order.amount),
            "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "sid": int(self.expected_fill_trade_id),
            "st": "OPEN",
            "t": 160001112.223,
            "u": "",
        }

    def _order_status_request_partially_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "afp": str(self.expected_partial_fill_price),
            "cid": "0x" + order.client_order_id.encode("utf-8").hex(),
            "fee": str(self.expected_partial_fill_fee.flat_fees[0].amount),
            "fq": str(self.expected_partial_fill_amount),
            "id": order.exchange_order_id,
            "isReverted": False,
            "m": self.exchange_trading_pair,
            "ot": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
            "p": str(order.price),
            "q": str(order.amount),
            "s": "Bid" if order.trade_type == TradeType.BUY else "Ask",
            "sid": int(self.expected_fill_trade_id),
            "st": "CANCELLED",
            "t": 160001112.223,
            "u": "",
        }

    @staticmethod
    def _callback_wrapper_with_response(callback: Callable, response: Any, *args, **kwargs):
        callback(args, kwargs)
        if isinstance(response, Exception):
            raise response
        else:
            return response

    def _exchange_order_id(self, order_number: int) -> str:
        template_exchange_id = self.expected_exchange_order_id
        digits = len(str(order_number))
        prefix = template_exchange_id[:-digits]
        return f"{prefix}{order_number}"