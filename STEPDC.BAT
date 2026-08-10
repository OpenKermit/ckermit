ECHO OFF
REM Leg DC -- XON/XOFF, the same reading as DB.  Same binary as DA and DB.
REM In-band, so byte-exactness is load-bearing here in a way it is not for
REM RTS/CTS: PX_CAU keeps DC1 and DC3 prefixed (ckcmai.c:2699,2705), and a
REM leg that is fast and wrong is the failure mode.  cmp before you read
REM any counter.
CKFCLO -l /dev/seriala -b 38400 --xonxoff -r > STEPDC.OUT
