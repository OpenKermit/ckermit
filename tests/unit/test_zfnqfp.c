/*
  Unit tests for zfnqfp() in ckufio.c, which resolves a filename to
  a fully qualified absolute pathname.  It has two internal paths:
  realpath(), used when the file exists, and a do-it-yourself "."/
  ".." collapser used as a fallback when realpath() fails (most
  commonly because the target does not exist yet).

  These tests also guard related fixes:

   - realpath() is called as realpath(s, NULL) so the C library
     allocates the result buffer itself, rather than writing into a
     fixed-size local buffer sized from MAXPATHLEN/CKMAXPATH.

   - The do-it-yourself fallback collapses "." and ".." in place
     into the caller's own buffer instead of a separate fixed-size
     scratch buffer.
*/
#include <check.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcasc.h"
#include "ckcfnp.h"

/*
  zfnqfp() and the functions it calls (isdir(), zgtdir(),
  tilde_expand(), whoami()) don't themselves need these, but linking
  them pulls in enough of ckufio.o's other symbols (before
  --gc-sections prunes them) that the linker still wants these
  resolved.
*/
int deblog = 0;
int dodebug(int a, char *b, char *c, CK_OFF_T d) {
    return 0;
}
int inserver = 0;
char uidbuf[UIDBUFLEN] = { NUL, NUL };
UID_T
real_uid(void) {
    return getuid();
}

static char tdir[CKMAXPATH];

static void
setup(void)
{
    char cmd[CKMAXPATH + 32];
    strcpy(tdir, "/tmp/zfnqfpXXXXXX");
    ck_assert_ptr_nonnull(mkdtemp(tdir));
    snprintf(cmd, sizeof(cmd), "mkdir -p '%s/a/b/c'", tdir);
    ck_assert_int_eq(system(cmd), 0);
}

static void
teardown(void)
{
    char cmd[CKMAXPATH + 16];
    snprintf(cmd, sizeof(cmd), "rm -rf '%s'", tdir);
    system(cmd);
}

/* realpath()-success path: existing directory, "." and ".."
   components, redundant slashes, all collapsed by the OS. */
START_TEST(test_existing_path_dot_dotdot)
{
    char in[CKMAXPATH], buf[CKMAXPATH], expect[CKMAXPATH];
    snprintf(in, sizeof(in), "%s/a/./b/../b//c", tdir);
    snprintf(expect, sizeof(expect), "%s/a/b/c/", tdir);

    struct zfnfp *r = zfnqfp(in, sizeof(buf), buf);
    ck_assert_ptr_nonnull(r);
    ck_assert_str_eq(buf, expect);
    ck_assert_ptr_eq(r->fpath, buf);
}
END_TEST

/* Existing plain file: fname should point at the basename within
   the returned buffer, not just anywhere containing that text. */
START_TEST(test_existing_file_fname_pointer)
{
    static const char base[] = "leaf.txt";
    char path[CKMAXPATH], buf[CKMAXPATH];
    snprintf(path, sizeof(path), "%s/a/b/c/%s", tdir, base);
    FILE *f = fopen(path, "w");
    ck_assert_ptr_nonnull(f);
    fclose(f);

    struct zfnfp *r = zfnqfp(path, sizeof(buf), buf);
    ck_assert_ptr_nonnull(r);
    ck_assert_str_eq(r->fname, base);
    ck_assert_int_eq(r->fname - r->fpath, (int)strlen(buf) - (int)strlen(base));
}
END_TEST

/* Fallback path: nonexistent leaf forces realpath() to fail, so
   zfnqfp() must fall back to the do-it-yourself "."/".." collapse.
   Checks the collapse is still correct there too. */
START_TEST(test_nonexistent_path_dot_dotdot)
{
    char in[CKMAXPATH], buf[CKMAXPATH], expect[CKMAXPATH];
    snprintf(in, sizeof(in), "%s/a/b/c/../../nonexistent_zz/../x", tdir);
    snprintf(expect, sizeof(expect), "%s/a/x", tdir);

    struct zfnfp *r = zfnqfp(in, sizeof(buf), buf);
    ck_assert_ptr_nonnull(r);
    ck_assert_str_eq(buf, expect);
}
END_TEST

/* A buffer too small for the resolved (existing) path must yield
   NULL, not a truncated result. Also exercises the free(rp) cleanup
   on the "too long" branch after realpath(s, NULL). */
START_TEST(test_buffer_too_small_existing)
{
    char in[CKMAXPATH], buf[4];
    snprintf(in, sizeof(in), "%s/a/b/c", tdir);
    struct zfnfp *r = zfnqfp(in, sizeof(buf), buf);
    ck_assert_ptr_null(r);
}
END_TEST

/*
  Regression test for the removal of the fixed-size "zfntmp" scratch
  buffer from the do-it-yourself fallback.

  Build a nonexistent path (so realpath() fails and the fallback
  runs) long enough to need a large buflen, and pass a buflen far
  bigger than the old scratch buffer (about MAXPATHLEN+4, ~4100
  bytes on Linux).
 
  That's comparable to what TMPBUFSIZ/LINBUFSIZ/FNVALL
  callers elsewhere in the codebase actually pass.  Before that
  commit, this overflows the old fixed buffer and segfaults;
  libcheck runs each test in a forked child by default, so the
  crash is reported as a test failure rather than taking down the
  whole suite.
*/
START_TEST(test_fallback_large_buflen_no_overflow)
{
    int buflen = 20000;
    int nseg = 1800;
    char *in = malloc(buflen);
    char *buf = malloc(buflen);
    char *expect = malloc(buflen);
    char *p;
    int i;

    ck_assert_ptr_nonnull(in);
    ck_assert_ptr_nonnull(buf);
    ck_assert_ptr_nonnull(expect);

    p = in;
    p += sprintf(p, "%s", tdir);
    for (i = 0; i < nseg; i++)
      p += sprintf(p, "/./seg");
    sprintf(p, "/does_not_exist_zz");

    p = expect;
    p += sprintf(p, "%s", tdir);
    for (i = 0; i < nseg; i++)
      p += sprintf(p, "/seg");
    sprintf(p, "/does_not_exist_zz");

    struct zfnfp *r = zfnqfp(in, buflen, buf);
    ck_assert_ptr_nonnull(r);
    ck_assert_str_eq(buf, expect);

    free(in);
    free(buf);
    free(expect);
}
END_TEST

/*
  CKMAXPATH must resolve to a real, positive size and, on this
  platform.
*/
START_TEST(test_ckmaxpath_tracks_path_max)
{
#ifdef PATH_MAX
    ck_assert_int_eq(CKMAXPATH, PATH_MAX);
#endif
    ck_assert_int_gt(CKMAXPATH, 0);
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite *s = suite_create("Kermit zfnqfp() Unit Tests");
    TCase *tc = tcase_create("core");

    tcase_add_checked_fixture(tc, setup, teardown);
    tcase_add_test(tc, test_existing_path_dot_dotdot);
    tcase_add_test(tc, test_existing_file_fname_pointer);
    tcase_add_test(tc, test_nonexistent_path_dot_dotdot);
    tcase_add_test(tc, test_buffer_too_small_existing);
    tcase_add_test(tc, test_fallback_large_buflen_no_overflow);
    tcase_add_test(tc, test_ckmaxpath_tracks_path_max);
    suite_add_tcase(s, tc);

    SRunner *sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    return failed ? 1 : 0;
}
