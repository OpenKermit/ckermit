ECHO OFF
REM Leg HM (pass 2) -- the parser build after the merge, FROM A:.
REM 460,466 bytes, needs 453,986 (443K), DGROUP 59,632 (90%) -- a 640K
REM class build, the first upstream merge ever to move a class.
REM Edits 12, 13, 14 and 15 by ABSOLUTE path.  No serial partner here.
REM The 435,154-byte CKICP.EXE that used to sit on A: was the PRE-merge
REM build and has been REMOVED: running it would have reproduced a stale
REM binary as if it were this one (SS16ai trap).
IF EXIST STEPHM.OUT DEL STEPHM.OUT
CKICP.EXE A:\SPDTEST.KSC > STEPHM.OUT
