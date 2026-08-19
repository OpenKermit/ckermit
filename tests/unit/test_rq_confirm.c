/*
  Unit tests for the SET RECEIVE CONFIRM helper function
  rq_under_root() in ckcfns.c.
*/
#include <check.h>
#include <string.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcfnp.h"

/*
  Stub debug() for linking with ckcfns.o.
*/
int deblog = 0;
int dodebug(int a, const char *b, const char *c, CK_OFF_T d) {
    return 0;
}

/* rq_under_root() */

START_TEST(test_under_root_descendant)
{
    ck_assert_int_eq(rq_under_root("/a/b","/a/b/c.txt"), 1);
    ck_assert_int_eq(rq_under_root("/a/b","/a/b/c/d.txt"), 1);
}
END_TEST

START_TEST(test_under_root_exact_match)
{
    ck_assert_int_eq(rq_under_root("/a/b","/a/b"), 1);
}
END_TEST

START_TEST(test_under_root_trailing_slash_on_root)
{
    ck_assert_int_eq(rq_under_root("/a/b/","/a/b/c.txt"), 1);
}
END_TEST

START_TEST(test_under_root_sibling_prefix_rejected)
{
    /* "/a/b" is a string-prefix of "/a/bc.txt" but not its directory
       parent; the path-separator boundary check must catch this. */
    ck_assert_int_eq(rq_under_root("/a/b","/a/bc.txt"), 0);
}
END_TEST

START_TEST(test_under_root_unrelated_path_rejected)
{
    ck_assert_int_eq(rq_under_root("/a/b","/x/y.txt"), 0);
}
END_TEST

START_TEST(test_under_root_empty_root_rejected)
{
    ck_assert_int_eq(rq_under_root("","/a/b"), 0);
    ck_assert_int_eq(rq_under_root(NULL,"/a/b"), 0);
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite * s = suite_create("Kermit SET RECEIVE CONFIRM helper Unit Tests");
    TCase * tc = tcase_create("core");

    tcase_add_test(tc, test_under_root_descendant);
    tcase_add_test(tc, test_under_root_exact_match);
    tcase_add_test(tc, test_under_root_trailing_slash_on_root);
    tcase_add_test(tc, test_under_root_sibling_prefix_rejected);
    tcase_add_test(tc, test_under_root_unrelated_path_rejected);
    tcase_add_test(tc, test_under_root_empty_root_rejected);
    suite_add_tcase(s, tc);

    SRunner * sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    return failed ? 1 : 0;
}
