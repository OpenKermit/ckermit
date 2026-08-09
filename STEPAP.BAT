ECHO OFF
REM Leg AP -- PORTING.md SS16ag, the SPLIT leg.
REM NOCKXXCHAR in, the errno pointer OUT: built with XFLAGS=-dV9K_LIBC_ERRNO,
REM so v9k_errnop is still compiled and simply not used.  AP against AK
REM isolates NOCKXXCHAR; AP against AL/AN isolates the errno far call.
CKAP -l /dev/seriala -b 9600 -r > STEPAP.OUT
