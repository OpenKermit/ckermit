ECHO OFF
REM Leg HJ (pass 2) -- server sweep at 38400.  Edits 19, 20 and 22.
REM RUNS ENTIRELY ON A: NOW.  Pass 1 ran on D:, answered every command
REM correctly, and then NOT ONE D: WRITE SURVIVED -- no STEPHJ.OUT, no
REM GOTHJ.DAT.  A: writes persisted in the same sitting.  Until that is
REM understood, A: is the only volume this bench can record a result on.
REM REMOTE HELP IS THE FIRST COMMAND THE HOST SENDS (SS16ax).
IF EXIST STEPHJ.OUT DEL STEPHJ.OUT
IF EXIST GOTHJ.DAT DEL GOTHJ.DAT
IF EXIST RCVHJ.DAT DEL RCVHJ.DAT
CKBB.EXE -l /dev/seriala -b 38400 -x > STEPHJ.OUT
