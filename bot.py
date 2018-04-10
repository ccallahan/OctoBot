import logging
from logging.config import fileConfig

import ccxt
from botcore.config.config import load_config

from config.cst import *
from evaluator.evaluator_creator import EvaluatorCreator
from evaluator.evaluator_matrix import EvaluatorMatrix
from evaluator.evaluator_thread import EvaluatorThread
from tools import Notification
from trading import Exchange
from trading.trader.trader import Trader
from trading.trader.trader_simulator import TraderSimulator

"""
Main CryptoBot class:
- Create all indicators and thread for each cryptocurrencies in config
"""


class Crypto_Bot:
    """
    Constructor :
    - Load configs
    """
    def __init__(self):
        # Logger
        fileConfig('config/logging_config.ini')
        self.logger = logging.getLogger("CryptoBot")

        # Config
        self.logger.info("Load config file...")
        self.config = load_config()

        # TODO : CONFIG TEMP LOCATION
        self.time_frames = [TimeFrames.FIVE_MINUTES, TimeFrames.ONE_HOUR]
        self.exchanges = [ccxt.binance]

        # Notifier
        self.notifier = Notification(self.config)

        self.symbols_threads = []
        self.exchange_traders = {}
        self.exchange_trader_simulators = {}
        self.exchanges_list = {}

    # TODO : remove ? only for test purpose
    def set_time_frames(self, time_frames):
        self.time_frames = time_frames

    def create_exchange_traders(self):
        for exchange_type in self.exchanges:
            exchange_inst = Exchange(self.config, exchange_type)

            # create trader instance for this exchange
            exchange_trader = Trader(self.config, exchange_inst)
            exchange_trader_simulator = TraderSimulator(self.config, exchange_inst)

            self.exchanges_list[exchange_type.__name__] = exchange_inst
            self.exchange_traders[exchange_type.__name__] = exchange_trader
            self.exchange_trader_simulators[exchange_type.__name__] = exchange_trader_simulator

    def create_evaluation_threads(self):
        self.logger.info("Evaluation threads creation...")

        # create Social and TA evaluators
        for crypto_currency, symbol_list in self.config[CONFIG_CRYPTO_CURRENCIES].items():

            # create Social evaluators
            social_eval_list = EvaluatorCreator.create_social_eval(self.config, crypto_currency)

            # create symbol matrix
            matrix = EvaluatorMatrix()

            # create TA evaluators
            for symbol in symbol_list:

                for exchange_type in self.exchanges:
                    exchange = self.exchanges_list[exchange_type.__name__]

                    if exchange.enabled():

                        # Verify that symbol exists on this exchange
                        if exchange.symbol_exists(symbol):

                            # Create real time TA evaluators
                            real_time_TA_eval_list = EvaluatorCreator.create_real_time_TA_evals(self.config,
                                                                                                exchange,
                                                                                                symbol)

                            self.create_evaluator_threads(symbol,
                                                          matrix,
                                                          exchange,
                                                          social_eval_list,
                                                          real_time_TA_eval_list,
                                                          exchange_type)

                        # notify that exchange doesn't support this symbol
                        else:
                            self.logger.warning(exchange_type.__name__ + " doesn't support " + symbol)

    def create_evaluator_threads(self, symbol, matrix, exchange, social_eval_list, real_time_TA_eval_list, exchange_type):
        for time_frame in self.time_frames:
            if exchange.time_frame_exists(time_frame.value):
                self.symbols_threads.append(EvaluatorThread(self.config,
                                                            symbol,
                                                            time_frame,
                                                            matrix,
                                                            exchange,
                                                            self.notifier,
                                                            social_eval_list,
                                                            real_time_TA_eval_list,
                                                            self.exchange_traders[exchange_type.__name__],
                                                            self.exchange_trader_simulators[exchange_type.__name__]
                                                            ))

    def start_threads(self):
        for thread in self.symbols_threads:
            thread.start()
        self.logger.info("Evaluation threads started...")

    def join_threads(self):
        for thread in self.symbols_threads:
            thread.join()

        for trader in self.exchange_traders:
            self.exchange_traders[trader].stop_order_listeners()

        for trader_simulator in self.exchange_trader_simulators:
            self.exchange_trader_simulators[trader_simulator].stop_order_listeners()

    def stop_threads(self):
        self.logger.info("Stopping threads ...")
        for thread in self.symbols_threads:
            thread.stop()

        for trader in self.exchange_traders:
            self.exchange_traders[trader].stop_order_listeners()

        for trader_simulator in self.exchange_trader_simulators:
            self.exchange_trader_simulators[trader_simulator].stop_order_listeners()
