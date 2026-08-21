ECHO OFF
REM Leg HA -- 32 KB receive at 38400.  THE REGRESSION LEG.
REM Control: SS16aq legs KA/KC/KN_2 -- 25.652/25.659/25.668 s, 1,277 cps,
REM 37,557 wire bytes, 18 packets, 0/0, rxpeak 409-488.
REM RUNS ON A: DELIBERATELY -- the control did, and changing the volume
REM would add a second variable to a leg whose whole job is to have none.
REM CKBB.EXE is on D: and is invoked from there: A: has 360 KB free and
REM the binary is 231 KB.  The loader reads it from D:, the program then
REM runs on A: and writes here.  Code and data are identical either way.
IF EXIST RCVHA.DAT DEL RCVHA.DAT
IF EXIST RCVHA.001 DEL RCVHA.001
IF EXIST STEPHA.OUT DEL STEPHA.OUT
D:\CKBB.EXE --nodisplay -l /dev/seriala -b 38400 -r > STEPHA.OUT
