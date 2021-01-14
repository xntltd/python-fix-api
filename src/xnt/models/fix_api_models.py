#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-

import quickfix as fx
import quickfix44 as fxg

from datetime import datetime
from decimal import Decimal
from enum import Enum, auto
from quickfix import IntArray, Group, SessionID
from threading import Event
from typing import Union
from xnt.models.json_to_obj import FIXMessage


class SType(Enum):
    FEED = "FEED"
    TRADE = "TRADE"


class MDEntryType(Enum):
    Bid = "0"
    Offer = "1"
    Trade = "2"
    Open_price = "4"
    Close_price = "5"
    Trade_volume = "B"
    Limit_low = "x"
    Limit_high = "y"
    Option_data = "z"


class CFICode(Enum):
    FOREX = "MRCXXX"
    Stock = "EXXXXX"
    Fund = "EUXXXX"
    Bond = "DBXXXX"
    Future = "FXXXXX"
    OptionC = "OCXXXX"
    OptionP = "OPXXXX"
    CSpread = "FMXXXX"


class Side(Enum):
    BUY = "1"
    SELL = "2"


class Durations(Enum):
    DAY = "0"
    GTC = "1"
    ATO = "2"
    IOC = "3"
    FOK = "4"
    # GTD = 6
    ATC = "7"


class OrdType(Enum):
    MARKET = "1"
    LIMIT = "2"
    STOP = "3"
    STOP_LIMIT = "4"
    # ICEBERG = ?
    # TRAILING_STOP = ?
    # TWAP = ?


class ExecType(Enum):
    PEND_NEW = "A"
    NEW = "0"
    CANCELLED = "4"
    PEND_CANCEL = "6"
    REJECTED = "8"
    TRADE = "F"
    ORD_STATUS = "I"


class OrderStatus(Enum):
    NEW = "0"
    PART_FILLED = "1"
    FILLED = "2"
    CANCELLED = "4"
    PEND_CANCEL = "6"
    REJECTED = "8"
    PEND_NEW = "A"


class InstrAttribType(Enum):
    FEED_MPI = "500"
    INITIAL_MARGIN = "501"
    MAINTENANCE_MARGIN = "502"
    ORDER_MPI = "503"
    LOT_SIZE = "504"
    EXPIRY = "505"


class OrdRejReason(Enum):
    UNKNOWN_SYM = "1"
    LIMIT_EXCEEDED = "3"
    UNKNOWN_ORD = "5"
    DUPLICATE_ORDER = "6"
    OTHER = "99"


class AccSumRejReason(Enum):
    FAILED = "1"
    EMPTY = "2"
    NO_PERMS = "3"


class SecurityReqResult(Enum):
    VALID = "0"
    INVALID_REQ = "1"
    NO_MATCH = "2"
    NOT_AUTHORIZED = "3"
    UNAVAILABLE = "4"
    NOT_SUPPORTED = "5"


class TradeRequestResult(Enum):
    SUCCESS = "0"
    NOT_SUPPORTED = "8"
    UNAUTHORIZED = "9"
    OTHER = "99"


class TradeRequestStatus(Enum):
    ACCEPTED = "0"
    COMPLETED = "1"
    REJECTED = "2"


class TradeMarginRejReason(Enum):
    ERROR = "1"
    INVALID_INSTR = "2"
    NO_PERMS = "3"


class DataType(Enum):
    MD = auto()
    Order = auto()
    AccSum = auto()
    SecList = auto()
    TradesList = auto()
    MarginList = auto()


class TradeDate(Group):
    def __init__(self) -> None:
        order = IntArray(2)
        order[0] = 75
        order[1] = 0
        Group.__init__(self, 580, 75, order)


class Status:
    def __init__(self, session_id: SessionID) -> None:
        self.stat = Event()  # type: Event
        self.ses = session_id  # type: SessionID

    def login(self) -> None:
        self.stat.set()

    def logout(self) -> None:
        self.stat.clear()

    @property
    def logened(self) -> bool:
        return self.stat.isSet()

    @property
    def uid(self) -> str:
        return self.ses.toString()

    def __repr__(self) -> str:
        return f"Session {self.uid} is {'' if self.logened else 'not'} logened"


def get_bool(s: str) -> bool:
    if s == "Y":
        return True
    elif s == "N":
        return False
    else:
        raise ValueError(f"String {s} is not boolean type")


