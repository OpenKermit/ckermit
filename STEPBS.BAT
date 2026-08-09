ECHO OFF
REM Leg BS -- the Victor SENDS, by name, a file of exactly 32,768 bytes.
REM Closes upstream edit 16, which shipped with a wdis reading and no run.
REM START THE HOST RECEIVER FIRST -- the Victor is the initiator here.
REM The tell for the old bug is "kermit -s NAME:" with an EMPTY message.
CKERMITW -l /dev/seriala -b 38400 -s RCVAG.DAT > STEPBS.OUT
