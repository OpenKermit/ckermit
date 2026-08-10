ECHO OFF
REM Leg DN -- PORTING.md SS16aj bench sitting.  THE NULL LEG.
REM Shipping build, no switch, flow control compiled in and off.  This is
REM the leg that says the machine, the cable and the harness are behaving
REM before anything else in the sitting is attributed to anything.
REM Pass is SS16ai leg CE / SS16ah leg BC shape.
CKERMITW -l /dev/seriala -b 38400 -r > STEPDN.OUT
