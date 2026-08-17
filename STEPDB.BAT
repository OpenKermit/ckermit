ECHO OFF
REM Leg DB -- THE LEG THE WHOLE SITTING IS FOR.  Same binary as DA, one
REM switch.  The Victor drops RTS at 256 bytes of ring occupancy and
REM raises it at 64.  The question is whether the far end ever sees it.
REM THE READING IS rxpeak, NOT THE CLOCK:
REM   rxpeak near 256-600  -> the host obeyed;  our RTS reaches its CTS
REM   rxpeak near 2,4xx    -> we asserted and nothing happened
REM held/rel say we asserted.  rxpeak says they listened.
CKFCLO -l /dev/seriala -b 38400 --rtscts -r > STEPDB.OUT
