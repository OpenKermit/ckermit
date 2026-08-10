ECHO OFF
REM Leg FG -- PORTING.md SS16aj.  THE NULL LEG, repeated after the SS1f
REM source of truth moved from the termios bits to upstream's "flow".
REM Shipping build, flow control compiled in and off.  Must reproduce the
REM pre-change control leg FZ.
CKFCA -l /dev/seriala -b 9600 -r > STEPFG.OUT
