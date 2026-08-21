ECHO OFF
REM Leg HC -- the control: flow control compiled in and switched off.
REM Marks are the SHIPPING 3072/1024.  Read hi= and lo= back off the
REM .OUT: a switch that silently failed looks exactly like a null result.
REM Same volume and same form as HA, so the three are comparable.
IF EXIST RCVHC.DAT DEL RCVHC.DAT
IF EXIST RCVHC.001 DEL RCVHC.001
IF EXIST STEPHC.OUT DEL STEPHC.OUT
D:\CKBB.EXE --noflow --nodisplay -l /dev/seriala -b 38400 -r > STEPHC.OUT
