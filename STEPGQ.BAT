ECHO OFF
REM Leg GQ -- the shipping build with section 1f, immediately after GP.
REM Same fixture, same rate, no switch: flow control compiled in and off.
REM GQ minus GP is the cost of section 1f, measured within one sitting.
REM Note the two binaries are 205,228 and 206,758, so SS16w's code-size
REM sensitivity IS in play here -- unlike CKFCLO/CKFCMID.  That is not a
REM confound, it is part of what is being costed.
IF EXIST RCVGQ.DAT DEL RCVGQ.DAT
CKERMITW -l /dev/seriala -b 38400 -r > STEPGQ.OUT
