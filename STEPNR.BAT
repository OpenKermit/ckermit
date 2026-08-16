ECHO OFF
REM Leg NR -- REMOTE DIRECTORY diagnosis (SS1 item 15).  KEEP_DEBUG build.
REM Server runs with the FULL capability set, which is what hangs.
IF EXIST NR.LOG DEL NR.LOG
CKNAPD -d -l /dev/seriala -b 9600 -x > STEPNR.OUT
REN DEBUG.LOG NR.LOG
