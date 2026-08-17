ECHO OFF
REM Leg AH -- edit 17, cautious x block 1.  The floor.
REM chk1() is untouched by edit 17, so this must REPRODUCE SS16ae leg BX
REM (26.50 s, rxpeak 2611, rxfull 0).  If it does not, something else moved.
CKERMITW -l /dev/seriala -b 38400 -r > STEPAH.OUT
