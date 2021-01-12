#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-

import logging
import warnings
from datetime import datetime
from decimal import Decimal
from queue import Queue, Empty
from uuid import uuid4

import quickfix as fx
import quickfix44 as fxg

from typing import Dict, Optional, Any, List, Union, Type

from src.xnt.models.fix_api_models import OrderStatus, DataType, Status, Reject, BusinessReject, MDSnapshot, MDReject, \
    ExecutionReport, OrderCancelReject, AccSumResponse, AccSumRej, SecurityList, TradeCaptureAck, TradeCapture, \
    TradeMargin, TradeMarginReject, MDEntryType, OrdType, Side, CFICode, TradeDate, Durations


def tostr(message: fx.Message) -> str:
    return message.toString().replace("\x01", "|")


class OrderSeq:
    def __init__(self):
        self.seq = []  # type: List[str]
        self.queue = Queue(maxsize=0)
        self.status = OrderStatus.NEW  # type: OrderStatus
        self.exante_id = None

    def get(self):
        try:
            return self.queue.get(block=False)
        except Empty:
            return None

    def put(self, item: ExecutionReport) -> None:
        self.seq.append(item.ClOrdID)
        self.queue.put(item)

    def qsize(self) -> int:
        return self.queue.qsize()

    def __repr__(self):
        return f"ClOrdId sequence: {','.join(self.seq)}\n status: {self.status.name}\n ExanteID: {self.exante_id}"


