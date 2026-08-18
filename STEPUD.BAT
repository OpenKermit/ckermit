ECHO OFF
REM Leg UD -- parser build, SPDTEST.KSC by ABSOLUTE path.  Edits 12-15.
REM No serial partner: set line/set speed only, nothing transfers.
IF EXIST STEPUD.OUT DEL STEPUD.OUT
CKMRGI A:\SPDTEST.KSC > STEPUD.OUT
