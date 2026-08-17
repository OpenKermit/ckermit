ECHO OFF
REM Leg BD -- repeat of BA.
IF EXIST RCVBD.DAT DEL RCVBD.DAT
CKWIN8K -l /dev/seriala -b 38400 --window=1 -r > STEPBD.OUT
