ECHO OFF
REM Leg AM -- PORTING.md SS16ag, the control REPEATED.
REM Same binary as leg AK.  This leg exists to measure the harness's own
REM run-to-run spread, without which the AK-AL difference is one sample.
CKERMITW -l /dev/seriala -b 9600 -r > STEPAM.OUT
