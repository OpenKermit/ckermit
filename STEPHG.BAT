ECHO OFF
REM Leg HG -- FreeDOS at 38400.  NO CONTROL EXISTS ANYWHERE; MAME cannot
REM drive this machine above about 9600, so this is discovery.
REM The readings that matter are rxlost and rxfull, not cps.
IF EXIST RCVHG.DAT DEL RCVHG.DAT
IF EXIST STEPHG.OUT DEL STEPHG.OUT
CKBB.EXE --nodisplay -l COM2 -b 38400 -r > STEPHG.OUT
