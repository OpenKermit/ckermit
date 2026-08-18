ECHO OFF
REM Leg UA -- 32 KB receive at 9600, merged (11.0.508) shipping build.
REM Regression for PORTING.md 16aq/16af: byte-exact, rxlost/rxfull 0.
IF EXIST RCVUA.DAT DEL RCVUA.DAT
IF EXIST STEPUA.OUT DEL STEPUA.OUT
CKMRG -l /dev/seriala -b 9600 -r > STEPUA.OUT
