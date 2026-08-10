ECHO OFF
REM Leg FB -- PORTING.md SS16aj.  XON/XOFF, with the water marks lowered to
REM 256/64 so the mechanism actually fires: at 9600 rxpeak sits near 300.
REM Host runs "set flow xon/xoff", so both directions are exercised.
CKFCLO -l /dev/seriala -b 9600 --xonxoff -r > STEPFB.OUT
