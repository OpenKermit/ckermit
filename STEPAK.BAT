ECHO OFF
REM Leg AK -- PORTING.md SS16ag, the CONTROL.
REM The shipping edit-17 binary, 205,968 bytes, unchanged.  Run in the same
REM session as leg AL so the comparison is a binary difference and not a
REM rebuild -- SS16af leg AJ is why this leg exists at all.
REM Baseline to match: SS16af leg AF, elapsed=6450 cs, rxbytes=39575.
CKERMITW -l /dev/seriala -b 9600 -r > STEPAK.OUT
