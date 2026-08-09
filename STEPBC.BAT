ECHO OFF
REM Leg BC -- SS16ag errno A/B, CONTROL arm, run 1 of 2.
REM CKERMITW as shipped: errno through the library's far call.
REM Byte-identical to SS16ag legs AP/AQ.
CKERMITW -l /dev/seriala -b 38400 -r > STEPBC.OUT
