ECHO OFF
REM Leg BE -- repeat of BB.
IF EXIST RCVBE.DAT DEL RCVBE.DAT
CKWIN8K -l /dev/seriala -b 38400 --window=2 -r > STEPBE.OUT
