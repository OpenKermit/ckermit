ECHO OFF
REM Leg CS -- server mode on hardware.  HW_TESTING leg 0.7.
REM The Victor waits; the host drives with send/get/finish.
CKERMITW -l /dev/seriala -b 38400 -x > STEPCS.OUT
