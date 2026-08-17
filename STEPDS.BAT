ECHO OFF
REM Leg DS -- the CTS GATE, and the one leg that can wedge.  Run it early.
REM --rtscts makes v9k_ser_put() require RR0 CTS before every byte.  SS16v
REM read cts=1 on this cable, so this should transfer -- but if CTS is not
REM actually wired the Victor will send NOTHING AT ALL, and that is the
REM failure the FLO_NONE default exists to avoid.  Do not debug it at the
REM bench; record it and stop this arm.
CKERMITW -l /dev/seriala -b 38400 --rtscts -s TRANS.DAT > STEPDS.OUT
