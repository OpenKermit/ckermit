ECHO OFF
REM Leg BB -- route B, window 2.  THE leg: long packets AND a window.
IF EXIST RCVBB.DAT DEL RCVBB.DAT
CKWIN8K -l /dev/seriala -b 38400 --window=2 -r > STEPBB.OUT
