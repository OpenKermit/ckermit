ECHO OFF
REM Leg FJ -- PORTING.md SS16aj.  The control for FH: SAME BINARY, same
REM lowered marks, one switch.  SS16w makes two binaries a confound, so the
REM control is a switch and not a rebuild.
CKFCLO -l /dev/seriala -b 9600 --noflow -r > STEPFJ.OUT
