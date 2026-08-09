/*
  vmatch.c -- throwaway probe, not part of the port.

  Two questions the traces in ckvictor.c cannot reach, both inside modules
  that must not be edited:

    1. What does libdos-m's stat() say about a WILDCARD path?  zchki() in
       ckufio.c stats its argument before anything else, and doarg() in
       ckuusy.c treats "it is a directory" (-2) as a file it should count
       but not send -- which prints "No files for -s" and looks exactly
       like an expansion that matched nothing.

    2. What does ckmatch() answer for the actual pattern and the actual
       name, compiled by this toolchain?  The Watcom build's debug log says
       1; nothing has asked the gcc build.

  Links against the port's own ckclib.o so it is the same code, not a copy.
*/
#include <stdio.h>
#include <sys/stat.h>
#include <sys/types.h>

extern int ckmatch(char * pattern, char * string, int icase, int opts);

/* ckclib.c reaches for these; the real ones live in modules this probe
   deliberately does not link. */
int matchdot = 0;
int dblflag = 0, dbldashf = 0;

static void
st(char * p)
{
    struct stat b;
    int rc = stat(p,&b);
    printf("stat(\"%s\") rc=%d isdir=%d size=%ld\n",
           p, rc, rc ? -1 : (S_ISDIR(b.st_mode) ? 1 : 0),
           rc ? 0L : (long)b.st_size);
}

static void
m(char * pat, char * str, int opts)
{
    printf("ckmatch(\"%s\",\"%s\",1,%d) = %d\n",
           pat, str, opts, ckmatch(pat,str,1,opts));
}

int
main()
{
    st(".");
    st("./");
    st(".\\");
    st("*.TXT");
    st("TESTFILE.TXT");
    st("NOSUCH.XYZ");
    st("TEST");
    m("*.TXT","TESTFILE.TXT",2);
    m("*.TXT","TESTFILE.TXT",0);
    m("*.TXT","KTEST.BAT",2);
    m("*","TESTFILE.TXT",2);
    return(0);
}

/* ckround() in ckclib.c wants this; nothing here calls ckround(). */
int fp_digits = 7;
