ECHO OFF
REM Leg UB -- Victor SENDS SNDUB.DAT (32,768) BY NAME at 9600.
REM Regression for upstream edit 16 (16-bit rc at ckuusy.c) + send path.
IF EXIST STEPUB.OUT DEL STEPUB.OUT
CKMRG -l /dev/seriala -b 9600 -s SNDUB.DAT > STEPUB.OUT
