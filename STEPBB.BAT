ECHO OFF
REM Leg BB -- SS16af leg AH repeated, for the HOST clock.  Block check 1.
REM Targets: rxfull 0, rxpeak 2585, rxbytes 37534, 18 pkts, elapsed 2700 cs.
REM A null result against AH is the pass.  BA minus BB is the deliverable.
CKERMITW -l /dev/seriala -b 38400 -r > STEPBB.OUT
