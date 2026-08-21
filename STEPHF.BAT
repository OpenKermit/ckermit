ECHO OFF
REM Leg HF -- FreeDOS for Victor on REAL hardware, first time.  COM2.
REM CHANNEL B IS NOT A PREFERENCE: entry.asm:280 writes an H to the 7201
REM at E000:0040 on EVERY INT 21h call, and hard rule 6 puts every console
REM and file write of this port through INT 21h.  Channel B is 0041/0043
REM and nothing in the kernel touches it.
REM Comparable to SS16az leg FDE: 685 cps, 0 damaged, 0 timeouts, 0 resends.
REM Expect  v9k: dos oem=fd ver=622 irq1=09
IF EXIST RCVHF.DAT DEL RCVHF.DAT
IF EXIST STEPHF.OUT DEL STEPHF.OUT
CKBB.EXE --nodisplay -l COM2 -b 9600 -r > STEPHF.OUT
