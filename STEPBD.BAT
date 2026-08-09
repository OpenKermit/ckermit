ECHO OFF
REM Leg BD -- SS16ag errno A/B, CONTROL arm, run 2 of 2.
REM Two legs per arm: SS16ag's control arm spread 321 ms, unexplained.
CKERMITW -l /dev/seriala -b 38400 -r > STEPBD.OUT
