ECHO OFF
REM Leg AG -- edit 17 (fast chk3), cautious x block 3.  THE HEADLINE LEG.
REM Compare against SS16ae leg PC: 38.00 s, rxpeak 4095 PINNED, rxfull 640,
REM 44,720 wire bytes to move 32,768.  Read rxfull FIRST, then wire bytes.
CKERMITW -l /dev/seriala -b 38400 -r > STEPAG.OUT
