ECHO OFF
REM Leg BE -- SS16ag errno A/B, TREATMENT arm, run 1 of 2.
REM CKFERR = make -f victorow.mak XFLAGS=-dV9K_FAST_ERRNO, 204,888 bytes.
REM Byte-identical to SS16ag legs AL/AN.  98 ms SLOWER under MAME at 9600.
CKFERR -l /dev/seriala -b 38400 -r > STEPBE.OUT
