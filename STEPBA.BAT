ECHO OFF
REM Leg BA -- route B (ring 8192, DRPSIZ 3800), window 1.  Control.
IF EXIST RCVBA.DAT DEL RCVBA.DAT
CKWIN8K -l /dev/seriala -b 38400 --window=1 -r > STEPBA.OUT
