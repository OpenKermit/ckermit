/*
  Unit tests for hasdotdot() in ckcfns.c
*/
#include <check.h>
#include <string.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcfnp.h"

/*
  debug() stub, needed for the same reason as the identical stubs in
  test_mpsafe.c/test_zfnqfp.c: hasdotdot() itself doesn't call
  debug(), but linking pulls in enough of ckcfns.o's other symbols
  (before --gc-sections prunes them) that the linker still wants it
  resolved.
*/
int deblog = 0;
int dodebug(int a, const char *b, const char *c, CK_OFF_T d) {
    return 0;
}

/* A ".." segment must be caught wherever it appears. */

START_TEST(test_bare_dotdot)
{
    ck_assert_int_eq(hasdotdot(".."), 1);
}
END_TEST

START_TEST(test_leading_dotdot_slash)
{
    ck_assert_int_eq(hasdotdot("../foo"), 1);
    ck_assert_int_eq(hasdotdot("../../etc/passwd"), 1);
}
END_TEST

START_TEST(test_trailing_slash_dotdot)
{
    ck_assert_int_eq(hasdotdot("foo/.."), 1);
    ck_assert_int_eq(hasdotdot("foo/bar/.."), 1);
}
END_TEST

START_TEST(test_embedded_slash_dotdot_slash)
{
    ck_assert_int_eq(hasdotdot("foo/../bar"), 1);
    ck_assert_int_eq(hasdotdot("a/b/../c/d"), 1);
}
END_TEST

START_TEST(test_multiple_dotdot_segments)
{
    ck_assert_int_eq(hasdotdot("a/../../b"), 1);
    ck_assert_int_eq(hasdotdot("../../../../etc/cron.d/evil"), 1);
}
END_TEST

/* Lookalikes that are not a ".." path segment must be let through. */

START_TEST(test_filename_with_embedded_dots_allowed)
{
    ck_assert_int_eq(hasdotdot("filename..doc"), 0);
    ck_assert_int_eq(hasdotdot("foo..bar"), 0);
}
END_TEST

START_TEST(test_dotdot_prefix_or_suffix_of_segment_allowed)
{
    /* A segment that merely starts or ends with ".." but isn't
       exactly ".." is an ordinary filename character, not a path
       traversal attempt. */
    ck_assert_int_eq(hasdotdot("..foo"), 0);
    ck_assert_int_eq(hasdotdot("foo.."), 0);
    ck_assert_int_eq(hasdotdot("dir/..foo/bar"), 0);
    ck_assert_int_eq(hasdotdot("dir/foo../bar"), 0);
}
END_TEST

START_TEST(test_three_or_more_dots_allowed)
{
    ck_assert_int_eq(hasdotdot("..."), 0);
    ck_assert_int_eq(hasdotdot("a/.../b"), 0);
}
END_TEST

/* Ordinary safe relative paths, the common recursive-transfer case. */

START_TEST(test_ordinary_relative_paths_allowed)
{
    ck_assert_int_eq(hasdotdot("ckermit/android.mk"), 0);
    ck_assert_int_eq(hasdotdot("a/b/c"), 0);
    ck_assert_int_eq(hasdotdot("file.txt"), 0);
    ck_assert_int_eq(hasdotdot(""), 0);
}
END_TEST

/* Single "." segments are a no-op for path depth, not a traversal. */

START_TEST(test_single_dot_segment_allowed)
{
    ck_assert_int_eq(hasdotdot("./foo"), 0);
    ck_assert_int_eq(hasdotdot("foo/./bar"), 0);
    ck_assert_int_eq(hasdotdot("."), 0);
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite * s = suite_create("Kermit hasdotdot() Unit Tests");
    TCase * tc = tcase_create("core");

    tcase_add_test(tc, test_bare_dotdot);
    tcase_add_test(tc, test_leading_dotdot_slash);
    tcase_add_test(tc, test_trailing_slash_dotdot);
    tcase_add_test(tc, test_embedded_slash_dotdot_slash);
    tcase_add_test(tc, test_multiple_dotdot_segments);
    tcase_add_test(tc, test_filename_with_embedded_dots_allowed);
    tcase_add_test(tc, test_dotdot_prefix_or_suffix_of_segment_allowed);
    tcase_add_test(tc, test_three_or_more_dots_allowed);
    tcase_add_test(tc, test_ordinary_relative_paths_allowed);
    tcase_add_test(tc, test_single_dot_segment_allowed);
    suite_add_tcase(s, tc);

    SRunner * sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    return failed ? 1 : 0;
}
