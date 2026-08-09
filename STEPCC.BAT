ECHO OFF
REM Leg CC -- the Victor SENDS with PX_CAU (the prefixing fix).
REM COUNTING leg, not a timing one: read wire bytes and prefix chars.
REM START THE HOST RECEIVER FIRST -- the Victor is the initiator.
CKERMITW -l /dev/seriala -b 38400 -s TRANS.DAT > STEPCC.OUT
