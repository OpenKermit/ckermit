ECHO OFF
REM Leg AF -- PORTING.md SS16af, the fast chk3().
REM Mirrors SS16u leg CM exactly: same fixture, same 9600, same take-file
REM settings, so the only difference is the block-check arithmetic.
REM Baseline to beat: elapsed=6700 cs, rxpeak=294, 24 packets, byte-exact.
CKERMITW -l /dev/seriala -b 9600 -r > STEPAF.OUT
