ECHO OFF
REM Leg NF -- receive onto a FULL disk (SS1 item 5).  Must FAIL, not HANG.
IF EXIST RCVNF.DAT DEL RCVNF.DAT
CKNAP2 -l /dev/seriala -b 9600 -r > STEPNF.OUT
