ECHO OFF
REM Leg AJ -- BASELINE build (16 edits), cautious x block 3.  THE CONTROL.
REM Same session, same cable, same day as AG.  SS16ae leg PC was a different
REM session; this is what makes AG a controlled comparison rather than a
REM cross-session one.  Note it runs CKBASE.EXE, not CKERMITW.EXE.
CKBASE -l /dev/seriala -b 38400 -r > STEPAJ.OUT
