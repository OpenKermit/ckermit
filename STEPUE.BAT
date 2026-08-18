ECHO OFF
REM Leg UE -- 32 KB receive at 9600, host started LATE (t+150) so the
REM Victor is already waiting.  Timing control for leg UA.
IF EXIST RCVUE.DAT DEL RCVUE.DAT
IF EXIST STEPUE.OUT DEL STEPUE.OUT
CKMRG -l /dev/seriala -b 9600 -r > STEPUE.OUT
