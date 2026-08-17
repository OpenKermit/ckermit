ECHO OFF
REM Leg DE -- the SHIPPING CANDIDATE.  Shipping build, shipping water
REM marks (3072/1024), --rtscts.  This is the exact configuration that
REM turning the default on would produce, so it is the leg that licenses
REM the change.  held should be 0: the mark is above every occupancy this
REM port has ever recorded.  Only run it if DB passed.
CKERMITW -l /dev/seriala -b 38400 --rtscts -r > STEPDE.OUT
