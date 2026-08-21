ECHO OFF
REM Leg HE -- the other half; watch xoff/xon/stuck and rxlost.
REM Marks are the SHIPPING 3072/1024.  Read hi= and lo= back off the
REM .OUT: a switch that silently failed looks exactly like a null result.
REM Same volume and same form as HA, so the three are comparable.
IF EXIST RCVHE.DAT DEL RCVHE.DAT
IF EXIST RCVHE.001 DEL RCVHE.001
IF EXIST STEPHE.OUT DEL STEPHE.OUT
D:\CKBB.EXE --xonxoff --nodisplay -l /dev/seriala -b 38400 -r > STEPHE.OUT
