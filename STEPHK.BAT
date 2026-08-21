ECHO OFF
REM Leg HK (pass 2) -- edit 21 on the wire.  ON A: for the same reason.
REM --safe-server forces FILE COLLISION to RENAME for the whole session
REM (ckcpro.c:503), so this path is not optional.  TWO name LENGTHS:
REM znewn() picks its branch by length and the control failed differently
REM in each (4 chars: E packet, empty text; 9 chars: SILENT OVERWRITE).
REM THE DISK IS THE OBSERVABLE -- the F-packet ACK reports fspec, which
REM rcvfil() fills BEFORE the collision switch runs.  Pass 1 ran the leg
REM and the answer was LOST WITH THE D: WRITES, which is exactly why the
REM observable has to be somewhere that persists.
IF EXIST RCVHK.DAT DEL RCVHK.DAT
IF EXIST RCVHK.001 DEL RCVHK.001
IF EXIST HK.D DEL HK.D
IF EXIST HK.001 DEL HK.001
IF EXIST STEPHK.OUT DEL STEPHK.OUT
CKBB.EXE --safe-server -l /dev/seriala -b 38400 -x > STEPHK.OUT
