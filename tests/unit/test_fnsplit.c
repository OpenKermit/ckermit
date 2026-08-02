/*
  Unit tests for fnsplit() and brquote(), the shared
  filespec-list splitter used by fnparse() (server-side GET-class
  request decoding) and the client-side canonical-quoting-for-the-wire
  helper added alongside it.
*/
#include <check.h>
#include <string.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcfnp.h"

#define BUFSZ 256
#define MAXTOK 8

/* fnsplit() */

START_TEST(test_fnsplit_simple_list)
{
    char text[] = "foo.txt bar.txt qux.dat";
    char * tokv[MAXTOK];
    char buf[BUFSZ];
    int n;

    n = fnsplit(text,tokv,MAXTOK,buf);
    ck_assert_int_eq(n, 3);
    ck_assert_str_eq(tokv[0], "foo.txt");
    ck_assert_str_eq(tokv[1], "bar.txt");
    ck_assert_str_eq(tokv[2], "qux.dat");
}
END_TEST

START_TEST(test_fnsplit_extra_spaces)
{
    char text[] = "  foo.txt    bar.txt  ";
    char * tokv[MAXTOK];
    char buf[BUFSZ];
    int n;

    n = fnsplit(text,tokv,MAXTOK,buf);
    ck_assert_int_eq(n, 2);
    ck_assert_str_eq(tokv[0], "foo.txt");
    ck_assert_str_eq(tokv[1], "bar.txt");
}
END_TEST

START_TEST(test_fnsplit_braced_name_with_spaces)
{
    char text[] = "foo.txt {bar baz.txt} qux.*";
    char * tokv[MAXTOK];
    char buf[BUFSZ];
    int n;

    n = fnsplit(text,tokv,MAXTOK,buf);
    ck_assert_int_eq(n, 3);
    ck_assert_str_eq(tokv[0], "foo.txt");
    ck_assert_str_eq(tokv[1], "bar baz.txt");
    ck_assert_str_eq(tokv[2], "qux.*");
}
END_TEST

START_TEST(test_fnsplit_multiple_braced_names)
{
    char text[] = "{file one} {file two}";
    char * tokv[MAXTOK];
    char buf[BUFSZ];
    int n;

    n = fnsplit(text,tokv,MAXTOK,buf);
    ck_assert_int_eq(n, 2);
    ck_assert_str_eq(tokv[0], "file one");
    ck_assert_str_eq(tokv[1], "file two");
}
END_TEST

START_TEST(test_fnsplit_nested_braces_preserved_literally)
{
    /* A single brace-quoted token may itself contain a balanced,
       unescaped pair; only the outermost pair is consumed as
       quoting. */
    char text[] = "{a {b} c} plain.txt";
    char * tokv[MAXTOK];
    char buf[BUFSZ];
    int n;

    n = fnsplit(text,tokv,MAXTOK,buf);
    ck_assert_int_eq(n, 2);
    ck_assert_str_eq(tokv[0], "a {b} c");
    ck_assert_str_eq(tokv[1], "plain.txt");
}
END_TEST

START_TEST(test_fnsplit_escaped_brace_inside_group)
{
    /* An unbalanced brace inside a {...} group must be escaped to be
       taken literally, exactly as brstrip()/setatm() require for the
       local command parser. */
    char text[] = "{foo\\}bar}";
    char * tokv[MAXTOK];
    char buf[BUFSZ];
    int n;

    n = fnsplit(text,tokv,MAXTOK,buf);
    ck_assert_int_eq(n, 1);
    ck_assert_str_eq(tokv[0], "foo}bar");
}
END_TEST

START_TEST(test_fnsplit_escaped_backslash_inside_group)
{
    char text[] = "{foo\\\\bar}";
    char * tokv[MAXTOK];
    char buf[BUFSZ];
    int n;

    n = fnsplit(text,tokv,MAXTOK,buf);
    ck_assert_int_eq(n, 1);
    ck_assert_str_eq(tokv[0], "foo\\bar");
}
END_TEST

