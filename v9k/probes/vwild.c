/*
  vwild.c -- a throwaway probe, not part of the port.

  PORTING.md SS15's top open item is that "-s *.COM" expands to nothing
  while "-s FILE" works.  ckufio.c's traverse() reaches the disk as
  opendir("./"), and ckvictor.c turns that into an INT 21h FindFirst on
  ".\*.*".  A FAT ROOT directory has no "." entry, so the guess is that
  DOS cannot resolve the "." component there and answers "path not found".

  This asks DOS directly, in the root and in a subdirectory, so the answer
  is a measurement instead of a guess.  Built with Open Watcom, but the
  question it settles is the same one the gcc build's hand-written
  FindFirst asks -- it is DOS being probed here, not a C library.

    wcl -bcl=dos -ml vwild.c
*/
#include <stdio.h>
#include <string.h>
#include <dos.h>
#include <direct.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <dirent.h>

static void
ff(char * pat)
{                                       /* Raw INT 21h 4Eh */
    struct find_t f;
    unsigned rc;

    rc = _dos_findfirst(pat,_A_NORMAL|_A_HIDDEN|_A_SYSTEM|_A_SUBDIR,&f);
    if (rc == 0)
      printf("  FF %-12s rc=0  first=%s\n",pat,f.name);
    else
      printf("  FF %-12s rc=%u (dos error)\n",pat,rc);
}

static void
od(char * path)
{                                       /* The library's opendir() */
    DIR * d;
    struct dirent * e;
    int n = 0;
    char first[16];

    first[0] = '\0';
    d = opendir(path);
    if (!d) {
        printf("  OD \"%s\" NULL\n",path);
        return;
    }
    while ((e = readdir(d))) {
        if (!first[0]) strcpy(first,e->d_name);
        n++;
    }
    closedir(d);
    printf("  OD \"%s\" n=%d first=%s\n",path,n,first);
}

static void
st(char * path)
{
    struct stat b;
    int rc = stat(path,&b);
    printf("  ST \"%s\" rc=%d mode=%04x isdir=%d\n",
           path,rc,rc ? 0 : (unsigned)b.st_mode,
           rc ? -1 : (S_ISDIR(b.st_mode) ? 1 : 0));
}

static void
probe(char * where)
{
    char cwd[80];

    cwd[0] = '\0';
    getcwd(cwd,sizeof(cwd));
    printf("== %s (cwd=%s)\n",where,cwd);
    ff("*.*");
    ff(".\\*.*");
    ff("./*.*");
    ff("*.COM");
    ff(".\\*.COM");
    st(".");
    st("./");
    st(".\\");
    od("");
    od(".");
    od("./");
    od(".\\");
}

int
main()
{
    probe("ROOT");
    if (chdir("\\TEST") == 0)
      probe("SUBDIR");
    else
      printf("== SUBDIR: chdir \\TEST failed\n");
    return(0);
}
