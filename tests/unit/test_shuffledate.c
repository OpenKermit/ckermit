/*
  Unit tests for shuffledate() in ckucmd.c, the date-format
  reshuffler behind \fcvtdate() and related functions.
*/
#include <check.h>
#include <string.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcfnp.h"

/* debug() macro support: deblog=0 ensures dodebug() is not called,
   but the symbol must exist for the linker. */
int deblog = 0;
int dodebug(int f, char *s1, char *s2, CK_OFF_T n) { return 0; }

/* printf() is defined to ckxprintf(); lookup() references it for
   out-of-order table checks under DEBUG. */
int ckxprintf(const char *format, ...) { return 0; }

/* Stub for ztime(). shuffledate() calls ckdate() when its argument
   is empty, which requires ztime(). */
void ztime(char **s) { *s = "Thu Jan  1 00:00:00 1970"; }

/* Disable locale month lookups in shuffledate(). */
int nolocale = 1;
char * locale_monthname(int month, int fc) { return NULL; }

/* lookup() result cache stubs. Setting lusize to 0 disables cache
   lookups without linking ckuus5.c. */
int lusize = 0;
char * lucmd[1];
int luval[1];
int luidx[1];
struct keytab * lutab[1];

/* shuffledate() with opt==4 expects normalized "yyyymmdd" or
   "yyyymmdd hh:mm:ss" input. */

START_TEST(test_shuffledate_well_formed_with_time)
{
    char buf[32];
    char * s;
    strcpy(buf, "20051126 11:10:34");
    s = shuffledate(buf, 4);
    ck_assert_str_eq(s, "Sat Nov 26 11:10:34 2005");
}
END_TEST

START_TEST(test_shuffledate_date_only_no_time_requested)
{
    /* Negative opt selects date-only output. Format -4 omits the space
       between day and year ("Sat Nov 262005"). */
    char buf[32];
    char * s;
    strcpy(buf, "20051126 11:10:34");
    s = shuffledate(buf, -4);
    ck_assert_str_eq(s, "Sat Nov 262005");
}
END_TEST

/*
  When trailing whitespace is stripped from a date-only string,
  shuffledate() pads the default time "00:00:00".
*/
START_TEST(test_shuffledate_date_only_strips_trailing_crlf)
{
    char buf[32];
    char * s;
    strcpy(buf, "20051126\r\n");
    s = shuffledate(buf, 4);
    ck_assert_str_eq(s, "Sat Nov 26 00:00:00 2005");
}
END_TEST

START_TEST(test_shuffledate_date_only_strips_trailing_space)
{
    char buf[32];
    char * s;
    strcpy(buf, "20051126   ");
    s = shuffledate(buf, 4);
    ck_assert_str_eq(s, "Sat Nov 26 00:00:00 2005");
}
END_TEST

/*
  Whitespace-only input strips to the start of the buffer without
  out-of-bounds access and returns the unconverted input string.
*/
START_TEST(test_shuffledate_all_whitespace_no_oob)
{
    char buf[32];
    char * s;
    strcpy(buf, "        \r\n\t   ");  /* 8 spaces, CR, LF, tab, 3 spaces */
    s = shuffledate(buf, 4);
    ck_assert_str_eq(s, buf);
}
END_TEST

/*
  Invalid month values (< 1 or > 12) return the original string
  without out-of-bounds lookups in moname[].
*/
START_TEST(test_shuffledate_invalid_month_zero)
{
    char buf[32];
    char * s;
    strcpy(buf, "20050026");  /* Month digits "00" -> mm == 0 */
    s = shuffledate(buf, 4);
    ck_assert_str_eq(s, buf);
}
END_TEST

START_TEST(test_shuffledate_invalid_month_too_large)
{
    char buf[32];
    char * s;
    strcpy(buf, "20051326");  /* Month digits "13" -> mm == 13 */
    s = shuffledate(buf, 4);
    ck_assert_str_eq(s, buf);
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite * s;
    TCase * tc;

    s = suite_create("Kermit shuffledate() Unit Tests");
    tc = tcase_create("core");

    tcase_add_test(tc, test_shuffledate_well_formed_with_time);
    tcase_add_test(tc, test_shuffledate_date_only_no_time_requested);
    tcase_add_test(tc, test_shuffledate_date_only_strips_trailing_crlf);
    tcase_add_test(tc, test_shuffledate_date_only_strips_trailing_space);
    tcase_add_test(tc, test_shuffledate_all_whitespace_no_oob);
    tcase_add_test(tc, test_shuffledate_invalid_month_zero);
    tcase_add_test(tc, test_shuffledate_invalid_month_too_large);
    suite_add_tcase(s, tc);

    SRunner * sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    return failed ? 1 : 0;
}
