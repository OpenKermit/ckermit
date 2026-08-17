ECHO OFF
REM Leg AR -- PORTING.md SS16ag.  Leg AK repeated: the shipping edit-17
REM control.  AM was the first attempt and came back 0 timeouts / 0 resends,
REM a different protocol shape, so it is not a second AK sample.
CKERMITW -l /dev/seriala -b 9600 -r > STEPAR.OUT
