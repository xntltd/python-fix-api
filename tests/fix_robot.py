#!/usr/bin/env python3.7

import logging
import os
import quickfix
from configparser import ConfigParser, SectionProxy
from dataclasses import dataclass
from decimal import Decimal
from queue import Empty
from threading import Thread
from typing import Dict, Optional, Union

from xnt.fix_api import Collector, FixAdapter
from xnt.models.fix_api_models import Side, Durations, OrdType, MDEntryType, AccSumResponse, AccSumRej, \
    MDSnapshot, OrderStatus


def mk_logger(dir_path: str, level: str) -> logging.Logger:
    log_handler = logging.FileHandler(os.path.join(dir_path, 'robot.log'), mode='a')
    log_handler.setFormatter(logging.Formatter('[%(asctime)s][%(processName)s]%(message)s'))

    log = logging.getLogger('default')  # type: logging.Logger
    log.setLevel(getattr(logging, level))
    log.addHandler(log_handler)
    return log


def get_side_price(q: Union[MDSnapshot, Decimal], pos: Decimal, r: Optional[Decimal] = None) -> Decimal:
    if hasattr(q, "__model__"):
        if pos > 0:
            md_type = MDEntryType.Bid
        else:
            md_type = MDEntryType.Offer
        for side in q.MDEntry:
            if side.MDEntryType == md_type:
                p = side.MDEntryPx
                break
    else:
        p = q

    if r and pos > 0:
        return p - r
    elif r and pos < 0:
        return p + r
    else:
        return p


def load_config() -> ConfigParser:
    c = ConfigParser()
    c["DEFAULT"] = {
        "logdir": "/var/log/robot/",
        "loglevel": "DEBUG"
    }
    c["TRADER"] = {
        "account": "WWB1220.001",
        "symbols": "AAPL.NASDAQ,AAL.NASDAQ",
        "range": "0.1",
        "size": "100",
        "maxSize": "0",
        "keepStartPrice": False
    }
    return c


@dataclass
class State:
    position: Decimal
    last: Union[MDSnapshot, Decimal]
    md_id: str
    order: Optional[str] = None

    @property
    def price(self) -> Decimal:
        if isinstance(self.last, Decimal):
            return self.last
        else:
            return get_side_price(self.last, self.position)


class FeedHandler(Thread):
    def __init__(self, client: FixAdapter, cfg: SectionProxy):
        self.client = client
        for s in self.client.status.values():
            if "FEED" in s.uid:
                self.fs = s
            if "TRADE" in s.uid:
                self.bs = s
        self.collector = client.collector
        self.range = Decimal(cfg["range"])
        self.account = cfg["account"]
        self.ord_quantity = Decimal(cfg["size"])
        self.keepStartPrice = cfg.getboolean("keepStartPrice")
        self.state = {k: None for k in cfg["symbols"].split(",")}  # type: Dict[str, Optional[State]]
        super().__init__(name="feed_handler", daemon=True)

    def run(self):
        self.init_state()
        while self.fs.logened and self.bs.logened:
            for s, state in self.state.items():
                try:
                    quote = self.collector.get(state.md_id).get(False)
                    if quote:
                        q = get_side_price(quote, self.state[s].position)
                        if abs(self.state[s].price - q) > self.range and self.state[s].position != 0:
                            if self.state[s].order:
                                state.order = self.client.order_replace_req(
                                    self.bs.ses, state.order, s, Side.BUY if state.position < 0 else Side.SELL,
                                    OrdType.LIMIT, self.ord_quantity, get_side_price(q, state.position, self.range))
                            else:
                                # order are not placed yet or wiped
                                state.order = self.client.new_order_req(
                                    self.bs.ses, s, Side.BUY if self.state[s].position < 0 else Side.SELL,
                                    Durations.DAY, self.ord_quantity, OrdType.LIMIT,
                                    get_side_price(q, state.position, self.range)
                                )
                            if not self.keepStartPrice:
                                self.state[s].last = quote
                        else:
                            self.client.logger.debug(f"not going to place order because {abs(self.state[s].price - q)} is less than {self.range}")
                except Empty:
                    continue
                q = self.collector.get(state.order)
                if q.status in (OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.FILLED):
                    state.order = None
                    self.collector.deregister(state.order)
                    if state.position < 0:
                        state.position += self.ord_quantity
                    else:
                        state.position -= self.ord_quantity

    def init_state(self):
        acc_sum_id = self.client.account_summary_req(self.bs.ses, self.account)
        q = self.collector.get(acc_sum_id)
        while not q.empty():
            p = q.get()  # type: Union[AccSumResponse, AccSumRej]
            if isinstance(p, AccSumResponse) and p.Instrument.SecurityID in self.state:
                md_id = self.client.md_req(self.fs.ses, p.Instrument.SecurityID, [MDEntryType.Bid, MDEntryType.Offer])
                self.state[p.Instrument.SecurityID] = State(p.LongQty or -p.ShortQty, p.AvgPx, md_id)


if __name__ == "__main__":
    config = load_config()
    settings = quickfix.SessionSettings('../src/config/settings.conf')
    app = FixAdapter(quickfix.Session, settings, collector=Collector(1))
    # noinspection PyUnresolvedReferences
    store = quickfix.FileStorageFactory(settings)
    logs = quickfix.FileLogFactory(settings)
    initiator = quickfix.SocketInitiator(app, store, settings, logs)
    collector = app.collector

    fh = FeedHandler(app, config["TRADER"])
    fh.start()
    fh.join()
