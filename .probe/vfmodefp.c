/*
  vfmodefp.c -- a throwaway probe, not part of the port.  Companion to
  vfmode.c; see PORTING.md SS16h.

  vfmode.c measured that Open Watcom's binmode.obj DOES set _fmode to
  O_BINARY on Victor MS-DOS 3.1 -- in a small program.  Linked into
  CKERMITW.EXE the same object leaves _fmode at 0100 (O_TEXT), measured
  through CKERMITW's own debug log, which zopeno() opens with fopen(,"w").

  Everything static checks out: the XI record is present (the table grows
  0x3c -> 0x42), cstart runs every priority ("mov ax,0FFh"), _TEXT is a
  single 60,160-byte segment so callit_near() can reach do_it_, and _fmode
  is the plain variable in both programs.

  The one STRUCTURAL difference between the two programs is floating point.
  CKERMITW drags in emu87.lib -- NOGFTIMER is still on, so gftimer() wants
  a float -- and the 8087 emulator installs itself from __init_8087_emu,
  which is another routine in the very same XI table binmode's record sits
  in.  An initializer that runs earlier and disturbs a segment register (or
  a vector) would break a later near-call initializer without crashing.

  So: this is vfmode.c plus one double.  If _fmode comes back 0100 here and
  0200 in vfmode.c, floating point is the difference and the emulator init
  is the suspect.  If it comes back 0200, it is not, and the difference is
  something else about CKERMITW.

    wcc -ml -0 -os -zq -zc -bt=dos -i=<rel>/h vfmodefp.c
    wlink system dos name vfmodefp.exe file { vfmodefp.obj <binmode.obj> }
*/
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/stat.h>

static void
wtest(char * name, char * mode)
{
    FILE * f;
    struct stat b;
    long n = -1;

    f = fopen(name,mode);
    if (!f) {
        printf("  fopen(%s,\"%s\") FAILED\n",name,mode);
        return;
    }
    fwrite("A\nB",1,3,f);
    fclose(f);
    if (stat(name,&b) == 0)
      n = (long)b.st_size;
    printf("  wrote 3 bytes (A LF B) with mode \"%-2s\" -> file is %ld bytes%s\n",
           mode, n, (n == 3) ? "  BINARY" : "  TEXT");
    remove(name);
}

int
main(int argc, char **argv)
{
    /*
      Read _fmode BEFORE touching the FPU: the emulator installs itself
      from an XI initializer, before main, so if it is the culprit the
      damage is already done by the time this line runs.  The double below
      is only here to make the linker pull emu87.lib in at all.
    */
    printf("vfmodefp: _fmode=%04x  (O_TEXT=%04x O_BINARY=%04x)\n",
           (unsigned)_fmode, (unsigned)O_TEXT, (unsigned)O_BINARY);
    wtest("FPA.TMP","w");
    wtest("FPB.TMP","wb");
    {
        /* argc keeps the optimiser from folding this away, so emu87.lib
           really is linked -- which is the whole point of the probe. */
        double d = (double)argc + 3.5;
        printf("  (float linkage: %f)\n", d * 2.0);
    }
    return(0);
}
