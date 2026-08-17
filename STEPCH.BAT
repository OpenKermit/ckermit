ECHO OFF
REM Leg CH -- the FIRST transfer ever run on the parser build.
REM CKICP is rebuilt as of 9 Aug and carries upstream edits 16 and 17.
REM A stale CKICP would reproduce SS16af's ring defect at 38400.
CKICP RXEA.KSC > STEPCH.OUT
