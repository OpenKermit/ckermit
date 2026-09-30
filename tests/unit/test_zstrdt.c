/*
  Unit tests for zstrdt() and zlocaltime() in ckufio.c.

  zstrdt() converts a "yyyymmdd hh:mm:ss" local date to a time_t.
  zlocaltime() converts the same format from GMT to local time.

  Dates up to the last second of a signed 32-bit time_t are checked
  on every platform.  Later dates are checked only when time_t is 8
  bytes.  Both matter where long is 32 bits and time_t is 64 bits.
*/
#include <check.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcasc.h"
#include "ckcfnp.h"

/* Symbols that linking ckufio.o still needs after --gc-sections. */
int deblog = 0;
int dodebug(int a, const char *b, const char *c, CK_OFF_T d) {
    return 0;
}
int inserver = 0;
char uidbuf[UIDBUFLEN] = { NUL, NUL };
UID_T
real_uid(void) {
    return getuid();
}

static void
set_tz(const char *tz)
{
    ck_assert_int_eq(setenv("TZ", tz, 1), 0);
    tzset();
}

/* Call zstrdt() on a string constant. */
static time_t
strdt(const char *date)
{
    char buf[32];
    ckstrncpy(buf, (char *)date, sizeof(buf));
    return zstrdt(buf, (int)strlen(buf));
}

/* Call zlocaltime() on a string constant. */
static char *
localtm(const char *date)
{
    static char buf[32];
    ckstrncpy(buf, (char *)date, sizeof(buf));
    return zlocaltime(buf);
}

START_TEST(test_zstrdt_utc)
{
    set_tz("UTC");
    ck_assert(strdt("19700101 00:00:00") == (time_t)0);
    ck_assert(strdt("20010909 01:46:40") == (time_t)1000000000L);
    ck_assert(strdt("20370615 12:00:00") == (time_t)2128680000L);
    ck_assert(strdt("20380119 03:14:07") == (time_t)2147483647L);
}
END_TEST

/* The date string is local time, so a zone west of GMT adds its
   offset.  June in EST5EDT also applies the daylight saving hour. */
START_TEST(test_zstrdt_local)
{
    set_tz("EST5");
    ck_assert(strdt("20380118 22:14:07") == (time_t)2147483647L);
    set_tz("EST5EDT");
    ck_assert(strdt("20370615 12:00:00") == (time_t)2128694400L);
}
END_TEST

START_TEST(test_zstrdt_rejects)
{
    set_tz("UTC");
    ck_assert(strdt("19650615 12:00:00") == (time_t)-1);
    ck_assert(strdt("20370615 12:00") == (time_t)-1);
    ck_assert(strdt("20371315 12:00:00") == (time_t)-1);
}
END_TEST

START_TEST(test_zstrdt_after_2038)
{
    if (sizeof(time_t) < 8)
      return;
    set_tz("UTC");
    ck_assert(strdt("20380119 03:14:08") ==
              (time_t)2147483647L + (time_t)1);
    ck_assert(strdt("21060207 06:28:16") ==
              (time_t)4294967295UL + (time_t)1);
    ck_assert(strdt("21500615 12:00:00") ==
              (time_t)5694580800LL);
}
END_TEST

START_TEST(test_zlocaltime)
{
    char *p;
    set_tz("EST5");
    p = localtm("20370615 12:00:00");
    ck_assert_ptr_nonnull(p);
    ck_assert_str_eq(p, "20370615 07:00:00");
    p = localtm("20380119 03:14:07");
    ck_assert_ptr_nonnull(p);
    ck_assert_str_eq(p, "20380118 22:14:07");
}
END_TEST

START_TEST(test_zlocaltime_after_2038)
{
    char *p;
    if (sizeof(time_t) < 8)
      return;
    set_tz("EST5");
    p = localtm("21500615 12:00:00");
    ck_assert_ptr_nonnull(p);
    ck_assert_str_eq(p, "21500615 07:00:00");
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite *s = suite_create("Kermit zstrdt() Unit Tests");
    TCase *tc = tcase_create("core");

    tcase_add_test(tc, test_zstrdt_utc);
    tcase_add_test(tc, test_zstrdt_local);
    tcase_add_test(tc, test_zstrdt_rejects);
    tcase_add_test(tc, test_zstrdt_after_2038);
    tcase_add_test(tc, test_zlocaltime);
    tcase_add_test(tc, test_zlocaltime_after_2038);
    suite_add_tcase(s, tc);

    SRunner *sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);
    return (failed == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