def get_dt(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y%m%d-%H:%M:%S.%f")
    except ValueError:
        return datetime.strptime(s.split('.')[0], "%Y%m%d-%H:%M:%S")


class Header(FIXMessage):
    def __init__(self, message: fx.Header) -> None:
        self.SenderCompID = message.getField(49)
        self.TargetCompID = message.getField(56)
        self.SendingTime = message.getField(52)
        self.MesSeqNum = int(message.getField(34))


class Instrument(FIXMessage):
    def __init__(self, message: Union[fx.Message, fx.Group]) -> None:
        self.Symbol = message.getField(55)
        self.SecurityID = message.getField(48)
        self.SecurityIDSource = message.getField(22)
        self.CFICode = CFICode(message.getField(461)) if message.getFieldIfSet(fx.CFICode()) else None
        self.MaturityMonthYear = message.getField(200) if message.getFieldIfSet(fx.MaturityMonthYear()) else None
        self.StrikePrice = message.getField(202) if message.getFieldIfSet(fx.StrikePrice()) else None
        self.SecurityExchange = message.getField(207) if message.getFieldIfSet(fx.SecurityExchange()) else None


class Reject(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.RefSeqNum = message.getField(45)
        self.RefTagID = int(message.getField(371)) if message.getFieldIfSet(fx.RefTagID()) else None
        self.RefMsgType = message.getField(372) if message.getFieldIfSet(fx.RefMsgType()) else None
        self.SessionRejectReason = message.getField(373) if message.getFieldIfSet(fx.SessionRejectReason()) else None
        self.Text = message.getField(58) if message.getFieldIfSet(fx.Text()) else None


class BusinessReject(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.RefSeqNum = int(message.getField(45))
        self.RefMsgType = message.getField(372)
        self.BusinessRejectReason = message.getField(380)
        self.Text = message.getField(58) if message.getFieldIfSet(fx.Text()) else None


class MDReject(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.MDReqID = message.getField(262)
        self.MDReqRejReason = message.getField(281) if message.getFieldIfSet(fx.MDReqRejReason()) else None
        self.Text = message.getField(58) if message.getFieldIfSet(fx.Text()) else None


class MDSnapshot(FIXMessage):
    class _MDEntry(FIXMessage):
        def __init__(self, idx: int, message: fx.Message) -> None:
            group = fxg.MarketDataSnapshotFullRefresh.NoMDEntries()
            message.getGroup(idx, group)
            self.MDEntryType = MDEntryType(group.getField(269))
            self.MDEntryPx = Decimal(group.getField(270))
            self.MDEntrySize = Decimal(group.getField(271))
            self.MDEntryDate = group.getField(272) if group.getFieldIfSet(fx.MDEntryDate()) else None
            self.MDEntryTime = group.getField(273) if group.getFieldIfSet(fx.MDEntryTime()) else None
            self.OptionImpliedVolatility = Decimal(group.getField(20060)) if \
                group.getFieldIfSet(fx.StringField(20060)) else None
            self.OptionDelta = Decimal(group.getField(20061)) if \
                group.getFieldIfSet(fx.StringField(20061)) else None
            self.OptionVega = Decimal(group.getField(20062)) if \
                group.getFieldIfSet(fx.StringField(20062)) else None
            self.OptionTheta = Decimal(group.getField(20063)) if \
                group.getFieldIfSet(fx.StringField(20063)) else None
            self.OptionGamma = Decimal(group.getField(20064)) if \
                group.getFieldIfSet(fx.StringField(20064)) else None
            self.OptionTheoreticalPrice = Decimal(group.getField(20065)) if \
                group.getFieldIfSet(fx.StringField(20065)) else None

    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.MDReqID = message.getField(262)
        self.Symbol = message.getField(55)
        self.NoMDEntries = int(message.getField(268))
        self.MDEntry = [self._MDEntry(i + 1, message) for i in range(self.NoMDEntries)]


class ExecutionReport(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.ClOrdID = message.getField(11)
        self.OrigClOrdID = message.getField(41) if message.getFieldIfSet(fx.OrigClOrdID()) else None
        self.OrderID = message.getField(37)
        self.ExecID = message.getField(17)
        self.ExecType = ExecType(message.getField(150))
        self.OrdStatus = OrderStatus(message.getField(39))
        self.Account = message.getField(1) if message.getFieldIfSet(fx.Account()) else None
        self.Instrument = Instrument(message)
        self.Side = Side(message.getField(54))
        self.Duration = Durations(message.getField(59))
        self.TransactTime = get_dt(message.getField(60)) if message.getFieldIfSet(fx.TransactTime()) else None
        self.LeavesQty = Decimal(message.getField(151))
        self.CumQty = Decimal(message.getField(14))
        self.AvgPx = Decimal(message.getField(6))
        self.LastQty = Decimal(message.getField(32)) if message.getFieldIfSet(fx.LastQty()) else None
        self.LastPx = Decimal(message.getField(31)) if message.getFieldIfSet(fx.LastPx()) else None
        self.OrderQty = Decimal(message.getField(38))
        self.OrdType = OrdType(message.getField(40))
        self.Price = Decimal(message.getField(44)) if message.getFieldIfSet(fx.Price()) else None
        self.StopPx = Decimal(message.getField(99)) if message.getFieldIfSet(fx.StopPx()) else None
        self.OrdRejReason = OrdRejReason(message.getField(103)) if message.getFieldIfSet(fx.OrdRejReason()) else None
        self.Text = message.getField(58) if message.getFieldIfSet(fx.Text()) else None
        self.MassStatusReqID = message.getField(584) if message.getFieldIfSet(fx.MassStatusReqID()) else None
        self.LastRptRequested = message.getField(912) if message.getFieldIfSet(fx.LastRptRequested()) else None


class OrderCancelReject(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.ClOrdID = message.getField(11)
        self.OrigClOrdID = message.getField(41)
        self.OrderID = message.getField(37)
        self.OrdStatus = OrderStatus(message.getField(39))
        self.CxlRejResponseTo = message.getField(434)
        self.CxlRejReason = message.getField(102) if message.getFieldIfSet(fx.CxlRejReason()) else None
        self.Text = message.getField(58) if message.getFieldIfSet(fx.Text()) else None


class AccSumResponse(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.AccSumReqID = message.getField(20020)
        self.Account = message.getField(1)
        self.AccSumCurrency = message.getField(20023)
        self.TotalNetValue = Decimal(message.getField(900)) if message.getFieldIfSet(fx.TotalNetValue()) else None
        self.UsedMargin = Decimal(message.getField(20040)) if message.getFieldIfSet(fx.DoubleField(20040)) else None
        self.NumAccSumReports = int(message.getField(20021))
        self.Instrument = Instrument(message)
        self.LongQty = Decimal(message.getField(704))
        self.ShortQty = Decimal(message.getField(705))
        self.AvgPx = Decimal(message.getField(6)) if message.getFieldIfSet(fx.AvgPx()) else None
        self.ProfitAndLoss = Decimal(message.getField(20030)) if message.getFieldIfSet(fx.DoubleField(20030)) else None
        self.ConvertedProfitAndLoss = Decimal(message.getField(20031)) if \
            message.getFieldIfSet(fx.DoubleField(20031)) else None
        self.Value = Decimal(message.getField(20032)) if message.getFieldIfSet(fx.DoubleField(20032)) else None
        self.ConvertedValue = Decimal(message.getField(20033)) if message.getFieldIfSet(fx.DoubleField(20033)) else None


class AccSumRej(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.AccSumReqID = message.getField(20020)
        self.Account = message.getField(1)
        self.Text = message.getField(58)
        self.AccSumRejReason = AccSumRejReason(message.getField(20022))


class SecurityList(FIXMessage):
    class _SLSymbol(FIXMessage):
        class _InstrAttrib(FIXMessage):
            def __init__(self, idx: int, message: fx.Group) -> None:
                group = fxg.SecurityDefinition.NoInstrAttrib()
                message.getGroup(idx, group)
                self.InstrAttribType = InstrAttribType(group.getField(871)) if \
                    group.getFieldIfSet(fx.InstrAttribType()) else None
                self.InstrAttribValue = Decimal(group.getField(872)) if \
                    group.getFieldIfSet(fx.InstrAttribValue()) else None

        class _Leg(FIXMessage):
            def __init__(self, idx: int, message: fx.Group) -> None:
                group = fxg.SecurityDefinition.NoLegs()
                message.getGroup(idx, group)
                self.LegSymbol = group.getField(600)
                self.LegCFICode = CFICode(group.getField(608)) if \
                    group.getFieldIfSet(fx.LegCFICode()) else None
                self.LegMaturityMonthYear = group.getField(610) if \
                    group.getFieldIfSet(fx.LegMaturityMonthYear()) else None
                self.LegSecurityExchange = group.getField(616) if \
                    group.getFieldIfSet(fx.LegSecurityExchange()) else None

        class _Underlying(FIXMessage):
            def __init__(self, idx: int, message: fx.Group) -> None:
                group = fxg.SecurityDefinition.NoUnderlyings()
                message.getGroup(idx, group)
                self.UnderlyingSymbol = group.getField(311) if group.getFieldIfSet(fx.UnderlyingSymbol()) else None
                self.UnderlyingSecurityIDSource = group.getField(305) if \
                    group.getFieldIfSet(fx.UnderlyingSecurityIDSource()) else None
                self.UnderlyingSecurityID = group.getField(309) if \
                    group.getFieldIfSet(fx.UnderlyingSecurityID()) else None

        def __init__(self, idx: int, message: fx.Message) -> None:
            group = fxg.SecurityList.NoRelatedSym()
            message.getGroup(idx, group)
            self.Instrument = Instrument(group)
            self.SecurityDescription = group.getField(107)
            self.ContractMultiplier = Decimal(group.getField(231)) if \
                group.getFieldIfSet(fx.ContractMultiplier()) else None
            self.NoInstrAttrib = int(group.getField(870)) if group.getFieldIfSet(fx.NoInstrAttrib()) else 0
            self.Attributes = [self._InstrAttrib(i + 1, group) for i in range(self.NoInstrAttrib)]
            self.Currency = group.getField(15)
            self.NoLegs = int(group.getField(555)) if group.getFieldIfSet(fx.NoLegs()) else 0
            self.Legs = [self._Leg(i + 1, group) for i in range(self.NoLegs)]
            self.NoUnderlyings = int(group.getField(711)) if group.getFieldIfSet(fx.NoUnderlyings()) else 0
            self.Underlyings = [self._Underlying(i + 1, group) for i in range(self.NoUnderlyings)]

    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.SecurityReqID = message.getField(320)
        self.SecurityResponseID = message.getField(322) if message.getFieldIfSet(fx.SecurityResponseID()) else None
        self.TotNoRelatedSym = int(message.getField(393)) if message.getFieldIfSet(fx.TotNoRelatedSym()) else 0
        self.SecurityRequestResult = SecurityReqResult(message.getField(560))
        self.NoRelatedSym = int(message.getField(146)) if message.getFieldIfSet(fx.NoRelatedSym()) else 0
        self.SLSymbols = [self._SLSymbol(i + 1, message) for i in range(self.NoRelatedSym)]


class TradeCaptureAck(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.TradeRequestID = message.getField(568)
        self.TradeRequestType = message.getField(569)
        self.TotNumTradeReports = int(message.getField(748)) if message.getFieldIfSet(fx.TotNumTradeReports()) else None
        self.TradeRequestResult = TradeRequestResult(message.getField(749))
        self.TradeRequestStatus = TradeRequestStatus(message.getField(750))
        self.Text = message.getField(58) if message.getFieldIfSet(fx.Text()) else None


class TradeCapture(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.TradeRequestID = message.getField(568)
        self.PreviouslyReported = get_bool(message.getField(570))
        self.TotNumTradeReports = int(message.getField(748))
        self.Instrument = Instrument(message)
        self.LastPx = Decimal(message.getField(31))
        self.LastQty = Decimal(message.getField(32))
        self.TransactTime = get_dt(message.getField(60))
        self.TradeDate = message.getField(75)  # should be date(YYYY, MM, DD)
        self.ExecID = message.getField(17)
        self.TradeReportID = message.getField(571)
        group = fxg.TradeCaptureReport.NoSides()
        message.getGroup(1, group)
        self.Side = Side(group.getField(54))
        self.OrderID = group.getField(37)
        self.Account = group.getField(1)
        self.ProfitAndLoss = message.getField(20030)


class TradeMarginReject(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.TradeMarginReqID = message.getField(20050)
        self.TradeMarginReqRejReason = TradeMarginRejReason(message.getField(20051))
        self.Text = message.getField(58) if message.getFieldIfSet(fx.Text()) else None


class TradeMargin(FIXMessage):
    def __init__(self, message: fx.Message) -> None:
        self.Header = Header(message.getHeader())
        self.TradeMarginReqID = message.getField(20050)
        self.ExpectedMarginValue = Decimal(message.getField(20052))
        self.ExpectedMarginDelta = Decimal(message.getField(20053))
