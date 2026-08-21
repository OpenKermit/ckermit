ECHO OFF
REM Leg HH -- the FreeDOS console arm.  THERE IS NO REDIRECT ON THIS LEG
REM AND THAT IS THE POINT: SS16u says the transfer display goes away under
REM the redirect that records the counters, so a leg that has to SHOW you
REM a screen cannot have one.  SS16ba first attempt and SS16az leg FDG both
REM died of this.  The picture and the counters need two runs; HG is the
REM run with the counters and this is the run with the picture.
REM PHOTOGRAPH THE SCREEN MID-TRANSFER.
IF EXIST RCVHH.DAT DEL RCVHH.DAT
CLS
CKBB.EXE -l COM2 -b 38400 -r
