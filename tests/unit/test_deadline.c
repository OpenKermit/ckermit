/*
  Unit tests for ck_deadline_set(), ck_deadline_remaining_ms() and
  ck_deadline_expired() in ckutio.c.

  A deadline far in the future must read as far away and not
  expired.  With a 32-bit time_t, the current time plus the timeout
  exceeds the largest time_t.  With a 32-bit long, the remaining
  milliseconds exceed the largest long.  Both hold on every
  platform, so these tests run everywhere.
*/
#include <check.h>
#include <limits.h>
#include <stdlib.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"

VOID ck_deadline_set(int);
long ck_deadline_remaining_ms(void);
int ck_deadline_expired(void);

/* 24 days in milliseconds.  It fits a 32-bit long. */
#define MS_24_DAYS (24L * 24L * 60L * 60L * 1000L)

START_TEST(test_deadline_short)
{
    long ms;
    ck_deadline_set(2);
    ms = ck_deadline_remaining_ms();
    ck_assert(ms > 1000L && ms <= 2000L);
    ck_assert_int_eq(ck_deadline_expired(), 0);
}
END_TEST

/* 999999999 seconds is about 31.7 years. */
START_TEST(test_deadline_past_32_bit_time_t)
{
    ck_deadline_set(999999999);
    ck_assert(ck_deadline_remaining_ms() >= MS_24_DAYS);
    ck_assert_int_eq(ck_deadline_expired(), 0);
}
END_TEST

START_TEST(test_deadline_int_max)
{
    ck_deadline_set(INT_MAX);
    ck_assert(ck_deadline_remaining_ms() >= MS_24_DAYS);
    ck_assert_int_eq(ck_deadline_expired(), 0);
}
END_TEST

/* 30 days of milliseconds overflows a 32-bit long. */
START_TEST(test_deadline_past_32_bit_long_ms)
{
    ck_deadline_set(30 * 24 * 60 * 60);
    ck_assert(ck_deadline_remaining_ms() >= MS_24_DAYS);
    ck_assert_int_eq(ck_deadline_expired(), 0);
}
END_TEST

/* The remaining time must be a timeout every select() accepts. */
START_TEST(test_deadline_select_cap)
{
    ck_deadline_set(INT_MAX);
    ck_assert(ck_deadline_remaining_ms() / 1000L <= CK_SELECT_MAXSECS);
}
END_TEST

START_TEST(test_deadline_cleared)
{
    ck_deadline_set(0);
    ck_assert_int_eq(ck_deadline_expired(), 0);
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite *s = suite_create("Kermit ck_deadline Unit Tests");
    TCase *tc = tcase_create("core");

    tcase_add_test(tc, test_deadline_short);
    tcase_add_test(tc, test_deadline_past_32_bit_time_t);
    tcase_add_test(tc, test_deadline_int_max);
    tcase_add_test(tc, test_deadline_past_32_bit_long_ms);
    tcase_add_test(tc, test_deadline_select_cap);
    tcase_add_test(tc, test_deadline_cleared);
    suite_add_tcase(s, tc);

    SRunner *sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);
    return (failed == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
