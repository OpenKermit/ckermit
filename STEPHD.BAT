ECHO OFF
REM Leg HD -- THE LEG -- first RTS/CTS run with a far end that can stop.
REM Marks are the SHIPPING 3072/1024.  Read hi= and lo= back off the
REM .OUT: a switch that silently failed looks exactly like a null result.
REM Same volume and same form as HA, so the three are comparable.
IF EXIST RCVHD.DAT DEL RCVHD.DAT
IF EXIST RCVHD.001 DEL RCVHD.001
IF EXIST STEPHD.OUT DEL STEPHD.OUT
D:\CKBB.EXE --rtscts --nodisplay -l /dev/seriala -b 38400 -r > STEPHD.OUT
