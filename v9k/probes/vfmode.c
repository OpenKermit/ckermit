/*
  vfmode.c -- a throwaway probe, not part of the port.

  PORTING.md SS16h.  ckufio.c is the UNIX file module: zopeni() is a bare
  fopen(name,"r") and zopeno() only ever builds "w" or "a", so nothing in
  C-Kermit ever says "b" and the DOS runtime's default translation mode
  decides whether a binary transfer survives.  Open Watcom ships
  binmode.obj to set that default to O_BINARY before main().

  Linking it into CKERMITW.EXE did NOT work: with "#undef NLCHAR" in place
  so C-Kermit itself does no conversion, a received 2048-byte file still
  landed on disk as 2056 -- one added CR per LF, i.e. still O_TEXT.

  Everything checked statically says it should have worked: the object is
  in the image (+22 bytes), __InitRtns is linked, and XIB/XI/XIE bracket a
  well-formed 11-entry table with binmode's record among them.  So stop
  inferring and read _fmode on the machine.

    wcc -ml -0 -os -zq -zc -bt=dos -i=<rel>/h vfmode.c
    wlink system dos name vfmode.exe file { vfmode.obj <binmode.obj> }

  Built three ways -- with no binmode.obj, with the one shipped in
  rel/lib286/dos (which is byte-identical to the SMALL model build), and
  with the large-model one out of the bld tree -- so the three answers can
  be compared side by side on one boot.
*/
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/stat.h>

/*
  Write three bytes, one of which is LF, and ask the file system how many
  landed.  3 means the stream is binary; 4 means the runtime turned the LF
  into CRLF, which is exactly what corrupted the transfer.
*/
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
main()
{
    printf("vfmode: _fmode=%04x  (O_TEXT=%04x O_BINARY=%04x)\n",
           (unsigned)_fmode, (unsigned)O_TEXT, (unsigned)O_BINARY);
    wtest("FMTA.TMP","w");              /* what zopeno() actually passes */
    wtest("FMTB.TMP","wb");             /* the control                   */
    return(0);
}
