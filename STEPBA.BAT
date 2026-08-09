ECHO OFF
REM Leg BA -- SS16af leg AG repeated, for the HOST clock.  Block check 3.
REM Targets: rxfull 0, rxpeak 2581, rxbytes 37568, 18 pkts, elapsed 2800 cs.
REM The host redirect is the point of the leg -- see HW_TEST_16ag.md leg 1.
CKERMITW -l /dev/seriala -b 38400 -r > STEPBA.OUT
