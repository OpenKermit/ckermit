ECHO OFF
REM Leg DA -- the CONTROL half of the decisive pair.  CKFCLO is the
REM shipping tree with the water marks at 256/64 and NOTHING ELSE; it is
REM the same 206,758 bytes and it has already run byte-exact under MAME.
REM --noflow, so the marks are unreachable.  Read rxpeak.
REM RUN DA AND DB BACK TO BACK.  Nothing in this sitting is comparable
REM across a gap.
CKFCLO -l /dev/seriala -b 38400 --noflow -r > STEPDA.OUT
