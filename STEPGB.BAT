ECHO OFF
REM Leg GB -- the efficacy leg.  Same binary as GA, one switch.  RTS drops
REM at 1024 and rises at 896, so occupancy should be PINNED near 1024 if
REM the far end obeys and should follow GA's curve to 2,8xx-3,1xx if it
REM does not.  The reading is rxpeak, and this time it is a CAP rather than
REM a comparison, so a retransmission does not void it.
REM ALWAYS run mapoffset.py on peakat before believing rxpeak.
IF EXIST RCVGB.DAT DEL RCVGB.DAT
CKFCMID -l /dev/seriala -b 38400 --rtscts -r > STEPGB.OUT
