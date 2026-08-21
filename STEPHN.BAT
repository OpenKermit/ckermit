ECHO OFF
REM Leg HN (pass 2) -- HL control, one VOLUME over: receive into D:\.
REM THE REDIRECT GOES TO A:, DELIBERATELY.  The received file has to land
REM on D: because D: IS the variable, but no D: write survived pass 1, so
REM the counters -- which are the result -- are written to A: instead.
REM If RCVHN.DAT is missing afterwards but STEPHN.OUT is there, the leg
REM still reports: dec max= and elapsed= are what this pair compares.
IF EXIST A:\STEPHN.OUT DEL A:\STEPHN.OUT
D:
IF EXIST RCVHN.DAT DEL RCVHN.DAT
CKBB.EXE --nodisplay -l /dev/seriala -b 9600 -r > A:\STEPHN.OUT
A:
