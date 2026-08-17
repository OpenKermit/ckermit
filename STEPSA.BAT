ECHO OFF
REM Leg SA -- server capability sweep: informational and refusal commands.
REM Full capability set, no --safe-server.  CKRDR2.EXE md5 5f2a1580.
IF EXIST STEPSA.OUT DEL STEPSA.OUT
CKRDR2 -l /dev/seriala -b 9600 -x > STEPSA.OUT
