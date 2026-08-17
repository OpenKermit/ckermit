/*
  Unit tests for fpformat() in ckuus4.c, the floating-point-to-string
  formatter behind \ffpround() and related functions.
*/
#include <check.h>
#include <string.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcfnp.h"

/* debug() macro support: deblog=0 means dodebug() is never actually
   called, but the symbol must still exist for the linker. */
int deblog = 0;
int dodebug(int f, char *s1, char *s2, CK_OFF_T n) { return 0; }

START_TEST(test_fpformat_simple)
{
    char * s = fpformat(3.14159, 2, 1);
    ck_assert_str_eq(s, "3.14");
}
END_TEST

START_TEST(test_fpformat_zero)
{
    char * s = fpformat(0.0, 2, 1);
    ck_assert_str_eq(s, "0.00");
}
END_TEST

START_TEST(test_fpformat_negative)
{
    char * s = fpformat(-3.14159, 2, 1);
    ck_assert_str_eq(s, "-3.14");
}
END_TEST

/*
  Rounding 999.999 to 2 places crosses an order-of-magnitude
  boundary where a 3-digit integer part becomes 4-digit.
*/
START_TEST(test_fpformat_crosses_magnitude_boundary)
{
    char * s = fpformat(999.999, 2, 1);
    ck_assert_str_eq(s, "1000.00");
}
END_TEST

/*
  Rounding 99.995 to 2 places crosses an order-of-magnitude
  boundary where a 2-digit integer part becomes 3-digit.
*/
START_TEST(test_fpformat_crosses_magnitude_boundary_2)
{
    char * s = fpformat(99.995, 2, 1);
    ck_assert_str_eq(s, "100.00");
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite * s;
    TCase * tc;

    /* fpformat() depends on fp_digits and fp_rounding, initialized
       by initfloat(). Without initfloat(), fp_digits remains zero
       and fpformat() zeroes all output digits. */
    initfloat();

    s = suite_create("Kermit fpformat() Unit Tests");
    tc = tcase_create("core");

    tcase_add_test(tc, test_fpformat_simple);
    tcase_add_test(tc, test_fpformat_zero);
    tcase_add_test(tc, test_fpformat_negative);
    tcase_add_test(tc, test_fpformat_crosses_magnitude_boundary);
    tcase_add_test(tc, test_fpformat_crosses_magnitude_boundary_2);
    suite_add_tcase(s, tc);

    SRunner * sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    return failed ? 1 : 0;
}
