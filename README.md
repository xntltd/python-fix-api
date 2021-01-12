# python-http-api

Python library for XNT Ltd. HTTP API service Provides object-oriented access to actual endpoints (https://api-live.exante.eu/api-docs/)
All methods are strictly typed, python3.7+.

## Dependencies

Library creates interface under [QuickFIX Engine](http://www.quickfixengine.org/) to provide all existed methods described at [ExanteFIX](https://exante.eu/clientsarea/media/manuals/docs/2020/01/ExanteFIX_1.13.3.pdf).
Due to several issues with generation on python wrapper of original C+ library it's impossible to use [official Quickfix python library](https://pypi.org/project/quickfix/).
It is neccessary to use forked version of this library (for more details check https://github.com/xntltd/quickfix)

## Building and installation

Package available from github assets and pypi repository

~~pip install xnt-python-fix-api~~

## Basic usage

Main class [FixAdapter](src/xnt/fix_api.py#L114) provides all neccessary methods to access API, each method has docstring with basic explanation of its usage.
Session setting should be provided to the FIX Engine before initialization. Settings example can be found [here](src/xnt/config/settings.conf). You should fill SenderCompIDs, Passwords and connection addresses for each session with data provided by tech-support team. If necessary, adjust session intervals.
Actual [FIX Dictionary](src/xnt/config/FIX44.xml) also included within package
More info about configuring QuickFIX can be found [here](http://www.quickfixengine.org/quickfix/doc/html/)

Most basic example of library usage in building stand-alone trading applications can be checked in [example](tests/http_robot.py)