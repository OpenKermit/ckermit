ECHO OFF
REM Leg UC -- server capability sweep, merged build.  Edits 19 and 20.
IF EXIST STEPUC.OUT DEL STEPUC.OUT
IF EXIST SRVU.TXT DEL SRVU.TXT
CKMRG -l /dev/seriala -b 9600 -x > STEPUC.OUT
