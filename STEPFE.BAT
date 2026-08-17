ECHO OFF
REM Leg FE -- PORTING.md SS16aj.  Section 1f's command-line switches, read
REM back through the debug log because uname() reports them in every
REM invocation (SS16i).  No serial line, no socat, no host.
REM The fourth is SS16i's mandatory unknown-option control: without it
REM "recognised" cannot be told from "silently ignored".
CKFCD --xonxoff -d -h > STEPFEA.OUT
REN DEBUG.LOG FEXON.LOG
CKFCD --rtscts -d -h > STEPFEB.OUT
REN DEBUG.LOG FERTS.LOG
CKFCD -d -h > STEPFEC.OUT
REN DEBUG.LOG FEDEF.LOG
CKFCD --xonxofz -d -h > STEPFED.OUT
REN DEBUG.LOG FEBAD.LOG
