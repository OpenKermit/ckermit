ECHO OFF
REM Leg HB -- the Victor SENDS 32,768 bytes BY NAME at 38400.
REM Edit 16 range.  Control: SS16ai leg CC -- PX_CAU exactly (32 values),
REM 4,512 prefixes, 37,557 wire bytes, 18 packets, 22.207 s, 1,475 cps.
REM
REM THE FIXTURE IS FIXTURE.DAT, NOT TRANS.DAT.  Leg CC sent TRANS.DAT and
REM TRANS.DAT IS NO LONGER ON THIS IMAGE -- it went in a cleanup.  A:\
REM FIXTURE.DAT is 32,768 bytes and md5 d94d2bed..., byte-identical to it,
REM and edit 16 keys off the SIZE, not the name.
REM
REM No --nodisplay: leg CC did not use it and this must match it.
REM START THE HOST RECEIVER FIRST -- the Victor is the initiator.
IF EXIST STEPHB.OUT DEL STEPHB.OUT
D:\CKBB.EXE -l /dev/seriala -b 38400 -s FIXTURE.DAT > STEPHB.OUT