START_TEST(test_fnsplit_unquoted_embedded_brace_not_at_start)
{
    /*
      A literal '{' that does not begin a token must not open a brace-quoted
      token partway through an unquoted token.
    */
    char text[] = "d{bal}ance.txt plain.txt";
    char * tokv[MAXTOK];
    char buf[BUFSZ];
    int n;

    n = fnsplit(text,tokv,MAXTOK,buf);
    ck_assert_int_eq(n, 2);
    ck_assert_str_eq(tokv[0], "d{bal}ance.txt");
    ck_assert_str_eq(tokv[1], "plain.txt");
}
END_TEST

START_TEST(test_fnsplit_overflow_does_not_corrupt_outv)
{
    /* More tokens than maxout: the true count is still returned, but
       outv[] is never written past maxout. */
    char text[] = "a b c d e";
    char * tokv[3];
    char buf[BUFSZ];
    int n;

    n = fnsplit(text,tokv,3,buf);
    ck_assert_int_eq(n, 5);
    ck_assert_str_eq(tokv[0], "a");
    ck_assert_str_eq(tokv[1], "b");
    ck_assert_str_eq(tokv[2], "c");
}
END_TEST

/* brquote() */

START_TEST(test_brquote_no_wrap_needed)
{
    char buf[BUFSZ];
    ck_assert_str_eq(brquote("foo.txt",buf,BUFSZ), "foo.txt");
}
END_TEST

START_TEST(test_brquote_wraps_name_with_space)
{
    char buf[BUFSZ];
    ck_assert_str_eq(brquote("file one.txt",buf,BUFSZ), "{file one.txt}");
}
END_TEST

START_TEST(test_brquote_wraps_leading_brace)
{
    char buf[BUFSZ];
    ck_assert_str_eq(brquote("{weird.txt",buf,BUFSZ), "{\\{weird.txt}");
}
END_TEST

START_TEST(test_brquote_escapes_embedded_delimiters_when_wrapping)
{
    char buf[BUFSZ];
    /* Has a space, so it needs wrapping; the embedded brace pair
       must come out escaped so fnsplit()'s depth counter doesn't
       misread it. */
    ck_assert_str_eq(brquote("d{bal}ance one.txt",buf,BUFSZ),
                      "{d\\{bal\\}ance one.txt}");
}
END_TEST

START_TEST(test_brquote_roundtrips_through_fnsplit)
{
    /* The real contract: whatever brquote() emits, fnsplit() must
       read back as the original name. */
    char qbuf[BUFSZ];
    char * tokv[MAXTOK];
    char sbuf[BUFSZ];
    char text[BUFSZ];
    int n;

    brquote("d{bal}ance one.txt",qbuf,BUFSZ);
    ckstrncpy(text,qbuf,BUFSZ);
    n = fnsplit(text,tokv,MAXTOK,sbuf);
    ck_assert_int_eq(n, 1);
    ck_assert_str_eq(tokv[0], "d{bal}ance one.txt");
}
END_TEST

START_TEST(test_brquote_roundtrips_multiple_names_through_fnsplit)
{
    /* The MGET wire format: several brquote()'d names joined with
       spaces in one line, split back apart by a single fnsplit()
       call. Only one of the two names needs wrapping. */
    char q1[BUFSZ], q2[BUFSZ], line[BUFSZ];
    char * tokv[MAXTOK];
    char sbuf[BUFSZ];
    int n;

    brquote("plain.txt",q1,BUFSZ);
    brquote("file two.txt",q2,BUFSZ);
    ckstrncpy(line,q1,BUFSZ);
    ckstrncat(line," ",BUFSZ);
    ckstrncat(line,q2,BUFSZ);

    n = fnsplit(line,tokv,MAXTOK,sbuf);
    ck_assert_int_eq(n, 2);
    ck_assert_str_eq(tokv[0], "plain.txt");
    ck_assert_str_eq(tokv[1], "file two.txt");
}
END_TEST

START_TEST(test_brquote_leading_brace_roundtrips_through_fnsplit)
{
    char qbuf[BUFSZ];
    char * tokv[MAXTOK];
    char sbuf[BUFSZ];
    char text[BUFSZ];
    int n;

    brquote("{weird.txt",qbuf,BUFSZ);
    ckstrncpy(text,qbuf,BUFSZ);
    n = fnsplit(text,tokv,MAXTOK,sbuf);
    ck_assert_int_eq(n, 1);
    ck_assert_str_eq(tokv[0], "{weird.txt");
}
END_TEST

