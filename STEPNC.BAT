ECHO OFF
REM Leg NC/ND -- FILE COLLISION REPLACE, ptab fix (SS16ai trap, 2nd try).
REM ND must OVERWRITE what NC wrote, so NOTHING deletes between them.
REM Leg NX -- unknown-option control.  NS -- --safe-server.
IF EXIST RCVNC.DAT DEL RCVNC.DAT
IF EXIST RCVNS.DAT DEL RCVNS.DAT
CKNAP2 -l /dev/seriala -b 9600 -r > STEPNC.OUT
CKNAP2 -l /dev/seriala -b 9600 -r > STEPND.OUT
CKNAP2 --safe-serverz -l /dev/seriala -b 9600 -x > STEPNX.OUT
CKNAP2 --safe-server -l /dev/seriala -b 9600 -x > STEPNS.OUT
