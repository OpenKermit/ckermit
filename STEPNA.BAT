ECHO OFF
REM Legs NA/NB -- nap(), FILE COLLISION REPLACE, DOS probe.  CKNAP build.
REM NB deliberately does NOT delete: it must OVERWRITE what NA wrote.
IF EXIST RCVNA.DAT DEL RCVNA.DAT
CKNAP -l /dev/seriala -b 9600 -r > STEPNA.OUT
CKNAP -l /dev/seriala -b 9600 -r > STEPNB.OUT
