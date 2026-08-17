ECHO OFF
REM Leg FC -- PORTING.md SS16aj.  The control for FB: SAME BINARY, same
REM lowered marks, one switch.  SS16w makes two binaries a confound, so the
REM switch is the control and not a rebuild.
CKFCLO -l /dev/seriala -b 9600 --noflow -r > STEPFC.OUT
