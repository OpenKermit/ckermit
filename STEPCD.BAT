ECHO OFF
REM Leg CD -- the Victor SENDS with PX_ALL.  CONTROL for leg CC.
REM CKPXALL is the same tree and the same size as CKERMITW; the only
REM difference is the constant the prefixing initializer stores.
REM START THE HOST RECEIVER FIRST -- the Victor is the initiator.
CKPXALL -l /dev/seriala -b 38400 -s TRANS.DAT > STEPCD.OUT
