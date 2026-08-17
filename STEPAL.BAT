ECHO OFF
REM Leg AL -- PORTING.md SS16ag, NOCKXXCHAR + the errno pointer.
REM Same fixture, same 9600, same take-file settings as leg AK, so the only
REM difference is the two ckvictor.h/ckvictor.c changes.  Protocol-identical
REM is the test to look for: rxbytes must equal AK's.
CKAL -l /dev/seriala -b 9600 -r > STEPAL.OUT