class MDSub(Queue):
    def put(self, item: Any, block: bool = False, timeout: int = None) -> None:
        """
        overloading base method to drop first value on reaching maxsize.
        """
        with self.not_full:
            if self.maxsize > 0:
                if self._qsize() >= self.maxsize:
                    self._get()
            self._put(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()


class Collector(object):
    def __init__(self, md_queue_lenght: int = 20) -> None:
        self._md_queue_l = md_queue_lenght
        self._ord_map = dict()
        self.rejects = Queue(maxsize=0)

    def register(self, name: str, obj_type: DataType) -> None:
        if obj_type == DataType.MD:
            setattr(self, name, MDSub(maxsize=self._md_queue_l))
        elif obj_type == DataType.Order:
            setattr(self, name, OrderSeq())
        elif obj_type in (DataType.AccSum, DataType.SecList, DataType.TradesList, DataType.MarginList):
            setattr(self, name, Queue(maxsize=0))

    def bound_cl_ord_id(self, name: str, ex_ord_id: Optional[str] = None) -> None:
        if name not in self._ord_map or ex_ord_id:
            self._ord_map[name] = ex_ord_id

    def deregister(self, name: str) -> None:
        try:
            if name in self._ord_map:
                ex_oid = self._ord_map[name]
                for k, v in self._ord_map.items():
                    if v == ex_oid:
                        self._ord_map.pop(k)
                delattr(self, ex_oid)
            elif not name.startswith('_') and not callable(name):
                delattr(self, name)
        except AttributeError:
            pass

    def get(self, name: str) -> Union[None, MDSub, OrderSeq]:
        try:
            if name in self._ord_map:
                return getattr(self, self._ord_map[name])
            return getattr(self, name)
        except AttributeError:
            return None

    def has(self, name: str) -> bool:
        return hasattr(self, name)

    @property
    def listall(self) -> Dict[str, Type]:
        return {k: v for k, v in self.__dict__.items() if (not callable(k) and not k.startswith('_'))}

    @property
    def status(self) -> str:
        return ''.join([f"Object '{k}', type of {type(v)} with length {v.qsize()}\n" for k, v in self.listall.items()])


class FixAdapter(fx.Application):
    """
    We do not need hard tracking of MesSeqNum here :thinking:
    """

    def __init__(self, session: Type[fx.Session], session_settings: fx.SessionSettings,
                 logger: Optional[logging.Logger] = None, collector: Collector = None) -> None:
        super(FixAdapter, self).__init__()
        self.session = session
        self.settings = session_settings
        self.logger = logger or logging.Logger(name="FIX", level=logging.DEBUG)
        self.status = dict()  # type: Dict[str, Status]
        self.collector = collector or Collector()

    def _iscon(self, session_id: fx.SessionID) -> bool:
        if session_id:
            status = self.session.lookupSession(session_id)
            if status:
                return status.isLoggedOn()
        return False

    def _set_header(self, message: fx.Message, msg_type: Any) -> None:
        message.getHeader().setField(fx.BeginString(fx.BeginString_FIX44))
        message.getHeader().setField(fx.MsgType(msg_type))

    def _set_instr(self, message: fx.Message, symbol: str) -> None:
        message.setField(fx.Symbol(symbol))
        message.setField(fx.SecurityID(symbol))
        message.setField(fx.SecurityIDSource("111"))

    def onCreate(self, session_id: fx.SessionID) -> None:
        self.logger.debug(f"Created session {session_id.toString()}")
        stat = Status(session_id)
        self.status[stat.uid] = stat

    def onLogon(self, session_id: fx.SessionID):
        """
        CONN EST
        """
        self.logger.info(f"Logon for {session_id.toString()} received")
        self.status[session_id.toString()].login()

    def onLogout(self, session_id: fx.SessionID):
        """
        CONN BREAK
        """
        self.logger.info(f"Logout for {session_id.toString()} received")
        self.status[session_id.toString()].logout

    def toAdmin(self, message: fx.Message, session_id: fx.SessionID) -> None:
        """
        ENGINE -> CP
        """
        msg_type = message.getHeader().getField(35)
        if msg_type == "A":
            message.setField(fx.Password(self.settings.get(session_id).getString("Password")))
            try:
                message.setField(fx.BoolField(10001, self.settings.get(session_id).getString("CancelOnDisconnect")))
            except fx.ConfigError:
                pass
        elif self._iscon(session_id):
            if msg_type == "0":
                self.logger.debug(f"Heartbeat MesSeqNum {message.getHeader().getField(34)}")
            else:
                self.logger.info(f"> {tostr(message)}")
        else:
            self.logger.error(f"Session {session_id.toString()} not connected while trying sent {tostr(message)}")

    def fromAdmin(self, message: fx.Message, session_id: fx.SessionID):
        """
        CP -> ENGINE
        """
        if self._iscon(session_id):
            msg_type = message.getHeader().getField(35)
            if msg_type == "0":
                self.logger.debug(f"Heartbeat received {message.getHeader().getField(34)}")
            else:
                self.logger.info(f"< {tostr(message)}")

    def toApp(self, message: fx.Message, session_id: fx.SessionID):
        """
        APP -> ENGINE
        """
        pass

    def fromApp(self, message: fx.Message, session_id: fx.SessionID):
        """
        ENGINE -> APP
        """
        if self._iscon(session_id):
            msg_type = message.getHeader().getField(35)
            if msg_type == "3":
                self.collector.rejects.put(Reject(message))
                warnings.warn(f"Received reject {tostr(message)}")
            elif msg_type == "j":
                self.collector.rejects.put(BusinessReject(message))
                warnings.warn(f"Received reject {tostr(message)}")
            elif msg_type == "W":
                self.collector.get(message.getField(262)).put(MDSnapshot(message))
            elif msg_type == "Y":
                self.collector.get(message.getField(262)).put(MDReject(message))
            elif msg_type in ("8", "9"):
                if msg_type == "8":
                    t = ExecutionReport(message)
                else:
                    t = OrderCancelReject(message)
                self.collector.bound_cl_ord_id(t.ClOrdID, t.OrderID)
                if not self.collector.has(t.OrderID):
                    self.collector.register(t.OrderID, DataType.Order)
                self.collector.get(t.OrderID).put(t)
                self.collector.get(t.OrderID).status = t.OrdStatus
                self.collector.get(t.OrderID).exante_id = t.OrderID
            elif msg_type == "UASR":
                self.collector.get(message.getField(20020)).put(AccSumResponse(message))
            elif msg_type == "UASJ":
                self.collector.get(message.getField(20020)).put(AccSumRej(message))
            elif msg_type == "y":
                self.collector.get(message.getField(320)).put(SecurityList(message))
            elif msg_type == "AQ":
                self.collector.get(message.getField(568)).put(TradeCaptureAck(message))
            elif msg_type == "AE":
                self.collector.get(message.getField(568)).put(TradeCapture(message))
            elif msg_type == "UTMR":
                self.collector.get(message.getField(20050)).put(TradeMargin(message))
            elif msg_type == "UTMJ":
                self.collector.get(message.getField(20050)).put(TradeMarginReject(message))
            else:
                warnings.warn(f"Received unknown message type {msg_type} {tostr(message)}")

    def logon_req(self, session_id: fx.SessionID, reset_mes_seq_num: bool = False,
                  cancel_on_disconnect: bool = False, pwd: str = None) -> None:
        # if self._iscon(session_id):
        msg = fx.Message()
        self._set_header(msg, fx.MsgType_Logon)
        msg.setField(fx.StringField(554, pwd))
        msg.setField(fx.ResetSeqNumFlag(reset_mes_seq_num))
        if cancel_on_disconnect:
            msg.setField(fx.BoolField(10001, True))
        fx.Session.sendToTarget(msg, session_id)

    def logout_req(self, session_id: fx.SessionID, reason: Optional[str] = None) -> None:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_Logout)
            if reason:
                msg.setField(fx.Text(fx.StringField(reason)))
            fx.Session.sendToTarget(msg, session_id)

    def resend_req(self, session_id: fx.SessionID, begin_seq_no: int, end_seq_no: int) -> None:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_ResendRequest)
            msg.setField(fx.BeginSeqNo(begin_seq_no))
            msg.setField(fx.EndSeqNo(end_seq_no))
            fx.Session.sendToTarget(msg, session_id)

    def test_req(self, session_id: fx.SessionID, test_req_id: Any) -> None:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_TestRequest)
            msg.setField(fx.TestReqID(str(test_req_id)))
            fx.Session.sendToTarget(msg, session_id)

    def md_req(self, session_id: fx.SessionID, symbol: str, md_type: List[MDEntryType], md_req_id: Optional[str] = None,
               sub: bool = True, md_depth: int = 1) -> Optional[str]:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_MarketDataRequest)
            # self._set_instr(msg, symbol)
            group = fxg.MarketDataRequest.NoRelatedSym()
            group.setField(fx.Symbol(symbol))
            group.setField(fx.SecurityID(symbol))
            group.setField(fx.SecurityIDSource("111"))
            msg.addGroup(group)
            if not md_req_id:
                md_req_id = str(uuid4().hex)
            if sub:
                msg.setField(fx.SubscriptionRequestType(fx.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES))
                msg.setField(fx.MDUpdateType(fx.MDUpdateType_FULL_REFRESH))
                self.collector.register(md_req_id, DataType.MD)
            else:
                msg.setField(fx.SubscriptionRequestType(
                    fx.SubscriptionRequestType_DISABLE_PREVIOUS_SNAPSHOT_PLUS_UPDATE_REQUEST))
                self.collector.deregister(md_req_id)
            msg.setField(fx.MDReqID(md_req_id))
            msg.setField(fx.MarketDepth(md_depth))
            msg.setField(fx.NoMDEntryTypes(len(md_type)))
            for md_entry in md_type:
                group = fxg.MarketDataRequest().NoMDEntryTypes()
                group.setField(fx.MDEntryType(md_entry.value))
                msg.addGroup(group)
            fx.Session.sendToTarget(msg, session_id)
            return md_req_id

    def new_order_req(self, session_id: fx.SessionID, symbol: str, side: Side, duration: Durations, quantity: Decimal,
                      order_type: OrdType, price: Optional[Decimal] = None, stop_price: Optional[Decimal] = None,
                      account: Optional[str] = None, cod: bool = False,
                      client_order_id: Optional[str] = None) -> Optional[str]:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_NewOrderSingle)
            if account:
                msg.setField(fx.Account(account))
            self._set_instr(msg, symbol)
            if not client_order_id:
                client_order_id = str(uuid4().hex)
            msg.setField(fx.ClOrdID(client_order_id))
            msg.setField(fx.Side(side.value))
            msg.setField(fx.TransactTime(int(datetime.now().timestamp())))
            msg.setField(fx.OrderQty(float(quantity)))
            msg.setField(fx.OrdType(order_type.value))
            if order_type in (OrdType.LIMIT, OrdType.STOP_LIMIT) and price:
                msg.setField(fx.Price(float(price)))
            if order_type in (OrdType.STOP, OrdType.STOP_LIMIT) and stop_price:
                msg.setField(fx.StopPx(float(stop_price)))
            msg.setField(fx.TimeInForce(duration.value))
            if cod:
                msg.setField(fx.BoolField(10001, 'Y'))
            fx.Session.sendToTarget(msg, session_id)
            self.collector.bound_cl_ord_id(client_order_id)
            return client_order_id

    def cancel_req(self, session_id: fx.SessionID, orig_client_order_id: str, symbol: str, side: Side,
                   quantity: Decimal, client_order_id: Optional[str] = None) -> Optional[str]:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_OrderCancelRequest)
            self._set_instr(msg, symbol)
            msg.setField(fx.Side(side.value))
            msg.setField(fx.TransactTime(int(datetime.now().timestamp())))
            msg.setField(fx.OrigClOrdID(orig_client_order_id))
            msg.setField(fx.OrderQty(float(quantity)))
            if not client_order_id:
                client_order_id = str(uuid4().hex)
            msg.setField(fx.ClOrdID(client_order_id))
            fx.Session.sendToTarget(msg, session_id)
            self.collector.bound_cl_ord_id(client_order_id)
            return client_order_id

    def order_status_req(self, session_id: fx.SessionID, client_order_id: str, symbol: str, side: Side) -> None:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_OrderStatusRequest)
            self._set_instr(msg, symbol)
            msg.setField(fx.ClOrdID(client_order_id))
            msg.setField(fx.Side(side.value))
            fx.Session.sendToTarget(msg, session_id)
            self.collector.bound_cl_ord_id(client_order_id)

    def order_replace_req(self, session_id: fx.SessionID, orig_client_order_id: str, symbol: str, side: Side,
                          order_type: OrdType,
                          quantity: Decimal, price: Optional[Decimal] = None, stop_price: Optional[Decimal] = None,
                          client_order_id: Optional[str] = None) -> Optional[str]:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_OrderCancelReplaceRequest)
            self._set_instr(msg, symbol)
            if not client_order_id:
                client_order_id = str(uuid4().hex)
            msg.setField(fx.ClOrdID(client_order_id))
            msg.setField(fx.OrigClOrdID(orig_client_order_id))
            msg.setField(fx.Side(side.value))
            msg.setField(fx.TransactTime(int(datetime.now().timestamp())))
            msg.setField(fx.OrderQty(float(quantity)))
            msg.setField(fx.OrdType(order_type.value))
            if order_type in (OrdType.LIMIT, OrdType.STOP_LIMIT):
                msg.setField(fx.Price(float(price)))
            if order_type in (OrdType.STOP, OrdType.STOP_LIMIT):
                msg.setField(fx.StopPx(float(stop_price)))
            fx.Session.sendToTarget(msg, session_id)
            self.collector.bound_cl_ord_id(client_order_id)
            return client_order_id

    def account_summary_req(self, session_id: fx.SessionID, account: Optional[str] = None,
                            currency: Optional[str] = None, acc_sum_id: Optional[int] = None) -> Optional[str]:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, 'UASQ')
            if not acc_sum_id:
                acc_sum_id = int(datetime.now().timestamp())
            msg.setField(fx.IntField(20020, acc_sum_id))
            if account:
                msg.setField(fx.Account(account))
            if currency:
                msg.setField(fx.StringField(20023, currency))
            fx.Session.sendToTarget(msg, session_id)
            self.collector.register(str(acc_sum_id), DataType.AccSum)
            return str(acc_sum_id)

    def order_mass_status_req(self, session_id: fx.SessionID, mosr_id: Optional[str] = None) -> Optional[str]:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_OrderMassStatusRequest)
            if not mosr_id:
                mosr_id = str(uuid4().hex)
            msg.setField(fx.MassStatusReqID(mosr_id))
            msg.setField(fx.MassStatusReqType(7))
            fx.Session.sendToTarget(msg, session_id)
            return mosr_id

    def security_list_req(self, session_id: fx.SessionID, sym_substring: Optional[str] = None,
                          cfi_code: Optional[CFICode] = None, sec_list_req_id: Optional[str] = None) -> Optional[str]:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_SecurityListRequest)
            if not sec_list_req_id:
                sec_list_req_id = str(uuid4().hex)
            msg.setField(fx.SecurityReqID(sec_list_req_id))
            if sym_substring:
                msg.setField(fx.SecurityListRequestType(0))
                msg.setField(fx.Symbol(sym_substring))
            elif cfi_code:
                msg.setField(fx.SecurityListRequestType(1))
                msg.setField(fx.CFICode(cfi_code.value))
            else:
                msg.setField(fx.SecurityListRequestType(4))
            fx.Session.sendToTarget(msg, session_id)
            self.collector.register(sec_list_req_id, DataType.SecList)
            return sec_list_req_id

    def trades_capture_req(self, session_id: fx.SessionID, start_date: datetime, stop_date: Optional[datetime] = None,
                           trade_req_id: Optional[str] = None) -> Optional[str]:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, fx.MsgType_TradeCaptureReportRequest)
            if not trade_req_id:
                trade_req_id = str(uuid4().hex)
            msg.setField(fx.TradeRequestID(trade_req_id))
            msg.setField(fx.TradeRequestType(0))
            msg.setField(fx.NoDates(2 if stop_date else 1))
            group = TradeDate()
            group.setField(fx.TradeDate(start_date.strftime("%Y%m%d")))
            msg.addGroup(group)
            if stop_date:
                group = TradeDate()
                group.setField(fx.TradeDate(stop_date.strftime("%Y%m%d")))
                msg.addGroup(group)
            fx.Session.sendToTarget(msg, session_id)
            self.collector.register(trade_req_id, DataType.TradesList)
            return trade_req_id

    def trades_margin_req(self, session_id: fx.SessionID, account: str, symbol: str, currency: str, quantity: Decimal,
                          price: Decimal, trade_margin_id: Optional[str] = None) -> Optional[str]:
        if self._iscon(session_id):
            msg = fx.Message()
            self._set_header(msg, 'UTMQ')
            self._set_instr(msg, symbol)
            if not trade_margin_id:
                trade_margin_id = str(uuid4().hex)
            msg.setField(fx.StringField(20050, trade_margin_id))
            msg.setField(fx.Account(account))
            msg.setField(fx.Currency(currency))
            msg.setField(fx.Quantity(float(quantity)))
            if price:
                msg.setField(fx.Price(float(price)))
            fx.Session.sendToTarget(msg, session_id)
            self.collector.register(trade_margin_id, DataType.MarginList)
            return trade_margin_id
