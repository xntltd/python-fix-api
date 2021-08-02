# python-http-api

Python library for XNT Ltd. FIX API service Provides object-oriented access to actual endpoints (fix*.exante.eu)
All methods are strictly typed, python3.7+.

## Dependencies

Library creates interface under [QuickFIX Engine](http://www.quickfixengine.org/) to provide all existed methods described at [ExanteFIX](https://exante.eu/clientsarea/media/manuals/docs/2020/01/ExanteFIX_1.13.3.pdf).
Due to several issues with generation on python wrapper of original C+ library it's impossible to use [official Quickfix python library](https://pypi.org/project/quickfix/).
It is neccessary to use forked version of this library (for more details check https://github.com/xntltd/quickfix)

## Building and installation

Package available from github assets and pypi repository

~~pip install xnt-python-fix-api~~

## Configuration

Package deploys updated [FIX44.xml](src/xnt/config/FIX44.xml) dictionary for using with XNT Ltd. services and example of [configuration file](src/xnt/config/settings.conf).
Due to engine restrictions it is neccessary to provide an absolute path to both DataDictionary and TransportDataDictionary:

    DataDictionary=/home/user/.local/lib/python3.8/site-packages/xnt/config/FIX44.xml
    TransportDataDictionary=/home/user/.local/lib/python3.8/site-packages/xnt/config/FIX44.xml

You should fill SenderCompIDs, Passwords and connection addresses for each session with data provided by tech-support team. If necessary, adjust session intervals.
ResetOnLogon flags are neccessary for FEED session, but it's not recommended to reset MessageSeqNum for TRADE sessions due to possibility of state loss
More info about configuring QuickFIX Engine and it's options can be found [here](http://www.quickfixengine.org/quickfix/doc/html/)

## Basic usage

Main class [FixAdapter](src/xnt/fix_api.py#L114) provides all neccessary methods to access API, each method has docstring with basic explanation of its usage.

    from xnt.fix_api import FixAdapter, Side, Durations, OrdType, Decimal, MDEntryType, CFICode
    import quickfix as fix 
    from datetime import datetime
    settings = fix.SessionSettings('/home/ab/.local/lib/python3.8/site-packages/xnt/config/settings.conf') 
    app = FixAdapter(fix.Session, settings) 
    store = fix.FileStoreFactory(settings) 
    logs = fix.FileLogFactory(settings) 
    initiator = fix.SocketInitiator(app, store, settings, logs) 
    initiator.start() # at this point engine establish connections to all provided sessions
    c = app.collector # access to state collector

Most basic example of library usage in building stand-alone trading applications can be checked in [example](tests/http_robot.py)
