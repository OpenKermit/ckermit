/*
  Unit tests for slotstate() and slotdir().  slotstate() records the IKSD
  session state and the current command in the INFO field of the
  database record dbrec[].  slotdir() records the current directory in
  the DIR field.  The record is written to a temporary database file.
*/
#include <check.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcker.h"
#include "ckcfnp.h"

int ikdbopen = 0;
/* Stubs for symbols that ckuusx.c's debug code refers to. */
int deblog = 0;
int debok = 0;
int debtim = 0;
void ztime(char ** s) { *s = ""; }
int debxlen = 54;
long ztmsec = -1L;
int zsout(int n, const char * s) { return 0; }
int zsoutl(int n, const char * s) { return 0; }
int zclose(int n) { return 0; }
char * ckdate(void) { return "20260101 00:00:00"; }

extern char dbrec[];
extern char * dbfile;
extern int mydbslot;

static char dbname[] = "/tmp/test_slotstate.XXXXXX";

static void
setup(void)
{
    int fd = mkstemp(dbname);
    ck_assert_int_ge(fd, 0);
    close(fd);
    dbfile = dbname;
    mydbslot = 0;
    ikdbopen = 1;
    memset(dbrec, 'X', DB_RECL);
}

static void
teardown(void)
{
    unlink(dbname);
    memcpy(dbname + strlen(dbname) - 6, "XXXXXX", 6);
}

/* Return a string of n copies of c.  The caller frees it. */

static char *
filled(int n, int c)
{
    char * s = malloc(n + 1);
    ck_assert_ptr_nonnull(s);
    memset(s, c, n);
    s[n] = '\0';
    return s;
}

START_TEST(test_slotstate_short_args_padded)
{
    int i;
    slotstate(1, "REMOTE CD", "/tmp", "");
    ck_assert_int_eq(memcmp(&dbrec[DB_INFO], "REMOTE CD /tmp ", 15), 0);
    for (i = 15; i < dB_INFO; i++)
      ck_assert_int_eq(dbrec[DB_INFO + i], ' ');
}
END_TEST

START_TEST(test_slotstate_arg_exactly_fills_field)
{
    /* "REMOTE CD " takes 10 bytes.  1014 bytes fill the rest. */
    char * s2 = filled(dB_INFO - 10, 'a');
    slotstate(1, "REMOTE CD", s2, "");
    ck_assert_int_eq(memcmp(&dbrec[DB_INFO], "REMOTE CD ", 10), 0);
    ck_assert_int_eq(memcmp(&dbrec[DB_INFO + 10], s2, dB_INFO - 10), 0);
    free(s2);
}
END_TEST

START_TEST(test_slotstate_long_arg_truncated)
{
    char * s2 = filled(dB_INFO + 100, 'b');
    slotstate(1, "REMOTE CD", s2, "third");
    ck_assert_int_eq(memcmp(&dbrec[DB_INFO], "REMOTE CD ", 10), 0);
    ck_assert_int_eq(memcmp(&dbrec[DB_INFO + 10], s2, dB_INFO - 10), 0);
    free(s2);
}
END_TEST

START_TEST(test_slotstate_long_first_arg_truncated)
{
    char * s1 = filled(dB_INFO + 1, 'c');
    slotstate(1, s1, "second", "third");
    ck_assert_int_eq(memcmp(&dbrec[DB_INFO], s1, dB_INFO), 0);
    free(s1);
}
END_TEST

START_TEST(test_slotdir_root_and_dir_padded)
{
    int i;
    slotdir("/anon", "/pub");
    ck_assert_int_eq(memcmp(&dbrec[DB_DIR], "/anon/pub", 9), 0);
    for (i = 9; i < dB_DIR; i++)
      ck_assert_int_eq(dbrec[DB_DIR + i], ' ');
    ck_assert_int_eq(dbrec[DB_INFO], 'X');
}
END_TEST

START_TEST(test_slotdir_long_root_stays_in_field)
{
    /* A root longer than the DIR field fills it and stops there. */
    int i;
    char * s1 = filled(dB_DIR + 476, 'r');
    slotdir(s1, "/pub");
    ck_assert_int_eq(memcmp(&dbrec[DB_DIR], s1, dB_DIR), 0);
    for (i = 0; i < dB_INFO; i++)
      ck_assert_int_eq(dbrec[DB_INFO + i], 'X');
    free(s1);
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite * s = suite_create("Kermit slotstate() Unit Tests");
    TCase * tc = tcase_create("core");

    tcase_add_checked_fixture(tc, setup, teardown);
    tcase_add_test(tc, test_slotstate_short_args_padded);
    tcase_add_test(tc, test_slotstate_arg_exactly_fills_field);
    tcase_add_test(tc, test_slotstate_long_arg_truncated);
    tcase_add_test(tc, test_slotstate_long_first_arg_truncated);
    tcase_add_test(tc, test_slotdir_root_and_dir_padded);
    tcase_add_test(tc, test_slotdir_long_root_stays_in_field);
    suite_add_tcase(s, tc);

    SRunner * sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    return failed ? 1 : 0;
}
