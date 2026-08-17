ECHO OFF
REM Leg FA -- PORTING.md SS16aj.  THE NULL LEG.  Shipping build, flow
REM control compiled in and switched off, which is the default.  It has to
REM reproduce a clean 9600 receive: byte-exact, rxlost=0 rxfull=0, and
REM every counter on the new "v9k: flow" line at 0.  It also reads mdm cts
REM under MAME, which is what says whether an RTS/CTS leg is possible here.
CKFCA -l /dev/seriala -b 9600 -r > STEPFA.OUT
