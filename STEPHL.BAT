ECHO OFF
REM Leg HL (pass 2) -- the rcvfil() stall pair, receive into A:\ at 9600.
REM NO -d, AND THAT IS A CHANGE FROM PASS 1.  The instrument is dec max=
REM on the .OUT plus the F-packet-to-ACK gap in the host packet log:
REM SS16ba read stalled legs at 3250/3350 and clean ones at 100-150, and
REM leg HA already showed dec max=450 at 38400 on this very volume.
REM -d costs ~25 ms per received byte (SS16k) and a ~180 KB log on a
REM volume with 720 KB free.  Leg HP does the -d run separately.
REM Run HN immediately after this.  ONE VARIABLE: the volume.
IF EXIST RCVHL.DAT DEL RCVHL.DAT
IF EXIST STEPHL.OUT DEL STEPHL.OUT
CKBB.EXE --nodisplay -l /dev/seriala -b 9600 -r > STEPHL.OUT
