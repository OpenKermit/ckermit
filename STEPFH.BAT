ECHO OFF
REM Leg FH -- PORTING.md SS16aj.  XON/XOFF, water marks lowered to 256/64
REM so the mechanism fires: rxpeak sits near 300 at 9600.  Host runs
REM "set flow xon/xoff", so both directions are exercised.
CKFCLO -l /dev/seriala -b 9600 --xonxoff -r > STEPFH.OUT
