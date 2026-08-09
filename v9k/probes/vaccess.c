/*
  vaccess.c -- a throwaway probe, not part of the port.

  PORTING.md SS16h: RECEIVE fails with the protocol error "Write access
  denied".  ckufio.c's zchko() creates the incoming file, deletes it again,
  and THEN asks access(".",W_OK) whether it is allowed to create files in
  the directory it just created one in.  On the Victor that last call
  returns -1 with errno 6 (EACCES) and the transfer dies.

  Open Watcom's access() is two lines (bld/clib/file/c/accss.c):

      if (_dos_getfileattr(path,&attrs)) return(-1);
      if ((attrs & _A_RDONLY) && pmode == W_OK) return(EACCES);
      return(0);

  so EACCES can come from EITHER half -- INT 21h AH=43h failing outright,
  or succeeding and reporting the read-only bit -- and the fix differs.
  This asks DOS both questions separately, in the root and in a
  subdirectory, so the answer is a measurement instead of a guess.

  vwild.c already established that Watcom's stat() answers "." here while
  libdos-m's did not (SS16f cause 3); stat() is repeated below only so the
  two calls can be compared side by side on the same run.

    wcl -bcl=dos -ml vaccess.c
*/
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <dos.h>
#include <direct.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>

/*
  One path, every question.  getfileattr is the call access() is built on,
  so its rc and its attribute word are printed raw -- that is the thing in
  dispute.  access() is then asked all three modes, because zchko() uses
  W_OK and zchki() uses R_OK and they need not agree.
*/
static void
ask(char * path)
{
    unsigned attrs = 0xFFFF;
    unsigned rc;
    int a_f, e_f, a_w, e_w, a_r, e_r, s_rc;
    struct stat b;

    rc = _dos_getfileattr(path,&attrs);

    errno = 0; a_f = access(path,F_OK); e_f = errno;
    errno = 0; a_w = access(path,W_OK); e_w = errno;
    errno = 0; a_r = access(path,R_OK); e_r = errno;

    s_rc = stat(path,&b);

    printf("  [%-14s] GFA rc=%u attr=%04x | F_OK=%d/%d W_OK=%d/%d R_OK=%d/%d"
           " | stat=%d isdir=%d\n",
           path, rc, attrs,
           a_f, e_f, a_w, e_w, a_r, e_r,
           s_rc, s_rc ? -1 : (S_ISDIR(b.st_mode) ? 1 : 0));
}

static void
probe(char * where)
{
    char cwd[80];

    cwd[0] = '\0';
    getcwd(cwd,sizeof(cwd));
    printf("== %s (cwd=%s)\n",where,cwd);
    ask(".");
    ask("./");
    ask(".\\");
    ask("");
    ask("\\");
    ask("A:\\");
    ask("A:.");
    ask("TEST");                        /* a named subdirectory */
    ask("TESTFILE.TXT");                /* a file that exists   */
    ask("NOSUCH.XYZ");                  /* one that does not    */
}

int
main()
{
    printf("vaccess: EACCES is %d on this runtime\n",EACCES);
    probe("ROOT");
    if (chdir("\\TEST") == 0)
      probe("SUBDIR");
    else
      printf("== SUBDIR: chdir \\TEST failed\n");
    return(0);
}
