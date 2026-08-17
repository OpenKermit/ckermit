ECHO OFF
REM Leg CE -- the NULL leg.  Victor receives 32 KB at 38400.
REM Prefixing is a sender-side decision, so this should be unchanged.
CKERMITW -l /dev/seriala -b 38400 -r > STEPCE.OUT