START_TEST(test_brquote_roundtrips_backslash_with_space)
{
    /* A backslash alongside a space: already forces wrapping, so
       this direction always worked. */
    char qbuf[BUFSZ];
    char * tokv[MAXTOK];
    char sbuf[BUFSZ];
    char text[BUFSZ];
    int n;

    brquote("foo\\bar one.txt",qbuf,BUFSZ);
    ckstrncpy(text,qbuf,BUFSZ);
    n = fnsplit(text,tokv,MAXTOK,sbuf);
    ck_assert_int_eq(n, 1);
    ck_assert_str_eq(tokv[0], "foo\\bar one.txt");
}
END_TEST

START_TEST(test_brquote_roundtrips_bare_backslash)
{
    /* A backslash with no space and no leading brace: brquote() must
       still wrap it, or fnsplit()'s unquoted-token path (which always
       treats a bare backslash as an escape introducer) mangles the
       name. Two cases: "\b" isn't a recognized escape (used to come
       back with the backslash silently dropped); "\1" is a decimal
       escape (used to come back as a literal 0x01 byte). */
    char qbuf[BUFSZ];
    char * tokv[MAXTOK];
    char sbuf[BUFSZ];
    char text[BUFSZ];
    int n;

    brquote("foo\\bar.txt",qbuf,BUFSZ);
    ckstrncpy(text,qbuf,BUFSZ);
    n = fnsplit(text,tokv,MAXTOK,sbuf);
    ck_assert_int_eq(n, 1);
    ck_assert_str_eq(tokv[0], "foo\\bar.txt");

    brquote("foo\\1bar.txt",qbuf,BUFSZ);
    ckstrncpy(text,qbuf,BUFSZ);
    n = fnsplit(text,tokv,MAXTOK,sbuf);
    ck_assert_int_eq(n, 1);
    ck_assert_str_eq(tokv[0], "foo\\1bar.txt");
}
END_TEST

START_TEST(test_brquote_truncates_safely)
{
    char buf[6];
    /* "file one.txt" needs wrapping; with only 6 bytes to work with,
       this must truncate, not overflow. */
    brquote("file one.txt",buf,6);
    ck_assert_int_eq(strlen(buf), 5);
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite * s = suite_create("Kermit fnsplit()/brquote() Unit Tests");
    TCase * tc = tcase_create("core");

    tcase_add_test(tc, test_fnsplit_simple_list);
    tcase_add_test(tc, test_fnsplit_extra_spaces);
    tcase_add_test(tc, test_fnsplit_braced_name_with_spaces);
    tcase_add_test(tc, test_fnsplit_multiple_braced_names);
    tcase_add_test(tc, test_fnsplit_nested_braces_preserved_literally);
    tcase_add_test(tc, test_fnsplit_escaped_brace_inside_group);
    tcase_add_test(tc, test_fnsplit_escaped_backslash_inside_group);
    tcase_add_test(tc, test_fnsplit_unquoted_embedded_brace_not_at_start);
    tcase_add_test(tc, test_fnsplit_overflow_does_not_corrupt_outv);
    tcase_add_test(tc, test_brquote_no_wrap_needed);
    tcase_add_test(tc, test_brquote_wraps_name_with_space);
    tcase_add_test(tc, test_brquote_wraps_leading_brace);
    tcase_add_test(tc, test_brquote_escapes_embedded_delimiters_when_wrapping);
    tcase_add_test(tc, test_brquote_roundtrips_through_fnsplit);
    tcase_add_test(tc, test_brquote_roundtrips_multiple_names_through_fnsplit);
    tcase_add_test(tc, test_brquote_leading_brace_roundtrips_through_fnsplit);
    tcase_add_test(tc, test_brquote_roundtrips_backslash_with_space);
    tcase_add_test(tc, test_brquote_roundtrips_bare_backslash);
    tcase_add_test(tc, test_brquote_truncates_safely);
    suite_add_tcase(s, tc);

    SRunner * sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    return failed ? 1 : 0;
}
