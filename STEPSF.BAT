ECHO OFF
REM Leg SF -- REMOTE RMDIR with the trailing-separator shim (CKSRV2.EXE).
IF EXIST STEPSF.OUT DEL STEPSF.OUT
CKSRV2.EXE -l /dev/seriala -b 9600 -x > STEPSF.OUT
