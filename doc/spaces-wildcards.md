# Working with Wildcards, Spaces in Filenames, and More

These topics are are all related to specifying filenames in C-Kermit.  Let's
dive in.

## Quoting a filename that contains a space

Kermit treats a bare space as the end of a filename. To include a
space in a filename, wrap the whole name in one of two delimiters:

- Braces: `{a file.txt}`
- Quotation marks (double quotes): `"a file.txt"`

Both work the same way in any command that takes a filename. Braces are always
available. Double quote wrapping can be turned off with `SET COMMAND
DOUBLEQUOTING OFF`, but is on by default.

Single quotes (apostrophes) don't help. `'a file.txt'` is read as two separate
words.

A backslash alone doesn't protect a space. `a\ file.txt` still splits into two
words. Braces or double quotes are the only way to include a space in a
filename.

To give several names with spaces to one `MGET` or `MSEND` command, wrap each
one separately:

```
mget {file one.txt} {file two.txt}
```

## Including a literal brace or quote character in a filename

If the filename itself contains a `{`, `}`, or `"` character, you need to escape
it with a backslash according to these rules:

- A double quote inside a name wrapped in braces needs no escaping: `{a
  "quoted" file.txt}` works fine.
- A double quote inside a name wrapped in double quotes must be escaped:
  `"a \"quoted\" file.txt"`.
- A *balanced* pair of literal braces inside a name wrapped in braces normally
  does not need escaping, except for the specific commands described below.

## Numeric character codes

A backslash followed by a number inserts a single character by its numeric code.
This applie anywhere Kermit interprets backslash codes, such as `ECHO` or an
`ASK` prompt.

- **Decimal** (the default): `\101` inserts the character whose decimal code
  is 101. You can also write it explicitly as `\d101` or `\D101`.
- **Octal**: `\o101` or `\O101` inserts the character 101 octal (65 decimal).
- **Hexadecimal**: `\x41` or `\X41` inserts the character 41 hex (65 decimal).
  Hex always takes exactly two digits.

Decimal and octal read up to three digits, stopping early if a
fourth digit would push the value past 255.  `\1015` reads as character 101 followed by a
literal `5`.

Where digit boundaries are ambiguous, wrap the number in braces. `\{10}1` is
character 10 followed by a literal `1`, while `\101` is character 101.  Braces
also apply to letter prefixes: `\{o101}`, `\{x41}`, `\{d101}`.

## Differences in Embedded Braces by Command

Whether a literal `{` or `}` in a filename must be escaped (`\{`, `\}`) or left bare (`{`,
`}`) depends on which command you're using:

| Command | Embedded `{` or `}` in the filename |
|---|---|
| `SEND`, `DIR`, `DELETE`, `RENAME`, `COPY`, `TYPE` | **Escape it**: `\{`, `\}` |
| `GET`, `MGET`, `REGET`, `RETRIEVE` | **Leave it bare**: `{`, `}` |
| `REMOTE DELETE`, `REMOTE DIRECTORY`, `REMOTE RENAME`, `REMOTE COPY` | **Leave it bare**: `{`, `}` |

Examples for a file named `file{one}.txt`:

```
send file\{one\}.txt
get file{one}.txt
remote delete file{one}.txt
```

The general rule is to try the bare form first for `GET`-family and `REMOTE`
commands, and the escaped form for everything else.

### Known Limitations

These date back many years in C-Kermit, and haven't yet been adjusted in the
C-Kermit 11 series due to the invasiveness of the fix or other considerstations,
though may be fixed in the future.

1. Renaming a file with a brace in its name directly to another specific name
(`rename file\{one\}.txt newname.txt`) does not currently work, even though the
name is unambiguous. Rename into a directory instead, keeping the same base name
(`rename file\{one\}.txt somedir`), which works correctly.

2. `MGET` cannot currently receive a name that needs an escaped, embedded double
quote when double quotes are used as the *outer* delimiter (e.g. `mget
"file\"one\".txt"`). Use braces as the outer delimiter for such a name instead
(`mget {file"one".txt}`), which works.

## Wildcards

A wildcard pattern can matche multiple filenames. Most commands that take a
filename also accept a wildcards.

Kermit may use its built-in wildcard engine, your shell's wildcard engine, or
wildcards can be disabled.  This is governed by `SET WILDCARD-EXPANSION`.

For more on how wildcards work and what they match, see the information under
`HELP WILDCARD` (or [in the help-reference manual](help-reference.md#wildcards))
for more details.  They are similar to Unix shell conventions.

To match wildcard characters literally, precede them with a backslash.  For
instance, `[a\-z]` matches the letter `a`, a literal hyphen, or `z`.  You can
instead turn wildcard matching off entirely with `SET WILDCARD-EXPANSION OFF`.

Because `{` and `}` are both wildcard and quoting syntax, they can be ambiguous.
Refer to the command table above for proper handling.
