ECHO OFF
REM Leg FD -- PORTING.md SS16aj.  Diagnostic: no host, no socat.  Open the
REM line with --xonxoff and read the debug log to see what ttpkt() hands
REM tcsetattr().  The receive times out against nothing, which is fine.
CKFCD -d -l /dev/seriala -b 9600 --xonxoff -r > STEPFD.OUT
REN DEBUG.LOG FDXON.LOG
