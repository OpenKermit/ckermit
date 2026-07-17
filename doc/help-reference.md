# C-Kermit Help Reference

Generated from a running kermit build by `tools/gen_help_reference.py`. Do not edit by hand. 

## Introductory Material

### INTRO

```
Welcome to UNIX C-Kermit communications software for:
 . Error-free and efficient file transfer
 . Terminal connection
 . Script programming
 . International character set conversion
 . Numeric and alphanumeric paging
 
Supporting:
 . Serial connections, direct or dialed.
 . Automatic modem dialing
 . TCP/IP network connections:
   - Telnet sessions
   - SSH connections via external agent
   - Rlogin sessions
   - FTP sessions
   - HTTP 1.1 sessions
   - Internet Kermit Service
 
While typing commands, you may use the following special characters:
 . DEL, RUBOUT, BACKSPACE, CTRL-H: Delete the most recent character typed.
 . CTRL-W:      Delete the most recent word typed.
 . CTRL-U:      Delete the current line.
 . CTRL-R:      Redisplay the current line.
 . CTRL-P:      Command recall - go backwards in command recall buffer.
 . CTRL-B:      Command recall - same as Ctrl-P.
 . CTRL-N:      Command recall - go forward in command recall buffer.
 . CTRL-K:      Insert the most recently entered local file specifiction.
 . ?            (question mark) Display a menu for the current command field.
 . ESC          (or TAB or Ctrl-I) Attempt to complete the current field.
 . \            (backslash) include the following character literally
                or introduce a backslash code, variable, or function.
 
IMPORTANT: Since backslash (\) is Kermit's command-line escape character,
you must enter DOS, Windows, or OS/2 pathnames using either forward slash (/)
or double backslash (\\) as the directory separator in most contexts.
Examples: C:/TMP/README.TXT, C:\\TMP\\README.TXT.
 
Command words other than filenames can be abbreviated in most contexts.
 
Basic commands:
  EXIT          Exit from Kermit
  HELP          Request general help
  HELP command  Request help about the given command
  TAKE          Execute commands from a file
  TYPE          Display a file on your screen
  ORIENTATION   Explains directory structure
 
Commands for file transfer:
  SEND          Send files
  RECEIVE       Receive files
  GET           Get files from a Kermit server
  RESEND        Recover an interrupted send
  REGET         Recover an interrupted get from a server
  SERVER        Be a Kermit server
 
File-transfer speed selection:
  FAST          Use fast settings -- THIS IS THE DEFAULT
  CAUTIOUS      Use slower, more cautious settings
  ROBUST        Use extremely slow and cautious settings
 
File-transfer performance fine tuning:
  SET RECEIVE PACKET-LENGTH  Kermit packet size
  SET WINDOW                 Number of sliding window slots
  SET PREFIXING              Amount of control-character prefixing
 
To make a direct serial connection:
  SET LINE      Select serial communication device
  SET SPEED     Select communication speed
  SET PARITY    Communications parity (if necessary)
  SET FLOW      Communications flow control, such as RTS/CTS
  CONNECT       Begin terminal connection
 
To dial out with a modem:
  SET DIAL DIRECTORY     Specify dialing directory file (optional)
  SET DIAL COUNTRY-CODE  Country you are dialing from (*)
  SET DIAL AREA-CODE     Area-code you are dialing from (*)
  LOOKUP                 Lookup entries in your dialing directory (*)
  SET MODEM TYPE         Select modem type
  SET LINE               Select serial communication device
  SET SPEED              Select communication speed
  SET PARITY             Communications parity (if necessary)
  DIAL                   Dial the phone number
  CONNECT                Begin terminal connection
 
Further info:   HELP DIAL, HELP SET MODEM, HELP SET LINE, HELP SET DIAL
(*) (For use with optional dialing directory)
 
To make a network connection:
  SET NETWORK DIRECTORY  Specify a network services directory (optional)
  LOOKUP                 Lookup entries in your network directory
  SET NETWORK TYPE       Select network type (if more than one available)
  SET HOST               Make a network connection but stay in command mode
  CONNECT                Begin terminal connection
  TELNET                 Select a Telnet host and CONNECT to it
  RLOGIN                 Select an Rlogin host and CONNECT to it
  SSH [ OPEN ]           Select an SSH host and CONNECT to it
  FTP [ OPEN ]           Make an FTP connection
  HTTP OPEN              Make an HTTP connection
 
To return from a terminal connection to the C-Kermit prompt:
  Type your escape character followed by the letter C.
 
To display your escape character:
  SHOW ESCAPE
 
To display other settings:
  SHOW COMMUNICATIONS, SHOW TERMINAL, SHOW FILE, SHOW PROTOCOL, etc.
 
The manual for C-Kermit is the book "Using C-Kermit".  For information
about the manual, visit:
  http://www.kermitproject.org/usingckermit.html
 
For an online C-Kermit tutorial, visit:
  http://www.kermitproject.org/ckututor.html
 
To learn about script programming and automation:
  http://www.kermitproject.org/ckscripts.html
 
For further information about a particular command, type HELP xxx,
where xxx is the name of the command.  For documentation, news of new
releases, and information about other Kermit software, visit the
Kermit Project website:
 
  http://www.kermitproject.org/
 
For information about technical support please visit this page:
 
  http://www.kermitproject.org/support.html
```

### NEWS

```
Welcome to C-Kermit 11.
For changes to C-Kermit since version 9.0 of 2011, please visit
https://github.com/OpenKermit/ckermit/blob/main/doc/changelog.md 
Documentation:
 . https://www.kermitproject.org/ckbindex.html
    Online index to C-Kermit documentation.
 . https://www.kermitproject.org/ckututor.html
    C-Kermit tutorial.
 
If the release date shown by the VERSION command is long past, be sure to
check the Kermit website to see if there have been updates:
 
  https://www.openkermit.org/    (Open Kermit home page)
  https://github.com/openkermit/ckermit/ (C-Kermit project page)
 
```

### LICENSE

```
Copyright (C) 1985, 2025,
  The Trustees of Columbia University in the City of New York.
Copyright (C) 2025-2026, John Goerzen.
All rights reserved.
 
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
 
 + Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 
 + Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in
   the documentation and/or other materials provided with the
   distribution.
 
 + Neither the name of Columbia University nor the names of its
   contributors may be used to endorse or promote products derived
   from this software without specific prior written permission.
 
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 
Portions Copyright (C) 1990, Massachusetts Institute of Technology.
Portions Copyright (C) 1991, 1993 Regents of the University of California.
Portions Copyright (C) 1991, 1992, 1993, 1994, 1995 by AT&T.
Portions Copyright (C) 1995, 1997, Eric Young <eay@cryptosoft.com>.
 
For further information, visit the Open Kermit website:
https://www.openkermit.org/ .
```

### SUPPORT

```
Live technical support for Kermit software is no longer available
from Columbia University, as it was from mid-1981 until mid-2011 when
the Kermit Project was cancelled.  Beginning with version 9.0, C-Kermit
is Open Source software.  The Kermit project has been moved to:
 
  http://www.kermitproject.org/
 
The C-Kermit home page is here:
 
  http://www.kermitproject.org/ckermit.html
 
The documentation for C-Kermit is listed here:
 
  http://www.kermitproject.org/ckermit.html#doc
 
A C-Kermit tutorial is here:
 
  http://www.kermitproject.org/ckututor.html
 
The C-Kermit Frequently Asked Questions page is here:
 
  http://www.kermitproject.org/ckfaq.html
 
and the Kermit Project Technical Support page is here:
 
  http://www.kermitproject.org/support.html
  
If you have a problem or question that is not addressed on the website
you can send email to:
 
  support@kermitproject.org
 
and as long as anyone is still at that address, it will be answered
on a best-effort basis.
```

## Commands

### _ASG

Synonym: _ASSIGN

```
Sorry, help not available for "_asg"
```

### _ASSIGN

Synonym for [_ASG](#asg).

### _DECREMENT

```
Sorry, help not available for "_decrement"
```

### _DEFINE

```
Sorry, help not available for "_define"
```

### _EVALUATE

```
Sorry, help not available for "_evaluate"
```

### _FORWARD

```
Sorry, help not available for "_forward"
```

### _GETARGS

```
Sorry, help not available for "_getargs"
```

### _INCREMENT

```
Sorry, help not available for "_increment"
```

### _PUTARGS

```
Sorry, help not available for "_putargs"
```

### _UNDEFINE

```
Sorry, help not available for "_undefine"
```

### ABOUT

Synonym for [VERSION](#version).

### ACCOUNT

```
 Equivalent to FTP ACCOUNT.
```

### ADD

```
ADD SEND-LIST filespec [ <mode> [ <as-name> ] ]
  Adds the specified file or files to the current SEND list.  Use SHOW
  SEND-LIST and CLEAR SEND-LIST to display and clear the list; use SEND
  by itself to send the files from it.
 
ADD BINARY-PATTERNS [ <pattern> [ <pattern> ... ] ]
  Adds the pattern(s), if any, to the SET FILE BINARY-PATTERNS list.
 
ADD TEXT-PATTERNS [ <pattern> [ <pattern> ... ] ]
  Adds the pattern(s), if any, to the SET FILE TEXT-PATTERNS list.
  Use SHOW PATTERNS to see the lists.  See HELP SET FILE for further info.
```

### ANSWER

```
Syntax:  ANSWER [ <seconds> ]
  Waits for a modem call to come in.  Prior SET MODEM TYPE and SET LINE
  required.  If <seconds> is 0 or not specified, Kermit waits forever or
  until interrupted, otherwise Kermit waits the given number of seconds.
  The ANSWER command puts the modem in autoanswer mode.  Subsequent DIAL
  commands will automatically put it (back) in originate mode.  SHOW MODEM,
  HELP SET MODEM for more info.
```

### APC

```
Syntax: APC text
  Echoes the text within a VT220/320/420 Application Program Command.
```

### ARRAY

```
Syntax: ARRAY verb operands...
 
Declares arrays and performs various operations on them.  Arrays have
the following syntax:
 
  \&a[n]
 
where "a" is a letter and n is a number or a variable with a numeric value
or an arithmetic expression.  The value of an array element can be anything
at all -- a number, a character, a string, a filename, etc.
 
The following ARRAY verbs are available:
 
[ ARRAY ] DECLARE arrayname[n] [ = initializers... ]
  Declares an array of the given size, n.  The resulting array has n+1
  elements, 0 through n.  Array elements can be used just like any other
  variables.  Initial values can be given for elements 1, 2, ... by
  including = followed by one or more values separated by spaces.  If you
  omit the size, the array is sized according to the number of initializers;
  if none are given the array is destroyed and undeclared if it already
  existed.  The ARRAY keyword is optional.  Synonym: [ ARRAY ] DCL.
 
[ ARRAY ] UNDECLARE arrayname
  Destroys and undeclares the given array.  Synonym: ARRAY DESTROY.
 
ARRAY SHOW [ arrayname ]
  Displays the contents of the given array.  A range specifier can be
  included to display a segment of the array, e.g. "array show \&a[1:24]."
  If the arrayname is omitted, all declared arrays are listed, but their
  contents is not shown.  Synonym: SHOW ARRAY.
 
ARRAY CLEAR arrayname
  Clears all elements of the array, i.e. sets them to empty values.
  You may include a range specifier to clear a segment of the array rather
  than the whole array, e.g. "array clear \%a[22:38]"
 
ARRAY SET arrayname value
  Sets all elements of the array to the given value.  You may specify a
  range to set a segment of the array, e.g. "array set \%a[2:9] 0"
 
ARRAY RESIZE arrayname number
  Changes the size of the given array, which must already exist, to the
  number given.  If the number is smaller than the current size, the extra
  elements are discarded; if it is larger, new empty elements are added.
 
ARRAY COPY array1 array2
  Copies array1 to array2.  If array2 has not been declared, it is created
  automatically.  If it array2 does exist, array1 is copied INTO it, as
  much as will fit.  Range specifiers may be given on one or both arrays.
 
ARRAY LINK array1 arra2
  Makes array1 a link to array2.
 
[ ARRAY ] SORT [ switches ] array-name [ array2 ]
  Sorts the given array lexically according to the switches.  Element 0 of
  the array is excluded from sorting by default.  The ARRAY keyword is
  optional.  If a second array name is given, that array is sorted according
  to the first one.  Switches:
 
  /CASE:{ON,OFF}
    If ON, alphabetic case matters; if OFF it is ignored.  If this switch is
    omitted, the current SET CASE setting applies.
 
  /KEY:number
    Position (1-based column number) at which comparisons begin, 1 by default.
 
  /NUMERIC
    Specifies a numeric rather than lexical sort.
 
  /RANGE:low[:high]
    The range of elements, low through high, to be sorted.  If this switch
    is not given, elements 1 through the dimensioned size are sorted.  If
    :high is omitted, the dimensioned size is used.  To include element 0 in
    a sort, use /RANGE:0 (to sort the whole array) or /RANGE:0:n (to sort
    elements 0 through n).  You can use a range specifier in the array name
    instead of the /RANGE switch.
 
  /REVERSE
    Sort in reverse order.  If this switch is not given, the array is sorted
    in ascending order.
 
Various functions are available for array operations; see HELP FUNCTION for
details.  These include \fdimension(), \farraylook(), \ffiles(), \fsplit(),
and many more.
```

### ASCII

Synonym: TEXT

```
Inhibits automatic transfer-mode switching and forces TEXT (ASCII) transfer
mode for all files in both Kermit and FTP protocols.
```

### ASG

Synonym for [ASSIGN](#assign).

### ASK

```
Syntax:  ASK [ switches ] variablename [ prompt ]
Example: ASK \%n { What is your name\? }
  Issues the prompt and defines the variable to be whatever is typed in
  response, up to the terminating carriage return.  Use braces to preserve
  leading and/or trailing spaces in the prompt.
 
Syntax:  ASKQ [ switches ] variablename [ prompt ]
Example: ASKQ \%p { Password:}
  Like ASK except the response does not echo on the screen or, if specified
  it echoes as asterisks or other specified character.
 
Switches:
 /DEFAULT:text
  Text to supply if the user enters a blank response or the /TIMEOUT
  limit expired with no response.
 
 /ECHO:char
  (ASKQ only) Character to be echoed each time the user presses a key
  corresponding to a printable character.  This lets users see what they are
  doing when they are typing (e.g.) passwords, and makes editing easier.
 
 /TIMEOUT:number
  If the response is not entered within the given number of seconds, the
  command fails.  This is equivalent to setting ASK-TIMER to a positive
  number, except it applies only to this command.  Also see SET ASK-TIMER.
  NOTE: If a /DEFAULT: value was also given, it is supplied automatically
  upon timeout and the command does NOT fail.
 
 /QUIET
  Suppresses "?Timed out" message when /TIMEOUT is given and user doesn't
  respond within the time limit.
```

### ASKQ

```
Syntax:  ASK [ switches ] variablename [ prompt ]
Example: ASK \%n { What is your name\? }
  Issues the prompt and defines the variable to be whatever is typed in
  response, up to the terminating carriage return.  Use braces to preserve
  leading and/or trailing spaces in the prompt.
 
Syntax:  ASKQ [ switches ] variablename [ prompt ]
Example: ASKQ \%p { Password:}
  Like ASK except the response does not echo on the screen or, if specified
  it echoes as asterisks or other specified character.
 
Switches:
 /DEFAULT:text
  Text to supply if the user enters a blank response or the /TIMEOUT
  limit expired with no response.
 
 /ECHO:char
  (ASKQ only) Character to be echoed each time the user presses a key
  corresponding to a printable character.  This lets users see what they are
  doing when they are typing (e.g.) passwords, and makes editing easier.
 
 /TIMEOUT:number
  If the response is not entered within the given number of seconds, the
  command fails.  This is equivalent to setting ASK-TIMER to a positive
  number, except it applies only to this command.  Also see SET ASK-TIMER.
  NOTE: If a /DEFAULT: value was also given, it is supplied automatically
  upon timeout and the command does NOT fail.
 
 /QUIET
  Suppresses "?Timed out" message when /TIMEOUT is given and user doesn't
  respond within the time limit.
```

### ASS

Synonym for [ASSIGN](#assign).

### ASSERT

```
Syntax: ASSERT <condition>
Succeeds or fails depending on <condition>; see HELP IF for <condition>s.
```

### ASSIGN

Synonyms: ASG, ASS

```
Syntax:  ASSIGN variablename string.
Example: ASSIGN \%a My name is \%b.
  Assigns the current value of the string to the variable (or macro).
  The definition string is fully evaluated before it is assigned, so that
  the values of any variables that are contained are used, rather than their
  names.  Compare with DEFINE.  To illustrate the difference, try this:
 
    DEFINE \%a hello
    DEFINE \%x \%a
    ASSIGN \%y \%a
    DEFINE \%a goodbye
    ECHO \%x \%y
 
  This prints 'goodbye hello'.
```

### ASSOCIATE

```
ASSOCIATE FILE-CHARACTER-SET <file-character-set> <transfer-character-set>
  Tells C-Kermit that whenever the given file-character set is selected, and
  SEND CHARACTER-SET (q.v.) is AUTOMATIC, the given transfer character-set
  is selected automatically.
 
ASSOCIATE XFER-CHARACTER-SET <xfer-character-set> <file-character-set>
  Tells C-Kermit that whenever the given transfer-character set is selected,
  either by command or by an announcer attached to an incoming text file,
  and SEND CHARACTER-SET is AUTOMATIC, the specified file character-set is
  to be selected automatically.  Synonym: ASSOCIATE TRANSFER-CHARACTER-SET.
 
Use SHOW ASSOCIATIONS to list the current character-set associations, and
SHOW CHARACTER-SETS to list the current settings.
```

### BACK

```
Syntax: BACK
  Returns to your previous directory.
```

### BEEP

```
Syntax: BEEP
Sends a BEL character to your terminal.
```

### BINARY

```
Inhibits automatic transfer-mode switching and forces BINARY transfer mode
for all files in both Kermit and FTP protocols.
```

### BROWSE

```
Syntax: BROWSE [ <url> ]
Starts your preferred Web browser on the given URL, or if none given, the
most recently visited URL, if any.  Also see SET BROWSER.
```

### BUG

Synonym for [SUPPORT](#support).

### BYE

```
Syntax: BYE
  Shut down and log out a remote Kermit server
```

### C

Synonym for [CONNECT](#connect).

### CAT

```
Syntax: MORE [ switches ] filename
  Equivalent to TYPE /NOPAGE filename; see HELP TYPE.
```

### CAUTIOUS

```
FAST, CAUTIOUS, and ROBUST are predefined macros that set several
file-transfer parameters at once to achieve the desired file-transfer goal.
FAST chooses a large packet size, a large window size, and a fair amount of
control-character unprefixing at the risk of possible failure on some
connections.  FAST is the default tuning in C-Kermit 7.0 and later.  In case
FAST file transfers fail for you on a particular connection, try CAUTIOUS.
If that fails too, try ROBUST.  You can also change the definitions of each
macro with the DEFINE command.  To see the current definitions, type
"show macro fast", "show macro cautious", or "show macro robust".
```

### CD

Synonym: CWD

```
  If LOCUS is REMOTE or LOCUS is AUTO and you have an FTP connection,
  this command is equivalent to REMOTE CD (RCD).  Otherwise:
 
Syntax: CD [ directory name ]
  Change Directory.  Changes your current, working, default directory to the
  one given, so that future non-absolute filename references are relative to
  this directory.  If the directory name is omitted, your home (login)
  directory is supplied.
  C-Kermit's default prompt shows your current directory.
  Synonyms: LCD, CWD.
  Also see: SET LOCUS, PWD, CDUP, BACK, REMOTE CD (RCD), SET CD, SET PROMPT.
  And see: HELP KCD.
  Relevant environment variables: CDPATH, HOME.
```

### CDUP

```
Change working directory to the one just above the current one.
```

### CGET

```
Syntax: CGET <remote-file-or-command> <local-command>
Equivalent to GET /COMMAND; see HELP GET for details.
```

### CH

Synonym for [CHECK](#check).

### CHANGE

```
Syntax: CHANGE [ switches ] filespec string1 string2
  Changes all occurrences of string1 to string2 in the given file or files.
  Works line by line, does not do multiline or across-line substitutions.
  To remove strings from files, specify string2 as "" or omit string2.
  Temporary files are created in the directory indicated by \v(tmpdir)
  (show var tmpdir).  You can select a different temporary directory with
  the SET TEMP-DIRECTORY command.  All temporary files are deleted after use.
 
  String1 and String2 should be enclosed in doublequotes "" or braces {} if
  if they contain spaces.  In the event that they already contain braces or
  doublequotes, especially if these are not balanced, some quoting may be
  required.  Or you can assign the strings to variables and then use the
  variable names in the CHANGE command; example:
 
    .a = {value="./
    .b = {value="../
    change *.html \m(a) \m(b)
 
  Since the CHANGE command works line by line, only text files can be
  changed; C-Kermit automatically skips over binary files.
 
  File selection switches (factory defaults are marked with +):
 
   /AFTER:         Select files modified after the given date
   /BEFORE:        Select files modified before the given date
   /LARGER:        Select files larger than the given size in bytes
   /SMALLER:       Select files smaller than the given size in bytes
   /EXCEPT:        Exclude the given files (list or pattern)
   /DOTFILES       Include files whose names start with dot (period).
   /NODOTFILES   + Don't include files whose names start with dot.
   /RECURSIVE      Descend through subdirectories.
   /NORECURSIVE  + Don't descend through subdirectories.
 
 File disposition switches:
 
   /BACKUP:name       Back up original files to named directory.
   /DESTINATION:name  Store resulting changed files in named directory.
   If neither of these options is given, original files are overwritten.
 
 String selection switches:
 
   /CASE:{ON,OFF}  OFF (default) = ignore case in string1; ON = don't ignore
 
 Action switches:
 
   /COUNT:name     Set named variable to number of files that were changed.
   /SIMULATE       List files that would be changed, but don't change them.
   /LIST           Show which files are being changed.
   /MODTIME:       Modification time for change files, PRESERVE or UPDATE.
 
You can use the /SIMULATE switch in combination with other switches to see
which files will be affected without actually changing them.
```

### CHECK

Synonym: CH

```
Syntax: CHECK name
  Checks  to see if the named feature is included in this version of Kermit.
  To list the features you can check, type "check ?".
```

### CHMOD

```
Syntax: CHMOD [ switches ] code filespec
  UNIX only.  Changes permissions of the given file(s) to the given code,
  which must be an octal number such as 664 or 775.  Optional switches:
 
   /FILES        Only change permissions of regular files.
   /DIRECTORIES  Only change permissions of directory files.
   /TYPE:BINARY  Only change permissions of binary files.
   /TYPE:TEXT    Only change permissions of text files.
   /DOTFILES     Include files whose names begin with dot (.).
   /RECURSIVE    Change permissions in subdirectories too.
   /LIST         List each file (synonym: /VERBOSE).
   /NOLIST       Operate silently (synonym: /QUIET).
   /PAGE         When listing, pause at end of each screen (implies /LIST).
   /NOPAGE       When listing, don't pause at end of each screen.
   /SIMULATE     Show what would be done but don't actually do it.
```

### CHROOT

```
Syntax: SET ROOT directoryname
  Sets the root for file access to the given directory and disables access
  to system and shell commands and external programs.  Once this command
  is given, no files or directories outside the tree rooted by the given
  directory can be opened, read, listed, deleted, renamed, or accessed in
  any other way.  This command can not be undone by a subsequent SET ROOT
  command.  Primarily for use with server mode, to restrict access of
  clients to a particular directory tree.  Synonym: CHROOT.
```

### CKERMIT

Synonyms: K95, KERMIT, WERMIT

```
Syntax: KERMIT [command-line-options]
  Lets you give command-line options at the prompt or in a script.
  HELP OPTIONS for more info.
```

### CL

Synonym for [CLOSE](#close).

### CLEAR

```
Syntax: CLEAR [ item-name ]
 
Clears the named item.  If no item is named, DEVICE-AND-INPUT is assumed.
 
  ALARM            Clears any pending alarm (see SET ALARM).
  APC              Clears Application Program Command status.
  BINARY-PATTERNS  Clears the file binary-patterns list.
  DEVICE           Clears the current port or network input buffer.
  DEVICE-AND-INPUT Clears both the device and the INPUT buffer.
  DIAL-STATUS      Clears the \v(dialstatus) variable.
  INPUT            Clears the INPUT-command buffer and the \v(input) variable.
  KEYBOARD-BUFFER  Clears the command terminal keyboard input buffer.
  SEND-LIST        Clears the current SEND list (see ADD).
  TEXT-PATTERNS    Clears the file text-patterns list.
```

### CLOSE

Synonym: CL

```
Syntax:  CLOSE [ item ]
  Close the indicated item.  The default item is CONNECTION, which is the
  current SET LINE or SET HOST connection.  The other items are:
 
    CX-LOG          (connection log, opened with LOG CX)
    SESSION-LOG     (opened with LOG SESSION)
    TRANSACTION-LOG (opened with LOG TRANSACTIONS)
    PACKET-LOG      (opened with LOG PACKETS)
    DEBUG-LOG       (opened with LOG DEBUG)
    READ-FILE       (opened with OPEN READ)
    WRITE-FILE      (opened with OPEN WRITE or OPEN APPEND)
 
Type HELP LOG and HELP OPEN for further info.
```

### CLS

```
Sorry, help not available for "cls"
```

### CO

Synonym for [COPY](#copy).

### COMMENT

Synonyms: #, EXTPROC

```
Syntax: COMMENT text
Example: COMMENT - this is a comment.
  Introduces a comment.  Beginning of command line only.  Commands may also
  have trailing comments, introduced by ; or #.
```

### COMPACT-SUBSTRING

```
Compact Substring Notation is a shorthand notation for the built-in
\fsubstring() function; 'name' is the name of any macro-type variable:
  \s(name[n:m])
      Substring of \m(name) starting at position n, length m
  \s(name[n_m])
      Substring of \m(name) from position n to position m
  \s(name[n]) or \s(name[n:])
      Substring of \m(name) from position n to the end
  \s(name[n.])
      The character at position n
```

### CONNECT

Synonym: C

```
Syntax: CONNECT (or C, or CQ) [ switches ]
  Connect to a remote computer via the serial communications device given in
  the most recent SET LINE command, or to the network host named in the most
  recent SET HOST command.  Type the escape character followed by C to get
  back to the C-Kermit prompt, or followed by ? for a list of CONNECT-mode
  escape commands.
 
Include the /QUIETLY switch to suppress the informational message that
tells you how to escape back, etc.  CQ is a synonym for CONNECT /QUIETLY.
 
Other switches include:
 
/TRIGGER:string
  One or more strings to look for that will cause automatic return to
  command mode.  To specify one string, just put it right after the
  colon, e.g. "/TRIGGER:Goodbye".  If the string contains any spaces, you
  must enclose it in braces, e.g. "/TRIGGER:{READY TO SEND...}".  To
  specify more than one trigger, use the following format:
 
    /TRIGGER:{{string1}{string2}...{stringn}}
 
  Upon return from CONNECT mode, the variable \v(trigger) is set to the
  trigger string, if any, that was actually encountered.  This value, like
  all other CONNECT switches applies only to the CONNECT command with which
  it is given, and overrides (temporarily) any global SET TERMINAL TRIGGER
  string that might be in effect.

Your escape character is Ctrl-\ (ASCII 28, FS)
```

### CONTINUE

```
 In a FOR or WHILE loop: continue the loop.
 At the prompt: continue a script that has "shelled out" to the prompt.
```

### CONVERT

Synonyms: TRANSLATE, XLATE

```
Syntax: CONVERT file1 cs1 cs2 [ file2 ]
Synonym: TRANSLATE
  Converts file1 from the character set cs1 into the character set cs2
  and stores the result in file2.  The character sets can be any of
  C-Kermit's file character sets.  If file2 is omitted, the translation
  is displayed on the screen.  An appropriate intermediate character-set
  is chosen automatically, if necessary.  Synonym: XLATE.  Example:
 
    CONVERT lasagna.txt latin1 utf8 lasagna-utf8.txt
 
  Multiple files can be translated if file2 is a directory or device name,
  rather than a filename, or if file2 is omitted.
```

### COP

Synonym for [COPY](#copy).

### COPY

Synonyms: CO, COP, CP

```
Syntax: COPY [ switches ] file1 file2
  Copies the source file (file1) to the destination file (file2).  If file2
  is a directory, file1 can contain wildcards to denote a group of files to
  be copied to the given directory.  Switches:
 
  /TOSCREEN
    Displays the file on the screen rather than copying to another file.
 
  /LIST
    Print the filenames and status while copying.  Synonyms: /LOG, /VERBOSE.
 
  /NOLIST
    Copy silently (default). Synonyms: /NOLOG, /QUIET.
 
  /PRESERVE
    Copy timestamp and permissions from source file to destination file.
 
  /OVERWRITE:{ALWAYS,NEVER,NEWER,OLDER}
    When copying from one directory to another, this tells what to do when
    the destination file already exists: overwrite it always; never; only if
    the source file is newer; or only if the source file is older.
 
  /APPEND
    Append the source file to the destination file.  In this case the source
    file specification can contain wildcards, and all the matching source
    files are appended, one after the other in alphabetical order by name,
    to the destination file.
 
  /SWAP-BYTES
    Swap bytes while copying (e.g. for converting between Big-Endian and
    Little-Endian binary data formats).
 
  /FROMB64
    Convert from Base64 encoding while copying.
 
  /TOB64
    Convert to Base64 encoding while copying.
 
  /INTERPRET
    If the file contains Kermit backslash escapes like \v(date), \v(time),
    \%1, \%2, \m(fast), etc, they are interpreted in the new copy of the
    file or in the screen version, if used in combination with /TOSCREEN.
    This option is not compatible most of the other options.
  
```

### COPYRIGHT

Synonym for [LICENSE](#license).

### CP

Synonym for [COPY](#copy).

### CQ

```
Syntax: CONNECT (or C, or CQ) [ switches ]
  Connect to a remote computer via the serial communications device given in
  the most recent SET LINE command, or to the network host named in the most
  recent SET HOST command.  Type the escape character followed by C to get
  back to the C-Kermit prompt, or followed by ? for a list of CONNECT-mode
  escape commands.
 
Include the /QUIETLY switch to suppress the informational message that
tells you how to escape back, etc.  CQ is a synonym for CONNECT /QUIETLY.
 
Other switches include:
 
/TRIGGER:string
  One or more strings to look for that will cause automatic return to
  command mode.  To specify one string, just put it right after the
  colon, e.g. "/TRIGGER:Goodbye".  If the string contains any spaces, you
  must enclose it in braces, e.g. "/TRIGGER:{READY TO SEND...}".  To
  specify more than one trigger, use the following format:
 
    /TRIGGER:{{string1}{string2}...{stringn}}
 
  Upon return from CONNECT mode, the variable \v(trigger) is set to the
  trigger string, if any, that was actually encountered.  This value, like
  all other CONNECT switches applies only to the CONNECT command with which
  it is given, and overrides (temporarily) any global SET TERMINAL TRIGGER
  string that might be in effect.

Your escape character is Ctrl-\ (ASCII 28, FS)
```

### CRECEIVE

```
Syntax: CRECEIVE [ switches ] <command>
Receives to the given <command> rather than to a file.  Equivalent to
RECEIVE /COMMAND; see HELP RECEIVE for details.
```

### CSEND

```
Syntax: CSEND [ switches ] <command> [ <as-name> ]
Sends from the given <command> rather than from a file.  Equivalent to
SEND /COMMAND; see HELP SEND for details.
```

### CWD

Synonym for [CD](#cd).

### DATE

```
Syntax: DATE [ date-time [ timezone ] ] [ delta-time ]
  Prints a date-time in standard format: yyyymmdd_hh:mm:ss.
  Various date-time formats are accepted:
 
  . The date, if given, must precede the time.
  . The year must be four digits or else a 2-digit format dd mmm yy,
    in which case if (yy < 50) yyyy = yy + 2000; else yyyy = yy + 1900.
  . If the year comes first, the second field is the month.
  . The day, month, and year may be separated by spaces, /, -, or underscore.
  . The date and time may be separated by spaces or underscore.
  . The month may be numeric (1 = January) or spelled out or abbreviated in
    English.
  . The time may be in 24-hour format or 12-hour format.
  . If the hour is 12 or less, AM is assumed unless AM or PM is included.
  . If the date is omitted but a time is given, the current date is supplied.
  . If the time is given but date omitted, 00:00:00 is supplied.
  . If both the date and time are omitted, the current date and time are
    supplied.
 
  The following shortcuts can also be used in place of dates:
 
  NOW
    Stands for the current date and time.
 
  TODAY
    Today's date, optionally followed by a time; 00:00:00 if no time given.
 
  YESTERDAY
    Yesterday's date, optionally followed by a time (default 00:00:00).
 
  TOMORROW
    Tomorrows's date, optionally followed by a time (default 00:00:00).
 
  Timezone specifications are similar to those used in e-mail and HTTP
    headers, either a USA timezone name, e.g. EST, or a signed four-digit
    timezone offset, {+,-}hhmm, e.g., -0500; it is used to convert date-time,
    a local time in that timezone, to GMT which is then converted to the
    local time at the host.  If no timezone is given, the date-time is local.
    To convert local time (or a time in a specified timezone) to UTC (GMT),
    use the function \futcdate().
 
  Delta times are given as {+,-}[number date-units][hh[:mm[:ss]]]
    A date in the future/past relative to the date-time; date-units may be
    DAYS, WEEKS, MONTHS, YEARS: +3days, -7weeks, +3:00, +1month 8:00.
 
All the formats shown above are acceptable as arguments to date-time switches
such as /AFTER: or /BEFORE:, and to functions such as \fcvtdate(),
\fdiffdate(), and \futcdate(), that take date-time strings as arguments.
```

### DCL

Synonym: DECLARE

```
Syntax: ARRAY verb operands...
 
Declares arrays and performs various operations on them.  Arrays have
the following syntax:
 
  \&a[n]
 
where "a" is a letter and n is a number or a variable with a numeric value
or an arithmetic expression.  The value of an array element can be anything
at all -- a number, a character, a string, a filename, etc.
 
The following ARRAY verbs are available:
 
[ ARRAY ] DECLARE arrayname[n] [ = initializers... ]
  Declares an array of the given size, n.  The resulting array has n+1
  elements, 0 through n.  Array elements can be used just like any other
  variables.  Initial values can be given for elements 1, 2, ... by
  including = followed by one or more values separated by spaces.  If you
  omit the size, the array is sized according to the number of initializers;
  if none are given the array is destroyed and undeclared if it already
  existed.  The ARRAY keyword is optional.  Synonym: [ ARRAY ] DCL.
 
[ ARRAY ] UNDECLARE arrayname
  Destroys and undeclares the given array.  Synonym: ARRAY DESTROY.
 
ARRAY SHOW [ arrayname ]
  Displays the contents of the given array.  A range specifier can be
  included to display a segment of the array, e.g. "array show \&a[1:24]."
  If the arrayname is omitted, all declared arrays are listed, but their
  contents is not shown.  Synonym: SHOW ARRAY.
 
ARRAY CLEAR arrayname
  Clears all elements of the array, i.e. sets them to empty values.
  You may include a range specifier to clear a segment of the array rather
  than the whole array, e.g. "array clear \%a[22:38]"
 
ARRAY SET arrayname value
  Sets all elements of the array to the given value.  You may specify a
  range to set a segment of the array, e.g. "array set \%a[2:9] 0"
 
ARRAY RESIZE arrayname number
  Changes the size of the given array, which must already exist, to the
  number given.  If the number is smaller than the current size, the extra
  elements are discarded; if it is larger, new empty elements are added.
 
ARRAY COPY array1 array2
  Copies array1 to array2.  If array2 has not been declared, it is created
  automatically.  If it array2 does exist, array1 is copied INTO it, as
  much as will fit.  Range specifiers may be given on one or both arrays.
 
ARRAY LINK array1 arra2
  Makes array1 a link to array2.
 
[ ARRAY ] SORT [ switches ] array-name [ array2 ]
  Sorts the given array lexically according to the switches.  Element 0 of
  the array is excluded from sorting by default.  The ARRAY keyword is
  optional.  If a second array name is given, that array is sorted according
  to the first one.  Switches:
 
  /CASE:{ON,OFF}
    If ON, alphabetic case matters; if OFF it is ignored.  If this switch is
    omitted, the current SET CASE setting applies.
 
  /KEY:number
    Position (1-based column number) at which comparisons begin, 1 by default.
 
  /NUMERIC
    Specifies a numeric rather than lexical sort.
 
  /RANGE:low[:high]
    The range of elements, low through high, to be sorted.  If this switch
    is not given, elements 1 through the dimensioned size are sorted.  If
    :high is omitted, the dimensioned size is used.  To include element 0 in
    a sort, use /RANGE:0 (to sort the whole array) or /RANGE:0:n (to sort
    elements 0 through n).  You can use a range specifier in the array name
    instead of the /RANGE switch.
 
  /REVERSE
    Sort in reverse order.  If this switch is not given, the array is sorted
    in ascending order.
 
Various functions are available for array operations; see HELP FUNCTION for
details.  These include \fdimension(), \farraylook(), \ffiles(), \fsplit(),
and many more.
```

### DECLARE

Synonym for [DCL](#dcl).

### DECREMENT

```
Syntax: DECREMENT variablename [ amount ]
  Decrement (subtract one from) the value of a variable if the current value
  is numeric.  If an optional amount is specified (as a number, a variable,
  or an arithmetic expression that evaluates to a number, or any combination)
  the variable is decremented by that number instead of 1.  The result is
  always an integer.  If floating-point numbers are given, the result is
  truncated.
 
Examples: DECR \%a, DECR days 7, DECR x \%n, DECR sum \%x+12
```

### DEFINE

Synonym: .

```
Syntax: DEFINE name [ definition ]
  Defines a macro or variable.  Its value is the definition, taken
  literally.  No expansion or evaluation of the definition is done.  Thus
  if the definition includes any variable or function references, their
  names are included, rather than their values (compare with ASSIGN).  If
  the definition is omitted, then the named variable or macro is undefined.
  If a variable of the same name already exists, its value is replaced by
  the new value.
 
A typical macro definition looks like this:
 
  DEFINE name command, command, command, ...
 
for example:
 
  DEFINE vax set parity even, set duplex full, set flow xon/xoff
 
which defines a Kermit command macro called 'vax'.  The definition is a
comma-separated list of Kermit commands.  Use the DO command to execute
the macro, or just type its name, followed optionally by arguments.
 
The definition of a variable can be anything at all, for example:
 
  DEFINE \%a Monday
  DEFINE \%b 3
 
These variables can be used almost anywhere, for example:
 
  ECHO Today is \%a
  SET BLOCK-CHECK \%b
```

### DELETE

Synonyms: ERASE, RM

```
Syntax: DELETE [ switches... ] filespec
  If LOCUS is REMOTE or LOCUS is AUTO and you have an FTP connection,
  this command is equivalent to REMOTE DELETE (RDELETE).  Otherwise:
 
  Deletes a file or files on the computer where C-Kermit is running.
  The filespec may denote a single file or can include wildcard characters
  to match multiple files.  RM is a synonym for DELETE.  Switches include:
 
/AFTER:date-time
  Specifies that only those files modified after the given date-time are
  to be deleted.  HELP DATE for info about date-time formats.
 
/BEFORE:date-time
  Specifies that only those files modified before the given date-time
  are to be deleted.
 
/NOT-AFTER:date-time
  Specifies that only those files modified at or before the given date-time
  are to be deleted.
 
/NOT-BEFORE:date-time
  Specifies that only those files modified at or after the given date-time
  are to be deleted.
 
/LARGER-THAN:number
  Specifies that only those files longer than the given number of bytes are
  to be deleted.
 
/SMALLER-THAN:number
  Specifies that only those files smaller than the given number of bytes are
  to be sent.
 
/EXCEPT:pattern
  Specifies that any files whose names match the pattern, which can be a
  regular filename or may contain wildcards, are not to be deleted.  To
  specify multiple patterns (up to 8), use outer braces around the group
  and inner braces around each pattern:
 
    /EXCEPT:{{pattern1}{pattern2}...}
 
/DOTFILES
  Include (delete) files whose names begin with ".".
 
/NODOTFILES
  Skip (don't delete) files whose names begin with ".".
 
/TYPE:TEXT
  Delete only regular text files (requires FILE SCAN ON as it is by default)
 
/TYPE:BINARY
  Delete only regular binary files (requires FILE SCAN ON)
 
/DIRECTORIES
  Include directories.  If this switch is not given, only regular files
  are deleted.  If it is given, Kermit attempts to delete any directories
  that match the given file specification, which succeeds only if the
  directory is empty.
 
/RECURSIVE
  The DELETE command applies to the entire directory tree rooted in the
  current or specified directory.  When the /DIRECTORIES switch is also
  given, Kermit deletes all the (matching) files in each directory before
  attempting to delete the directory itself.
 
/ALL
  This is a shortcut for /RECURSIVE /DIRECTORIES /DOTFILES.
 
/LIST
  List each file and tell whether it was deleted.  Synonyms: /LOG, /VERBOSE.
 
/NOLIST
  Don't list files while deleting.  Synonyms: /NOLOG, /QUIET.
 
/HEADING
  Print heading and summary information.
 
/NOHEADING
  Don't print heading and summary information.
 
/SUMMARY
  Like /HEADING /NOLIST, but only prints the summary line.
 
/PAGE
  If listing, pause after each screenful.
 
/NOPAGE
  Don't pause after each screenful.
 
/ASK
  Interactively ask permission to delete each file.  Reply Yes or OK to
  delete it, No not to delete it, Quit to cancel the DELETE command, and
  Go to go ahead and delete all the rest of the files without asking.
 
/NOASK
  Delete files without asking permission.
 
/SIMULATE
  Preview files selected for deletion without actually deleting them.
  Implies /LIST.
 
Use SET OPTIONS DELETE to make selected switches effective for every DELETE
command unless you override them; use SHOW OPTIONS to see selections currently
in effect.  Also see HELP SET LOCUS, HELP PURGE, HELP WILDCARD.
```

### DIAL

```
Syntax:  DIAL phonenumber
Example: DIAL 7654321
  Dials a number using an autodial modem.  First you must SET MODEM TYPE, then
  SET LINE, then SET SPEED.  Then give the DIAL command, including the phone
  number, for example:
 
   DIAL 7654321
 
  If the modem is on a network modem server, SET HOST first, then SET MODEM
  TYPE, then DIAL.
 
If you give the DIAL command interactively at the Kermit prompt, and the
call is placed successfully, Kermit automatically enters CONNECT mode.
If the DIAL command is given from a macro or command file, Kermit remains
in command mode after the call is placed, successfully or not.  You can
change this behavior with the SET DIAL CONNECT command.
 
If the phonenumber starts with a letter, and if you have used the SET DIAL
DIRECTORY command to specify one or more dialing-directory files, Kermit
looks it up in the given file(s); if it is found, the name is replaced by
the number or numbers associated with the name.  If it is not found, the
name is sent to the modem literally.
 
If the phonenumber starts with an equals sign ("="), this forces the part
after the = to be sent literally to the modem, even if it starts with a
letter, without any directory lookup.
 
You can also give a list of phone numbers enclosed in braces, e.g:
 
  dial {{7654321}{8765432}{+1 (212 555-1212}}
 
(Each number is enclosed in braces and the entire list is also enclosed in
braces.)  In this case, each number is tried until there is an answer.  The
phone numbers in this kind of list can not be names of dialing directory
entries.
 
A dialing directory is a plain text file, one entry per line:
 
  name  phonenumber  ;  comments
 
for example:
 
  work    9876543              ; This is a comment
  e-mail  +1  (212) 555 4321   ; My electronic mailbox
  germany +49 (511) 555 1234   ; Our branch in Hanover
 
If a phone number starts with +, then it must include country code and
area code, and C-Kermit will try to handle these appropriately based on
the current locale (HELP SET DIAL for further info); these are called
PORTABLE entries.  If it does not start with +, it is dialed literally.
 
If more than one entry is found with the same name, Kermit dials all of
them until the call is completed; if the entries are in portable format,
Kermit dials them in cheap-to-expensive order: internal, then local, then
long-distance, then international, based on its knowledge of your local
country code and area code (see HELP SET DIAL).
 
Specify your dialing directory file(s) with the SET DIAL DIRECTORY command.
 
See also SET DIAL, SET MODEM, SET LINE, SET HOST, SET SPEED, REDIAL, and
PDIAL.
```

### DIRECTORY

Synonyms: FOT, LS, V, VDIRECTORY

```
Syntax: DIRECTORY [ switches ] [ filespec [ filespec [ ... ] ] ]
  If LOCUS is REMOTE or LOCUS is AUTO and you have an FTP connection,
  this command is equivalent to REMOTE DIRECTORY (RDIR).  Otherwise:
 
  Lists local files.  The filespec may be a filename, possibly containing
  wildcard characters, or a directory name.  If no filespec is given, all
  files in the current directory are listed.  If a directory name is given,
  all the  files in it are listed.  Multiple filespecs can be given.
  Optional switches:
 
   /BRIEF           List filenames only.
   /VERBOSE       + Also list permissions, size, and date.
   /FILES           Show files but not directories.
   /DIRECTORIES     Show directories but not files.
   /ALL           + Show both files and directories.
   /ARRAY:&a        Store file list in specified array (e.g. \%a[]).
   /PAGE            Pause after each screenful.
   /NOPAGE          Don't pause after each screenful.
   /TOP:n           Only show the top n lines of the directory listing.
   /DOTFILES        Include files whose names start with dot (period).
   /NODOTFILES    + Don't include files whose names start with dot.
   /FOLLOWLINKS     Follow symbolic links.
   /NOFOLLOWLINKS + Don't follow symbolic links.
   /NOLINKS         Don't list symbolic links at all.
   /BACKUP        + Include backup files (names end with .~n~).
   /NOBACKUPFILES   Don't include backup files.
   /OUTPUT:file     Store directory listing in the given file.
   /HEADING         Include heading and summary.
   /NOHEADING     + Don't include heading or summary.
   /COUNT:var       Put the number of matching files in the given variable.
   /SUMMARY         Print only count and total size of matching files.
   /XFERMODE        Show pattern-based transfer mode (T=Text, B=Binary).
   /TYPE:           Show only files of the specified type (text or binary).
   /MESSAGE:text    Add brief message to each listing line.
   /NOMESSAGE     + Don't add message to each listing line.
   /NOXFERMODE    + Don't show pattern-based transfer mode
   /ISODATE       + In verbose listings, show date in ISO 8061 format.
   /ENGLISHDATE     In verbose listings, show date in "English" format.
   /RECURSIVE       Descend through subdirectories.
   /NORECURSIVE   + Don't descend through subdirectories.
   /SORT:key        Sort by key, NAME, DATE, or SIZE; default key is NAME.
   /NOSORT        + Don't sort.
   /ASCENDING     + If sorting, sort in ascending order.
   /REVERSE         If sorting, sort in reverse order.
 
Factory defaults are marked with +.  Default for paging depends on SET
COMMAND MORE-PROMPTING.  Use SET OPTIONS DIRECTORY [ switches ] to change
defaults; use SHOW OPTIONS to display customized defaults.  Also see
WDIRECTORY.
```

### DISABLE

```
Syntax: DISABLE command [ { LOCAL, REMOTE, BOTH } ]
  Prevents execution of the named command.  The optional parameter
  specifies the mode in which the command is disabled:

  LOCAL:  Disabled in local mode, which applies to commands requested
          by a remote host via escape sequences or APC.
  REMOTE: Disabled in remote mode, which applies to commands received
          by a Kermit server.
  BOTH:   Disabled in both modes.

  If the parameter is omitted, BOTH is used.  By default, most commands
  are enabled for REMOTE but disabled for LOCAL to prevent security issues.
  Use SHOW SERVER to view the current enable/disable states.
```

### DO

```
Syntax: [ DO ] macroname [ arguments ]
  Executes a macro that was defined with the DEFINE command.  The word DO
  can be omitted.  Trailing argument words, if any, are automatically
  assigned to the macro argument variables \%1 through \%9.
```

### E

Synonym for [EXIT](#exit).

### E-PACKET

```
Syntax: E-PACKET
  Sends an Error packet to the other Kermit.
```

### ECHO

```
Syntax: ECHO text
  Displays the text on the screen, followed by a line terminator.  The ECHO
  text may contain backslash codes.  Example: ECHO \7Wake up!\7.  Also see
  XECHO and WRITE SCREEN.
```

### EDIT

```
Syntax: EDIT [ <file> ]
Starts your preferred editor on the given file, or if none given, the most
recently edited file, if any.  Also see SET EDITOR.
```

### EIGHTBIT

```
Equivalent to SET PARITY NONE, SET COMMAND BYTE 8, SET TERMINAL BYTE 8.
```

### ELSE

```
Sorry, help not available for "else"
```

### ENABLE

```
Syntax: ENABLE capability [ { LOCAL, REMOTE, BOTH } ]
  Allows execution of the named capability.  The optional parameter
  specifies the mode in which the capability is enabled:

  LOCAL:  Enabled in local mode, which applies to commands requested
          by a remote host via escape sequences or APC.
  REMOTE: Enabled in remote mode, which applies to commands received
          by a Kermit server.
  BOTH:   Enabled in both modes.

  If the parameter is omitted, BOTH is used.  By default, most commands
  are enabled for REMOTE but disabled for LOCAL to prevent security issues.
  Use SHOW SERVER to view the current enable/disable states.
```

### END

Synonym: POP

```
Syntax: END [ number [ message ] ]
  Exits from the current macro or TAKE file, back to wherever invoked from.
  Number is return code.  Message, if given, is printed.
```

### ERASE

Synonym for [DELETE](#delete).

### EVALUATE

```
Syntax: EVALUATE variable expression
  Evaluates the expression and assigns its value to the given variable.
  The expression can contain numbers and/or numeric-valued variables or
  functions, combined with mathematical operators and parentheses in
  traditional notation.  Operators include +-/*(), etc.  Example:
  EVALUATE \%n (1+1) * (\%a / 3).
 
  NOTE: Prior to C-Kermit 7.0, the syntax was "EVALUATE expression"
  (no variable), and the result was printed.  Use SET EVAL { OLD, NEW }
  to choose the old or new behavior, which is NEW by default.
 
Alse see: HELP FUNCTION EVAL.
```

### EX

Synonym for [EXIT](#exit).

### EXEC

```
Syntax: EXEC <command> [ <arg1> [ <arg2> [ ... ] ]
  C-Kermit overlays itself with the given system command and starts it with
  the given arguments.  Upon any error, control returns to C-Kermit.
```

### EXIT

Synonyms: E, EX

```
Syntax: EXIT (or QUIT) [ number [ text ] ]
  Exits from the Kermit program, closing all open files and devices.
  If a number is given it becomes Kermit's exit status code.  If text is
  included, it is printed.  Also see SET EXIT.
```

### EXTPROC

Synonym for [COMMENT](#comment).

### F

Synonym for [FINISH](#finish).

### FAIL

```
Always fails.
```

### FAST

```
FAST, CAUTIOUS, and ROBUST are predefined macros that set several
file-transfer parameters at once to achieve the desired file-transfer goal.
FAST chooses a large packet size, a large window size, and a fair amount of
control-character unprefixing at the risk of possible failure on some
connections.  FAST is the default tuning in C-Kermit 7.0 and later.  In case
FAST file transfers fail for you on a particular connection, try CAUTIOUS.
If that fails too, try ROBUST.  You can also change the definitions of each
macro with the DEFINE command.  To see the current definitions, type
"show macro fast", "show macro cautious", or "show macro robust".
```

### FCLOSE

```
Syntax: FILE CLOSE <channel>
  Closes the file on the given channel if it was open.
  Also see HELP FILE OPEN.  Synonym: FCLOSE.
```

### FCOUNT

```
Syntax: FILE COUNT [ { /BYTES, /LINES, /LIST, /NOLIST } ] <channel>
  If the channel is open, this command prints the nubmer of bytes (default)
  or lines in the file if at top level or if /LIST is included; if /NOLIST
  is given, the result is not printed.  In all cases the result is assigned
  to \v(f_count).  Synonym: FCOUNT
```

### FFLUSH

```
Syntax: FILE FLUSH <channel>
  Flushes output buffers on the given channel if it was open, forcing
  all material previously written to be committed to disk.  Synonym: FFLUSH.
  Also available as \F_flush().
```

### FI

Synonym for [FINISH](#finish).

### FILE

```
Syntax: FILE <subcommand> [ switches ] <channel> [ <data> ]
  Opens, closes, reads, writes, and manages local files.
 
The FILE commands are:
 
  FILE OPEN   (or FOPEN)   -- Open a local file.
  FILE CLOSE  (or FCLOSE)  -- Close an open file.
  FILE READ   (or FREAD)   -- Read data from an open file.
  FILE WRITE  (or FWRITE)  -- Write data to an open file.
  FILE LIST   (or FLIST)   -- List open files.
  FILE STATUS (or FSTATUS) -- Show status of a channel.
  FILE REWIND (or FREWIND) -- Rewind an open file
  FILE COUNT  (or FCOUNT)  -- Count lines or bytes in an open file
  FILE SEEK   (or FSEEK)   -- Seek to specified spot in an open file.
  FILE FLUSH  (or FFLUSH)  -- Flush output buffers for an open file.
 
Type HELP FILE OPEN or HELP FOPEN for details about FILE OPEN;
type HELP FILE CLOSE or HELP FCLOSE for details about FILE CLOSE, and so on.
 
The following variables are related to the FILE command:
 
  \v(f_max)     -- Maximum number of files that can be open at once
  \v(f_error)   -- Completion code of most recent FILE command or function
  \v(f_count)   -- Result of most recent FILE COUNT command
 
The following functions are related to the FILE command:
 
  \F_eof()      -- Check if channel is at EOF
  \F_pos()      -- Get channel read/write position (byte number)
  \F_line()     -- Get channel read/write position (line number)
  \F_handle()   -- Get file handle
  \F_status()   -- Get channel status
  \F_getchar()  -- Read character
  \F_getline()  -- Read line
  \F_getblock() -- Read block
  \F_putchar()  -- Write character
  \F_putline()  -- Write line
  \F_putblock() -- Write block
  \F_errmsg()   -- Error message from most recent FILE command or function
 
Type HELP <function-name> for information about each one.
```

### FIN

Synonym for [FINISH](#finish).

### FIND

Synonyms: GREP, SEARCH

```
Syntax: GREP [ options ] pattern filespec
  Searches through the given file or files for the given character string
  or pattern.  In the normal case, all lines containing any text that matches
  the pattern are printed.  Pattern syntax is as described in HELP PATTERNS
  except that '*' is implied at the beginning unless the pattern starts with
  '^' and also at the end unless the pattern ends with '$'.  Therefore,
  "grep something *.txt" lists all lines in all *.txt files that contain
  the word "something", but "grep ^something *.txt" lists only the lines
  that START with "something".  The command succeeds if any of the given
  files contains any lines that match the pattern, otherwise it fails.
  Synonym: FIND.
 
Only one filespec can be given.  To search multiple files that can't
be represented by a wildcard use {file1,file2,file3,...} (in braces).
 
File selection options:
  /NOBACKUPFILES
    Excludes backup files (like oofa.txt.~3~) from the search.
  /DOTFILES
    Includes files whose names start with dot (.) in the search.
  /NODOTFILES
    Excludes files whose names start with dot (.) from the search.
  /RECURSIVE
    Searches through files in subdirectories too.
  /TYPE:TEXT
    Search only text files (requires FILE SCAN ON).
  /TYPE:BINARY
    Search only binary files (requires FILE SCAN ON).
 
Pattern-matching options:
  /NOCASE
    Ignores case of letters when comparing.  Depends on the underlying
    operating system APIs to work for non-ASCII character sets.
  /NOMATCH
    Searches for lines that do NOT match the pattern.
  /EXCEPT:pattern
    Exclude lines that match the main pattern that also match this pattern.
  /VERBATIM
    The search string is taken literally; variables are not evaluated.
    This allows you to (for example) search Kermit scripts that contain
    variable names, function names, etc (that begin with '\').
 
Display options:
  /COUNT:variable-name
    For each file, prints only the filename and a count of matching lines
    and assigns the total match count to the variable, if one is given.
  /DISPLAY:number
    How many matching lines to show.  The default is to show all matching
    lines.  Synonym:/SHOW.
  /NAMEONLY
    Prints the name of each file that contains at least one matching line,
    one name per line, rather than showing each matching line.
  /NOLIST
    Doesn't print anything (but sets SUCCESS or FAILURE appropriately).
  /LINENUMBERS
    Precedes each file line by its line number within the file.
  /PAGE
    Pauses after each screenful.
  /NOPAGE
    Doesn't pause after each screenful.
 
Result disposition options:
  /OUTPUT:name
    Sends results to the given file.
  /ARRAY:&x
    Returns the results in the specified array; one line per array element.
  /MACRO:name
    Returns the results in the macro whose name is given.  If a macro
    of the same name already exists, the grep results (if there are any)
    replace its previous value.  Synonym: DEFINE.
```

### FINISH

Synonyms: F, FI, FIN

```
Syntax: FINISH
  Tells the remote Kermit server to shut down without logging out.
```

### FIREWALL

```
Firewall Traversal in C-Kermit
 
The simplist form of firewall traversal is the HTTP CONNECT command. The
CONNECT command was implemented to allow a public web server which usually
resides on the boundary between the public and private networks to forward
HTTP requests from clients on the private network to public web sites.  To
allow secure web connections, the HTTP CONNECT command authenticates the
client with a username/password and then establishes a tunnel to the
desired host.
 
Web servers that support the CONNECT command can be configured to allow
outbound connections for authenticated users to any TCP/IP hostname-port
combination accessible to the Web server.  HTTP CONNECT can be used only
with TCP-based protocols.  Protocols such as Kerberos authentication that
use UDP/IP cannot be tunneled using HTTP CONNECT.
 
SET TCP HTTP-PROXY [switches] [<hostname or ip-address>[:<port>]]
  If a hostname or ip-address is specified, Kermit uses the given
  proxy server when attempting outgoing TCP connections.  If no hostnamer
  or ip-address is specified, any previously specified Proxy server is
  removed.  If no port number is specified, the "http" service is used.
  [switches] can be one or more of:
     /AGENT:<agent> /USER:<user> /PASSWORD:<password>
  Switch parameters are used when connecting to the proxy server and
  override any other values associated with the connection.
 
FTP is one of the few well-known Internet services that requires
multiple connections.  As described above, FTP originally required the
server to establish the data connection to the client using a destination
address and port provided by the client.  This doesn't work with port
filtering firewalls.
 
Later, FTP protocol added a "passive" mode, in which connections for
the data channels are created in the reverse direction.  Instead of the
server establishing a connection to the client, the client makes a second
connection with the server as the destination.  This works just fine as
long as the client is behind the firewall and the server is in public
address space.  If the server is behind a firewall then the traditional
active mode must be used.  If both the client and server are behind their
own port filtering firewalls then data channels cannot be established.
 
In Kermit's FTP client, passive mode is controlled with the command:
 
  SET FTP PASSIVE-MODE { ON, OFF }
 
The default is ON, meaning to use passive mode.
```

### FLIST

```
Syntax: FILE LIST
  Lists the channel number, name, modes, and position of each file opened
  with FILE OPEN.  Synonym: FLIST.
```

### FO

Synonym for [FOR](#for).

### FOPEN

```
Syntax: FILE OPEN [ switches ] <variable> <filename>
  Opens the file indicated by <filename> in the mode indicated by the
  switches, if any, or if no switches are included, in read-only mode, and
  assigns a channel number for the file to the given variable.
  Synonym: FOPEN.  Switches:
 
/READ
  Open the file for reading.
 
/STDIN
  Tells Kermit to read from Standard Input.  In this case you don't specify
  a filename.
 
/STDOUT
  Tells Kermit to write to Standard Output.  In this case you don't specify
  a filename.
 
/STDERR
  Tells Kermit to write to Standard Error.  In this case you don't specify
  a filename.
 
/WRITE
  Open the file for writing.  If /READ was not also specified, this creates
  a new file.  If /READ was specified, the existing file is preserved, but
  writing is allowed.  In both cases, the read/write pointer is initially
  at the beginning of the file.
 
/APPEND
  If the file does not exist, create a new file and open it for writing.
  If the file exists, open it for writing, but with the write pointer
  positioned at the end.
 
/BINARY
  This option is ignored in UNIX.
 
Switches can be combined in an way that makes sense and is supported by the
underlying operating system.
```

### FOR

Synonym: FO

```
Syntax: FOR variablename initial-value final-value increment { commandlist }
  FOR loop.  Execute the comma-separated commands in the commandlist the
  number of times given by the initial value, final value and increment.
  Example:  FOR \%i 10 1 -1 { pause 1, echo \%i }
```

### FORWARD

```
Like GOTO, but searches only forward for the label.  See GOTO.
```

### FOT

Synonym for [DIRECTORY](#directory).

### FREAD

```
Syntax: FILE READ [ switches ] <channel> [ <variable> ]
  Reads data from the file on the given channel number into the <variable>,
  if one was given; if no variable was given, the result is printed on
  the screen.  The variable should be a macro name rather than a \%x
  variable or array element if you want backslash characters in the file to
  be taken literally.  Synonym: FREAD.  Switches:
 
/LINE
  Specifies that a line of text is to be read.  A line is defined according
  to the underlying operating system's text-file format.  For example, in
  UNIX a line is a sequence of characters up to and including a linefeed.
  The line terminator (if any) is removed before assigning the text to the
  variable.  If no switches are included with the FILE READ command, /LINE
  is assumed.
 
/SIZE:number
  Specifies that the given number of bytes (characters) is to be read.
  This gives a semblance of "record i/o" for files that do not necessarily
  contain lines.  The resulting block of characters is assigned to the
  variable without any editing.
 
/CHARACTER
  Equivalent to /SIZE:1.  If FILE READ /CHAR succeeds but the <variable> is
  empty, this indicates a NUL byte was read.
 
/TRIM
  Trims trailing whitespace from the right when used with /LINE.  Ignored
  if used with /CHAR or /SIZE.
 
/UNTABIFY
  Tells Kermit to convert tabs to spaces (assuming tabs set every 8 spaces)
  when used with /LINE.  Ignored if used with /CHAR or /SIZE.
 
Synonym: FREAD.
Also available as \F_getchar(), \F_getline(), \F_getblock().
```

### FREWIND

```
Syntax: FILE REWIND <channel>
  If the channel is open, moves the read/write pointer to the beginning of
  the file.  Equivalent to FILE SEEK <channel> 0.  Synonym: FREWIND.
  Also available as \F_rewind().
```

### FSEEK

```
Syntax: FILE SEEK [ switches ] <channel> { [{+,-}]<number>, EOF }
  Switches are /BYTE, /LINE, /RELATIVE, /ABSOLUTE, and /FIND:pattern.
  Moves the file pointer for this file to the given position in the
  file.  Subsequent FILE READs or WRITEs will take place at that position.
  If neither the /RELATIVE nor /ABSOLUTE switch is given, an unsigned
  <number> is absolute; a signed number is relative.  EOF means to move to
  the end of the file.  If a /FIND: switch is included, Kermit seeks to the
  specified spot (e.g. 0 for the beginning) and then begins searching line
  by line for the first line that matches the given pattern.  To start
  searching from the current file position specify a line number of +0.
  To start searching from the line after the current one, use +1 (etc).
  Synonym: FSEEK.
```

### FSTATUS

```
Syntax: FILE STATUS <channel>
  If the channel is open, this command shows the name of the file, the
  switches it was opened with, and the current read/write position.
  Synonym: FSTATUS
```

### FTP

```
Syntax: FTP subcommand [ operands ]
  Makes an FTP connection, or sends a command to the FTP server.
  To see a list of available FTP subcommands, type "ftp ?".
  and then use HELP FTP xxx to get help about subcommand xxx.
  Also see HELP SET FTP, HELP SET GET-PUT-REMOTE, and HELP FIREWALL.
```

### FUNCTION

```
KERMIT FUNCTIONS
   
  Functions are part of Kermit's programming language used in writing
  scripts.  They are like functions in other programming languages like C
  and Perl; each function has a name and an argument list, and it returns
  (is replaced by) a value.  In a Kermit script, the function name preceded
  by a backslash (\) and then the letter F; for example:
 
     \Findex(string1,string2).
 
  The argument list is in parentheses.  In this example the name of the
  function is 'index', the arguments are string1 and string2, and the return
  value is the starting position of string2 in string1; type HELP FUNC INDEX
  for details.
 
  Type SHOW FUNCTIONS to see a list of available functions.
 
  Type HELP FUNCTION xxx more information about specific functions:
 
   . If xxx matches only one function name the documentation for that
     function is printed; example: HELP FUNCTION INDEX.
 
  . If xxx matches more than one function name, a list of all functions
     whose names contain xxx is printed; example: HELP FUNCTION DATE.
```

### FWRITE

```
FILE WRITE [ switches ] <channel> <text>
  Writes the given text to the file on the given channel number.  The <text>
  can be literal text or a variable, or any combination.  If the text might
  contain leading or trailing spaces, it must be enclosed in braces if you
  want to preserve them.  Synonym: FWRITE.  Switches:
 
/LINE
  Specifies that an appropriate line terminator is to be added to the
  end of the <text>.  If no switches are included, /LINE is assumed.
 
/SIZE:number
  Specifies that the given number of bytes (characters) is to be written.
  If the given <text> is longer than the requested size, it is truncated;
  if is shorter, it is padded according /LPAD and /RPAD switches.  Synonym:
  /BLOCK.
 
/LPAD[:value]
  If /SIZE was given, but the <text> is shorter than the requested size,
  the text is padded on the left with sufficient copies of the character
  whose ASCII value is given to write the given length.  If no value is
  specified, 32 (the code for Space) is used.  The value can also be 0 to
  write the indicated number of NUL bytes.  If /SIZE was not given, this
  switch is ignored.
 
/RPAD[:value]
  Like LPAD, but pads on the right.
 
/STRING
  Specifies that the <text> is to be written as-is, with no terminator added.
 
/CHARACTER
  Specifies that one character should be written.  If the <text> is empty or
  not given, a NUL character is written; otherwise the first character of
  <text> is given.
 
Synonym FWRITE.
Also available as \F_putchar(), \F_putline(), \F_putblock().
```

### G

Synonym for [GET](#get).

### GE

Synonym for [GET](#get).

### GET

Synonyms: G, GE

```
Syntax: GET [ switches... ] remote-filespec [ as-name ]
  Tells the other Kermit, which must be in (or support autoswitching into)
  server mode, to send the named file or files.  If the remote-filespec or
  the as-name contain spaces, they must be enclosed in braces.  If as-name
  is the name of an existing local directory, incoming files are placed in
  that directory; if it is the name of directory that does not exist, Kermit
  tries to create it.  Optional switches include:
 
/AS-NAME:text
  Specifies "text" as the name to store the incoming file under, or
  directory to store it in.  You can also specify the as-name as the second
  filename on the GET command line.
 
/BINARY
  Performs this transfer in binary mode without affecting the global
  transfer mode.
 
/COMMAND
  Receives the file into the standard input of a command, rather than saving
  it on  disk.  The /AS-NAME or the second "filename" on the GET command
  line is interpreted as the name of a command.
 
/DELETE
  Asks the other Kermit to delete the file (or each file in the group)
  after it has been transferred successfully.
 
/EXCEPT:pattern
  Specifies that any files whose names match the pattern, which can be a
  regular filename, or may contain "*" and/or "?" metacharacters,
  are to be refused.  To specify multiple patterns (up to 8), use outer
  braces around the group, and inner braces around each pattern:
 
    /EXCEPT:{{pattern1}{pattern2}...}
 
/FILENAMES:{CONVERTED,LITERAL}
  Overrides the global SET FILE NAMES setting for this transfer only.
 
/FILTER:command
  Causes the incoming file to passed through the given command (standard
  input/output filter) before being written to disk.
 
/MOVE-TO:directory-name
  Specifies that each file that arrives should be moved to the specified
  directory after, and only if, it has been received successfully.
 
/PATHNAMES:{OFF,ABSOLUTE,RELATIVE,AUTO}
  Overrides the global SET RECEIVE PATHNAMES setting for this transfer.
 
/PIPES:{ON,OFF}
  Overrides the TRANSFER PIPES setting for this command only.  ON allows
  reception of files with names like "!tar xf -" to be automatically
  directed to a pipeline.
 
/QUIET
  Suppresses the file-transfer display.
 
/RECOVER
  Used to recover from a previously interrupted transfer; GET /RECOVER
  is equivalent REGET.  Works only in binary mode.
 
/RECURSIVE
  Tells the server to descend through the directory tree when locating
  the files to be sent.
 
/RENAME-TO:string
  Specifies that each file that arrives should be renamed as specified
  after, and only if, it has been received successfully.  The string can
  be a filename, a directory name, an expression involving variables, etc.
 
/TEXT
  Performs this transfer in text mode without affecting the global
  transfer mode.
 
/TRANSPARENT
  Inhibits character-set translation of incoming text files for the duration
  of the GET command without affecting subsequent commands.
 
Also see HELP MGET, HELP SEND, HELP RECEIVE, HELP SERVER, HELP REMOTE.
```

### GETC

```
Syntax:  GETC [ switches] [ variablename [ prompt ] ]
Example: GETC \%c { Type any character to continue...}
  Issues the prompt and sets the variable to the first character you type.
  Use braces to preserve leading and/or trailing spaces in the prompt.
 
Switches:
  /CHECK
    GETC /CHECK (no variable or prompt is given when /CHECK is used)
   succeeds if characters are waiting to be read and fails if not.
 
  /QUIET
    In case of errors, no error message is issued.
 
  /TIMEOUT:n
    Gives GETC a time limit of n seconds to wait for a character to appear;
    if no character appears within n seconds, GETC fails and (if a /QUIET
    switch was not given, an error message is printed.
```

### GETOK

```
Syntax: GETOK [ switches ] prompt
  Prints the prompt, makes user type 'yes', 'no', or 'ok', and sets SUCCESS
  or FAILURE accordingly.  The optional switches are the same as for ASK.
```

### GOTO

```
Syntax: GOTO label
  In a TAKE file or macro, go to the given label.  A label is a word on the
  left margin that starts with a colon (:).  Example:

  :oofa
  echo Hello!
  goto oofa
```

### GREP

Synonym for [FIND](#find).

### H

Synonym for [HELP](#help).

### HANGUP

```
Syntax: HANGUP
Hang up the phone or network connection.
```

### HDIRECTORY

```
  HDIRECTORY is shorthand for DIRECTORY /SORT:SIZE /REVERSE;
  it produces a listing showing the biggest files first.  See the DIRECTORY
  command for further information.
```

### HE

Synonym for [HELP](#help).

### HEAD

```
Syntax: HEAD [ switches ] filename
  Equivalent to TYPE /HEAD filename; see HELP TYPE.
```

### HELP

Synonyms: H, HE

```
C-Kermit 11.0.499, 2026/07/16, Copyright (C) 2025-2026,
  John Goerzen.
Copyright (C) 1985, 2025,
  Trustees of Columbia University in the City of New York.

  Type EXIT    to exit.
  Type INTRO   for a brief introduction to C-Kermit.
  Type LICENSE to see the C-Kermit license.
  Type HELP    followed by a command name for help about a specific command.
  Type MANUAL  to access the C-Kermit manual page.
  Type NEWS    for news about new features.
  Type SUPPORT to learn how to get technical support.
  Press ?      (question mark) at the prompt, or anywhere within a command,
               for a menu (context-sensitive help, menu on demand).
 
  Type HELP OPTIONS for help with command-line options.
 
DOCUMENTATION: "Using C-Kermit" by Frank da Cruz and Christine M. Gianone,
2nd Edition, Digital Press / Butterworth-Heinemann 1997, ISBN 1-55558-164-1,
plus supplements at http://www.kermitproject.org/ckermit.html#doc.
```

### HTTP

```
Syntax:
HTTP [ <switches> ] OPEN [{ /SSL, /TLS }] <hostname> <service/port>
  Instructs Kermit to open a new connection for HTTP communication with
  the specified host on the specified port.  The default port is "http".
  If /SSL or /TLS are specified or if the service is "https" or port 443,
  a secure connection will be established using the current authentication
  settings.  See HELP SET AUTH for details.
  If <switches> are specified, they are applied to all subsequent HTTP
  actions (GET, PUT, ...) until an HTTP CLOSE command is executed.
  A URL can be included in place of the hostname and service or port.
 
HTTP CLOSE
  Instructs Kermit to close any open HTTP connection and clear any saved
  switch values.
 
HTTP [ <switches> ] CONNECT <host>[:<port>]
  Instructs the server to establish a connection with the specified host
  and to redirect all data transmitted between Kermit and the host for the
  life of the connection.
 
HTTP [ <switches> ] GET <remote-filename> [ <local-filename> ]
  Retrieves the named file on the currently open HTTP connection.  The
  default local filename is the same as the remote filename, but with any
  path stripped.  If you want the file to be displayed on the screen instead
  of stored on disk, include the /TOSCREEN switch and omit the local
  filename.  If you give a URL instead of a remote filename, this commands
  opens the connection, GETs the file, and closes the connection; the same
  is true for the remaining HTTP commands for which you can specify a
  remote filename, directory name, or path.
 
HTTP [ <switches> ] HEAD <remote-filename> [ <local-filename> ]
  Like GET except without actually getting the file; instead it gets only
  the headers, storing them into the given file (if a local filename is
  specified), one line per header item as shown in the /ARRAY: switch
  description.
 
HTTP [ <switches> ] INDEX <remote-directory> [ <local-filename> ]
  Retrieves the file listing for the given server directory.
  NOTE: This command is not supported by most Web servers, and even when
  the server understand it, there is no stardard response format.
 
HTTP [ <switches> ] POST [ /MIME-TYPE:<type> ] <local-file> <remote-path>
     [ <dest-file> ]
  Used to send a response as if it were sent from a form.  The data to be
  posted must be read from a file.
 
HTTP [ <switches> ] PUT [ /MIME-TYPE:<type> ] <local-file> <remote-file>
     [ <dest-file> ]
  Uploads the given local file to server file.  If the remote filename is
  omitted, the local name is used, but with any path stripped.
 
HTTP [ <switches> ] DELETE <remote-filename>
  Instructs the server to delete the specified filename.
 
where <switches> are:
/AGENT:<user-agent>
  Identifies the client to the server; "C-Kermit"
  by default.
 
/HEADER:<header-line>
  Used for specifying any optional headers.  A list of headers is provided
  using braces for grouping:
 
    /HEADER:{{tag:value}{tag:value}...}
 
  For a listing of valid "tag" value and "value" formats see RFC 1945:
  "Hypertext Transfer Protocol -- HTTP/1.0".  A maximum of eight headers
  may be specified.
 
/TOSCREEN
  Display server responses on the screen.
 
/USER:<name>
  In case a page requires a username for access.
 
/PASSWORD:<password>
  In case a page requires a password for access.
 
/ARRAY:<arrayname>
  Tells Kermit to store the response headers in the given array, one line
  per element.  The array need not be declared in advance.  Example:
 
    http /array:c get kermit/index.html
    show array c
    Dimension = 9
    1. Date: Fri, 26 Nov 1999 23:12:22 GMT
    2. Server: Apache/1.3.4 (Unix)
    3. Last-Modified: Mon, 06 Sep 1999 22:35:58 GMT
    4. ETag: "bc049-f72-37d441ce"
    5. Accept-Ranges: bytes
    6. Content-Length: 3954
    7. Connection: close     
    8. Content-Type: text/html
 
As you can see, the header lines are like MIME e-mail header lines:
identifier, colon, value.  The /ARRAY switch is the only method available
to a script to process the server responses for a POST or PUT command.
 
```

### I

Synonym for [INPUT](#input).

### IF

```
Syntax: IF [NOT] condition commandlist
 
If the condition is (is not) true, do the commandlist.  The commandlist
can be a single command, or a list of commands separated by commas or
enclosed in braces.  The condition can be a single condition or a group of
conditions separated by AND (&&) or OR (||) and enclosed in parentheses.
If parentheses are used they must be surrounded by spaces.  Examples:
 
  IF EXIST oofa.txt <command>
  IF ( EXIST oofa.txt || = \v(nday) 3 ) <command>
  IF ( EXIST oofa.txt || = \v(nday) 3 ) { <command>, <command>, ... }
 
The conditions are:
 
  SUCCESS     - The previous command succeeded
  OK          - Synonym for SUCCESS
  FAILURE     - The previous command failed
  ERROR       - Synonym for FAILURE
  FLAG        - Succeeds if SET FLAG ON, fails if SET FLAG OFF
  BACKGROUND  - C-Kermit is running in the background
  FOREGROUND  - C-Kermit is running in the foreground
  REMOTE-ONLY - C-Kermit was started with the -R command-line option
  KERBANG     - A Kerbang script is running
  ALARM       - SET ALARM time has passed
  ASKTIMEOUT  - The most recent ASK, ASKQ, GETC, or GETOK timed out
  EMULATION   - Succeeds if executed while in CONNECT mode
 
  MS-KERMIT   - Program is MS-DOS Kermit
  C-KERMIT    - Program is C-Kermit
  WINDOWS     - Program is Kermit 95
  GUI         - Program runs in a GUI window
 
  AVAILABLE CRYPTO                  - Encryption is available
  AVAILABLE KERBEROS4               - Kerberos 4 authentication is available
  AVAILABLE KERBEROS5               - Kerberos 5 authentication is available
  AVAILABLE NTLM                    - NTLM authentication is available
  AVAILABLE SRP                     - SRP authentication is available
  AVAILABLE SSL                     - SSL/TLS authentication is available
  MATCH string pattern              - Succeeds if string matches pattern
  FLOAT number                      - Succeeds if floating-point number
  COMMAND word                      - Succeeds if word is built-in command
  DEFINED variablename or macroname - The named variable or macro is defined
  DECLARED arrayname                - The named array is declared
  NUMERIC variable or constant      - The variable or constant is numeric
  FUNCTION name                     - The name is of a built-in function
  EXIST filename                    - The named file exists
  ABSOLUTE filename                 - The filename is absolute, not relative
  BINARY filename                   - The file is a binary regular file
  TEXT filename                     - The file is a text regular file
  DIRECTORY string                  - The string is the name of a directory
  LINK string                       - The string is a symbolic link
  READABLE filename                 - Succeeds if the file is readable
  WRITEABLE filename                - Succeeds if the file is writeable
  NEWER file1 file2                 - The 1st file is newer than the 2nd one
  OPEN { READ-FILE,SESSION-LOG,...} - The given file or log is open
  OPEN CONNECTION                   - A connection is open
  KBHIT                             - A key has been pressed
  TRUE                              - always succeeds
  FALSE                             - always fails
 
  VERSION - equivalent to "if >= \v(version) ..."
 
  EQUAL s1 s2 - s1 and s2 (character strings or variables) are equal
  LLT   s1 s2 - s1 is lexically (alphabetically) less than s2
  LLE   s1 s2 - s1 is lexically less than or equal to s2
  LGT   s1 s2 - s1 is lexically (alphabetically) greater than s2
  LGE   s1 s2 - s1 is lexically greater than or equal to s2
  NEQ   s1 s2 - s1 is not equal to s2
 
  =  n1 n2 - n1 and n2 (numbers or variables containing numbers) are equal
  <  n1 n2 - n1 is arithmetically less than n2
  <= n1 n2 - n1 is arithmetically less than or equal to n2
  >  n1 n2 - n1 is arithmetically greater than n2
  >= n1 n2 - n1 is arithmetically greater than or equal to n2
  != n1 n2 - n1 is not equal to n2
 
  (number by itself) - fails if the number is 0, succeeds otherwise
 
  (variable name)    - If value numeric: succeeds if nonzero, fails if zero
                       NOTE: variable name must not be the same as keyword
 
The IF command may be followed on the next line by an ELSE command. Example:
 
  IF < \%x 10 ECHO It's less
  ELSE echo It's not less
 
It can also include an ELSE part on the same line if braces are used:
 
  IF < \%x 10 { ECHO It's less } ELSE { ECHO It's not less }
 
Multiple commands can be enclosed in braces, separated by commas:
 
  IF > \%n \m(max) { echo \%n > old max \m(max), .max := \%n }
 
When braces are used the command may split onto multiple lines:
 
  IF > \%n \m(max) {
      echo "\%n greater than old max \m(max)"
      .max := \%n
  } else if < \%n \m(min) {
      echo "\%n less than old min \m(min)"
      .min := \%n
  }
 
Also see HELP WILDCARD (for IF MATCH pattern syntax).
```

### IKSD

```
Syntax: IKS [ switches ] [ host [ service ] ]
  Establishes a new connection to an Internet Kermit Service daemon.
  Equivalent to SET NETWORK TYPE TCP/IP, SET HOST host KERMIT /TELNET,
  IF SUCCESS CONNECT.  If host is omitted, the previous connection (if any)
  is resumed.  Depending on how Kermit has been built switches may be
  available to require a secure authentication method and bidirectional
  encryption.  See HELP SET TELNET for more info.
 
 /AUTH:<type> is equivalent to SET TELNET AUTH TYPE <type> and
   SET TELOPT AUTH REQUIRED with the following exceptions.  If the type
   is AUTO, then SET TELOPT AUTH REQUESTED is executed and if the type
   is NONE, then SET TELOPT AUTH REFUSED is executed.
 
 /ENCRYPT:<type> is equivalent to SET TELNET ENCRYPT TYPE <type>
   and SET TELOPT ENCRYPT REQUIRED REQUIRED with the following exceptions.
   If the type is AUTO then SET TELOPT AUTH REQUESTED REQUESTED is executed
   and if the type is NONE then SET TELOPT ENCRYPT REFUSED REFUSED is
   executed.
 
 /USERID:[<name>]
   This switch is equivalent to SET LOGIN USERID <name> or SET TELNET
   ENVIRONMENT USER <name>.  If a string is given, it sent to host during
   Telnet negotiations; if this switch is given but the string is omitted,
   no user ID is sent to the host.  If this switch is not given, your
   current USERID value, \v(userid), is sent.  When a userid is sent to the
   host it is a request to login as the specified user.
 
 /PASSWORD:[<string>]
   This switch is equivalent to SET LOGIN PASSWORD.  If a string is given,
   it is treated as the password to be used (if required) by any Telnet
   Authentication protocol (Kerberos Ticket retrieval, Secure Remote
   Password, or X.509 certificate private key decryption.)  If no password
   switch is specified a prompt is issued to request the password if one
   is required for the negotiated authentication method.
```

### IN

Synonym for [INPUT](#input).

### INCREMENT

```
Syntax: INCREMENT variablename [ number ]
  Increment (add one to) the value of a variable if the current value is
  numeric.  If an optional amount is specified (as a number, a variable,
  or an arithmetic expression that evaluates to a number, or any combination)
  the variable is incremented by that number instead of 1.  The result is
  always an integer.  If floating-point numbers are given, the result is
  truncated.
 
Examples: INCR \%a, INCR dollars 100, INCR size \%n, INCR total \%x/10
```

### INPUT

Synonyms: I, IN

```
Syntax:  INPUT [ /COUNT:n /CLEAR /NOMATCH /NOWRAP ] { number-of-seconds, time-of-day } [ text ]
 
Examples:
  INPUT 5 Login:
  INPUT 23:59:59 RING
  INPUT /NOMATCH 10
  INPUT /CLEAR 10 \13\10
  INPUT /CLEAR 10 \13\10$
  INPUT /COUNT:256 10
  INPUT 10 \fpattern(<*@*.*>)
 
  Waits up to the given number of seconds, or until the given time of day,
  for the given text to arrive on the connection. For use in script programs
  with IF FAILURE or IF SUCCESS, which tell whether the desired text arrived
  within the given amount of time.
 
  The text, if given, can be a regular text or it can be a \fpattern()
  invocation, in which case it is treated as a pattern rather than a literal
  string (HELP PATTERNS for details).
 
  If the /COUNT: switch is included, INPUT waits for the given number of
  characters to arrive.
 
  If no text is specified, INPUT waits for the first character that arrives
  and makes it available in the \v(inchar) variable.  This is equivalent to
  including a /COUNT: switch with an argument of 1.
 
  If the /NOMATCH switch is included, INPUT does not attempt to match any
  characters, but continues reading from the communication connection until
  the timeout interval expires.  If the timeout interval is 0, the INPUT
  command does not wait; i.e. the given text must already be available for
  reading for the INPUT command to succeed.  If the interval is negative,
  the INPUT command waits forever.
 
  The INPUT buffer, \v(input), is normally circular.  Incoming material is
  appended to it until it reaches the end, and then it wraps around to the
  beginning.  If the /CLEAR switch is given, INPUT clears its buffer before
  reading from the connection.
 
  Typical example of use:
 
    INPUT 10 login:
    IF FAIL EXIT 1 "Timed out waiting for login prompt"
    LINEOUT myuserid
    INPUT 10 Password:
    IF FAIL EXIT 1 "Timed out waiting for Password prompt"
    LINEOUT xxxxxxx
 
  The /NOWRAP switch means that INPUT should return with failure status
  and with \v(instatus) set to 6 if its internal buffer fills up before
  any of the other completion criteria are met.  This allows for capture
  of the complete incoming data stream (except NUL bytes, which are
  discarded).  CAUTION: if the search target (if any) spans the INPUT buffer
  boundary, INPUT will not succeed.
 
  \v(instatus) values are: 0 (success), 1 (timed out), 2 (keyboard interrupt),
  3 (internal error), 4 (I/O error or connection lost), 5 (INPUT disabled),
  and 6 (buffer filled and /NOWRAP set); these are shown by \v(inmessage).
 
  Also see OUTPUT, MINPUT, REINPUT, SET INPUT and CLEAR.  See HELP PAUSE for
  details on time-of-day format and HELP PATTERNS for pattern syntax.
```

### INT

Synonym for [INTRO](#intro).

### INTR

Synonym for [INTRO](#intro).

### INTRO

Synonyms: INT, INTR, INTRODUCTION

```
The INTRO command gives a brief introduction to C-Kermit.
```

### INTRODUCTION

Synonym for [INTRO](#intro).

### K95

Synonym for [CKERMIT](#ckermit).

### KCD

```
Syntax: KCD symbolic-directory-name
  Kermit Change Directory: Like CD (q.v.) but (a) always acts locally, and
  (b) takes a symbolic directory name rather than an actual directory name.
  The symbolic names correspond to Kermit's directory-valued built-in
  variables, such as \v(download), \v(exedir), and so on.  Here's the list:
 
    download      Your download directory (if any)
    exedir        The directory where the Kermit executable resides
    home          Your home, login, or default directory
    inidir        The directory where Kermit's initialization was found
    lockdir       The UNIX UUCP lockfile directory on this computer
    startup       Your current directory at the time Kermit started
    textdir       The directory where Kermit text files reside, if any
    tmpdir        Your temporary directory
 
  Also see CD, SET FILE DOWNLOAD, SET TEMP-DIRECTORY.
```

### KERMIT

Synonym for [CKERMIT](#ckermit).

### L

Synonym for [LOG](#log).

### LCD

Synonym: LCWD

```
  LCD (LCWD) is an alias for the CD (CWD) command forcing it to execute
  on the local computer.  Also see: CD, CDUP, RCD, SET LOCUS.
```

### LCDUP

```
Change working directory to the one just above the current one.
```

### LCWD

Synonym for [LCD](#lcd).

### LDELETE

```
  LDELETE is an alias for the DELETE command forcing it to execute
  on the local computer.  Also see: DELETE, RDELETE, SET LOCUS.
```

### LDIRECTORY

```
  LDIRIRECTORY is an alias for the DIRECTORY command forcing it to execute
  on the local computer.  Also see: DIRECTORY, SET LOCUS, RDIRECTORY.
```

### LEARN

```
Syntax: LEARN [ /ON /OFF /CLOSE ] [ filename ]
  Records a login script.  If you give a filename, the file is opened for
  subsequent recording.  If you don't give any switches, /ON is assumed.
  /ON enables recording to the current file (if any); /OFF disables
  recording.  /CLOSE closes the current file (if any).  After LEARN /CLOSE
  or exit from Kermit, your script is available for execution by the TAKE
  command.
```

### LI

Synonym for [LINEOUT](#lineout).

### LICENSE

Synonym: COPYRIGHT

```
Sorry, help not available for "LICENSE"
```

### LINEOUT

Synonym: LI

```
Sorry, help not available for "lineout"
```

### LMKDIR

```
  LMKDIR is an alias for the MKDIR command forcing it to execute
  on the local computer.  Also see: MKDIR, RMKDIR, SET LOCUS.
```

### LMV

Synonym: LRENAME

```
  LRENAME is an alias for the RENAME command forcing it to execute
  on the local computer.  Also see: RENAME, RRENAME, SET LOCUS.
```

### LO

Synonym for [LOG](#log).

### LOCAL

```
Declares a variable to be local to the current macro or command file.
```

### LOCUS

```
Syntax: SET LOCUS { AUTO, LOCAL, REMOTE }
  Specifies whether unprefixed file management commands should operate
  locally or (when there is a connection to a remote FTP or Kermit
  server) sent to the server.  The affected commands are: CD (CWD), PWD,
  CDUP, DIRECTORY, DELETE, RENAME, MKDIR, and RMDIR.  To force any of
  these commands to be executed locally, give it an L-prefix: LCD, LDIR,
  etc.  To force remote execution, use the R-prefix: RCD, RDIR, and so
  on.  SHOW COMMAND shows the current Locus.
 
  By default, the Locus for file management commands is switched
  automatically whenever you make or close a connection: if you make an
  FTP connection, the Locus becomes REMOTE; if you close an FTP connection
  or make any other kind of connection, the Locus becomes LOCAL.
 
  If you give a SET LOCUS LOCAL or SET LOCUS REMOTE command, this sets
  the locus as indicated and disables automatic switching.
  SET LOCUS AUTO restores automatic switching.
```

### LOG

Synonyms: L, LO

```
Syntax: LOG (or L) log-type [ filename [ { NEW, APPEND } ] ]
 
Record information in a log file:
 
CX
  Connections made with SET LINE, SET PORT, SET HOST, DIAL, TELNET, etc.
  The default filename is CX.LOG in your home directory and APPEND is the
  default mode for opening.
 
DEBUG
  Debugging information, to help track down bugs in the C-Kermit program.
  The default log name is debug.log in current directory.
 
PACKETS
  Kermit packets, to help with protocol problems.  The default filename is
  packet.log in current directory.
 
SESSION
  Records your CONNECT session (default: session.log in current directory).
 
TRANSACTIONS
  Names and statistics about files transferred (default: transact.log in
  current directory; see HELP SET TRANSACTION-LOG for transaction-log format
  options.)
 
If you include the APPEND keyword after the filename, the existing log file,
if any, is appended to; otherwise a new file is created (except APPEND is
the default for the connection log).  Use CLOSE <keyword> to stop logging.
 
Note: The filename can also be a pipe, e.g.:
 
  log transactions |lpr
  log debug {| grep "^TELNET" > debug.log}
 
Braces are required if the pipeline or filename contains spaces.
```

### LOGIN

```
Sorry, help not available for "login"
```

### LOGOUT

```
If you haved logged in to Kermit as an Internet Kermit server, the LOGOUT
command, given at the prompt, logs you out and closes your session.
```

### LOOKUP

```
Syntax: LOOKUP name
  Looks up the given name in the dialing directory or directories, if any,
  specified in the most recent SET DIAL DIRECTORY command.  Each matching
  entry is shown, along with any transformations that would be applied to
  portable-format entries based on your locale.  HELP DIAL, HELP SET DIAL
  for further info.
```

### LPWD

```
Syntax: PWD
Print the name of the current working directory.
```

### LRENAME

Synonym for [LMV](#lmv).

### LRMDIR

```
  LRMDIR is an alias for the RMDIR command forcing it to execute
  on the local computer.  Also see: RMDIR, RRMDIR, SET LOCUS.
```

### LS

Synonym for [DIRECTORY](#directory).

### LS

```
Syntax: LS [ args ]
  Runs "ls" with the given arguments.
```

### MAIL

```
Syntax: MAIL filename address
  Equivalent to SEND /MAIL:address filename.
```

### MANUAL

```
Syntax: MANUAL [ topic ]
  Runs the "man" command on the given topic (default "kermit").
```

### MD

Synonym for [MKDIR](#mkdir).

### MESSAGE

Synonym: MSG

```
Syntax: MESSAGE text-to-print-if-debugging
  Prints the given text to stdout if SET DEBUG MESSAGE is ON; prints it
  to stderr if SET DEBUG MESSAGE is STDERR; doesn't print it at all if SET
  DEBUG MESSAGE is OFF.  Synonym: MSG.
```

### MGET

```
Syntax: MGET [ switches... ] remote-filespec [ remote-filespec ... ]
 
Just like GET (q.v.) except allows a list of remote file specifications,
separated by spaces.
```

### MINPUT

```
Syntax:  MINPUT [ switches ] n [ string1 [ string2 [ ... ] ] ]
Example: MINPUT 5 Login: {Username: } {NO CARRIER} BUSY RING
  For use in script programs.  Waits up to n seconds for any one of the
  strings to arrive on the communication device.  If no strings are given,
  the command waits for any character at all to arrive.  Strings are
  separated by spaces; use {braces} or "doublequotes" for grouping.  If
  any of the strings is encountered within the timeout interval, the command
  succeeds and the \v(minput) variable is set to the number of the string
  that was matched: 1, 2, 3, etc.  If none of the strings arrives, the
  command times out, fails, and \v(minput) is set to 0.  In all other
  respects, MINPUT is like INPUT.  See HELP INPUT for the available switches
  and other details of operation.
```

### MKDIR

Synonym: MD

```
Creates a directory.  Also see LRMDIR, RRMDIR, SET LOCUS.
```

### MMOVE

```
MMOVE is exactly like MSEND, except each file that is
sent successfully is deleted after it is sent.
```

### MORE

```
Syntax: MORE [ switches ] filename
  Equivalent to TYPE /PAGE filename; see HELP TYPE.
```

### MOVE

```
  If LOCUS is REMOTE or LOCUS is AUTO and you have an FTP connection,
  this command is equivalent to REMOTE RENAME (RREN).  Otherwise:
 
Syntax: RENAME or MOVE or MV [ switches ] name1 [ name2 ]
  Renames the source file (name1) to the target name2.  If name2 is a
  directory, name1 is allowed to contain wildcards, and the file(s) matching
  name1 are moved to directory name2, subject to rules of the underlying
  operating system regarding renaming across disk boundaries, etc. Switches:
 
  /LIST
    Print the filenames and status while renaming.  Synonyms: /LOG, /VERBOSE
 
  /NOLIST
    Rename silently (default). Synonyms: /NOLOG, /QUIET
 
  /COLLISION:{FAIL,SKIP,OVERWRITE}
    Tells what to do if a file with the given (or derived) new name already
    exists: fail (and stop without renaming any files); skip this file
    without renaming it and go on to the next one, if any; or overwrite (the
    existing file).  PROCEED is a synonym for SKIP.
 
  /SIMULATE
    Show what the effects of the RENAME command would be without actually
    renaming any files.
 
  When any of the following switches is given, name2 must either be the
  the name of a directory, or else omitted, and name1 is allowed to contain
  contain wildcards, allowing multiple files to be renamed at once. If name2
  is given, then all files matching name1 are moved to the name2 directory
  after being renamed.
 
  /LOWER:{ALL,UPPER}
    Converts letters in the filename to lowercase.  ALL means to convert
    all matching filenames, UPPER means to convert only those filenames
    that contain no lowercase letters.  The switch argument can be omitted,
    in which case ALL filenames are converted.
 
  /UPPER:{ALL,LOWER}
    Converts letters in the filename to uppercase.  ALL means to convert
    all matching filenames, LOWER means to convert only those filenames
    that contain no uppercase letters.  As with /LOWER, ALL is the default
    switch argument.
 
  /FIXSPACES:s
    Replaces all spaces in each matching filename by the string s, which may
    be empty, a single character, or a string of characters.  The default
    replacement (if no argument is given) is underscore (_).
 
  /REPLACE:{{string1}{string2}{options}}
    Replaces all or selected occurrences of string1 with string2 in the
    matching filenames.  The braces are part of the command.  The options
    string can contain the following characters:
     A: String matching is case-sensitive.
     a: String matching is case-insensitive.
     ^: String matching is anchored to the beginning of the filename.
     $: String matching is anchored to the end of the filename.
     1: Only the first occurrence of the string (if any) will be changed.
     2: Only the second occurrence, and so on for all digits up to 9.
     -: (before a digit) Occurrences are counted from the right.
     ~: (before occurrence) All occurences BUT the one given are changed.
 
  /CONVERT:cset1:cset2
    Converts each matching filename from character-set 1 to character-set 2.
    Character sets are the same as for SET FILE CHARACTER-SET.
 
  Global values for /LIST and COLLISION can be set with SET RENAME and
  displayed with SHOW RENAME.
```

### MOVE

Synonym for [RENAME](#rename).

### MPAUSE

Synonym for [MSLEEP](#msleep).

### MPUT

Synonym for [MSEND](#msend).

### MS

Synonym for [MSEND](#msend).

### MSEND

Synonyms: MPUT, MS

```
Syntax: MSEND [ switches... ] filespec [ filespec [ ... ] ]
  Sends the files specified by the filespecs.  One or more filespecs may be
  listed, separated by spaces.  Any or all filespecs may contain wildcards
  and they may be in different directories.  Alternative names cannot be
  given.  Switches include /BINARY /DELETE /MAIL /PROTOCOL /QUIET /RECOVER
  /TEXT /TYPE; see HELP SEND for descriptions.
```

### MSG

Synonym for [MESSAGE](#message).

### MSLEEP

Synonym: MPAUSE

```
Syntax:  MSLEEP [ number ]
Example: MSLEEP 500
  Do nothing for the specified number of milliseconds; if no number given,
  100 milliseconds.
```

### MV

Synonym for [RENAME](#rename).

### NEWS

```
  Prints news of new features since publication of "Using C-Kermit".
```

### NOLOCAL

```
Sorry, help not available for "nolocal"
```

### NOPUSH

```
Sorry, help not available for "nopush"
```

### O

Synonym for [OUTPUT](#output).

### OPEN

```
Syntax:  OPEN mode filename
  For use with READ and WRITE commands.  Open the local file in the
  specified mode: READ, WRITE, or APPEND.  !READ and !WRITE mean to read
  from or write to a system command rather than a file.  Examples:
 
    OPEN READ oofa.txt
    OPEN !READ sort foo.bar
```

### OPTIONS

```
Command-line options are given after the program name in the system
command that you use to start Kermit.  Example:
 
 kermit -i -s oofa.exe
 
tells Kermit to send (-s) the file oofa.exe in binary (-i) mode.
 
Command-line options are case-sensitive; "-s" is different from "-S".
 
If any "action options" are included on the command line, Kermit exits
after executing its command-line options.  If -S is included, or no action
options were given, Kermit enters its interactive command parser and
issues its prompt.
 
Command-line options are single characters preceded by dash (-).  Some
require an "argument," others do not.  If an argument contains spaces, it
must be enclosed in doublequotes:
 
 kermit -s "filename with spaces"
 
An option that does not require an argument can be bundled with other options:
 
 kermit -Qis oofa.exe
 
Exceptions to the rules:
 
 . If the first command-line option is a filename, Kermit executes commands
   from the file.  Additional command-line options can follow the filename.
 
 . The special option "=" (equal sign) or "--" (double hyphen) means to
   treat the rest of the command line as data, rather than commands; this
   data is placed in the argument vector array, \&@[], along with the other
   items on the command line, and also in the top-level \%1..\%9 variables.
 
 . A similar option "+" (plus sign) means: the name of a Kermit script
   file follows.  This file is to be executed, and its name assigned to \%0
   and \&_[0].  All subsequent command-line arguments are to be ignored by
   Kermit but made available to the script as \%1, \%2, ..., as well as
   in the argument-vector arrays.  The initialization file is not executed
   automatically in this case.
 
 . The -s option can accept multiple filenames, separated by spaces.
 
 . the -j and -J options allow an optional second argument, the TCP port
   name or number.
 
Type "help options all" to list all the command-line options.
Type "help option x" to see the help message for option x.
 
Kermit also offers a selection of "extended command-line" options.
These begin with two dashes, followed by a keyword, and then, if the option
has arguments, a colon (:) or equal sign (=) followed by the argument.
Unlike single-letter options, extended option keywords aren't case sensitive
and they can be abbreviated to any length that still distinguishes them from
other extended-option keywords.  Example:
 
  kermit --banner:oofa.txt
 
which designates the file oofa.txt to be printed upon startup, rather than
the built-in banner (greeting) text.  To obtain a list of available
extended options, type "help extended-options ?".  To get help about all
extended options, type "help extended-options".  To get help about a
particular extended option, type "help extended-option xxx", where "xxx"
is the option keyword.
```

### ORIENTATION

```
 Shows the directories important to Kermit.
```

### OUTPUT

Synonym: O

```
Syntax: OUTPUT text
  Sends the text out the communications connection, as if you had typed it
  during CONNECT mode.  The text may contain backslash codes, variables,
  etc, plus the following special codes:
 
    \N - Send a NUL (ASCII 0) character (you can't use \0 for this).
    \B - Send a BREAK signal.
    \L - Send a Long BREAK signal.
 
Also see SET OUTPUT.
```

### PASSIVE

```
Sorry, help not available for "passive"
```

### PATTERNS

```
A "pattern" is notation used in a search string when searching through
text.  C-Kermit uses three kinds of patterns: floating patterns, anchored
patterns, and wildcards.  Wildcards are anchored patterns that are used to
match file names; type HELP WILDCARD to learn about them.
 
In a pattern, certain characters are special:
 
* Matches any sequence of zero or more characters.  For example, "k*t"
  matches all strings that start with "k" and end with "t" including
  "kt", "kit", "knight", or "kermit".
 
? Matches any single character.  For example, "k????t" matches all strings
  that are exactly 6 characters long and start with "k" and end with
  with "t".  When typing commands at the prompt, you must precede any
  question mark to be used for matching by a backslash (\) to override the
  normal function of question mark in interactive commands, which is to
  provide menus and file lists.
 
[abc]
  Square brackets enclosing a list of characters matches any character in
  the list.  Example: h[aou]t matches hat, hot, and hut.
 
[a-z]
  Square brackets enclosing a range of characters matches any character in
  the range; a hyphen (-) separates the low and high elements of the range.
  For example, [a-z] matches any character from a to z.
 
[acdm-z]
  Lists and ranges may be combined.  This example matches a, c, d, or any
  letter from m through z.
 
{string1,string2,...}
  Braces enclose a list of strings to be matched.  For example:
  ker{mit,nel,beros} matches kermit, kernel, and kerberos.  The strings
  may themselves contain *, ?, [abc], [a-z], or other lists of strings.
 
To force a special pattern character to be taken literally, precede it with
a backslash, e.g. [a\-z] matches a, hyphen, or z rather than a through z.
 
A floating  pattern can also include the following special characters:
 
^ (First character of pattern) Anchors the pattern at the beginning.
$ (Last character of pattern) Anchors the pattern at the end.
 
If a floating pattern does not start with "^", the pattern can match
anywhere in the string instead of only at the beginning; in other words, a
leading "*" is assumed.  Similarly, if the pattern doesn't end with "$",
a trailing "*" is assumed.
 
The following commands and functions use floating patterns:
  GREP [ <switches> ] <pattern> <filespec>
  TYPE /MATCH:<pattern> <file>
  \farraylook(<pattern>,<arrayname>)
  \fsearch(<pattern>,<string>[,<offset>])
  \frsearch(<pattern>,<string>[,<offset>])
  The /EXCEPT: clause in SEND, GET, DELETE, etc.
 
Example:
  \fsearch(abc,xxabcxxx) succeeds because xxabcxx contains abc.
  \fsearch(^abc,xxabcxx) fails because xxabcxx does not start with abc.
 
All other commands and functions use anchored patterns, meaning that ^ and $
are not treated specially, and * is not assumed at the beginning or end of
the pattern.  This is true mainly of filename patterns (wildcards), since
you would not want a command like "delete x" to delete all files whose
names contained "x"!
 
You can use anchored patterns not only in filenames, but also in SWITCH
case labels, in the INPUT and MINPUT commands, and in file binary- and
text-patterns for filenames.  The IF MATCH pattern is also anchored.
```

### PAUSE

Synonym: SLEEP

```
Syntax:  PAUSE [ { number-of-seconds, hh:mm:ss } ]
Example: PAUSE 3  or  PAUSE 14:52:30
  Do nothing for the specified number of seconds or until the given time of
  day in 24-hour hh:mm:ss notation.  If the time of day is earlier than the
  current time, it is assumed to be tomorrow.  If no argument given, one
  second is used.  The pause can be interrupted by typing any character on
  the keyboard unless SLEEP CANCELLATION is OFF.  If interrupted, PAUSE
  fails, otherwise it succeeds.  Synonym: SLEEP.
```

### PDIAL

```
Syntax: PDIAL phonenumber
  Partially dials a phone number.  Like DIAL but does not wait for carrier
  or CONNECT message.
```

### PING

```
Syntax: PING [ IP-hostname-or-number ]
  Checks if the given IP network host is reachable.  Default host is from
  most recent SET HOST or TELNET command.  Runs system PING program, if any.
```

### PIPE

```
Syntax: PIPE [ command ]
Makes a connection through the program whose command line is given. Example:

 pipe rlogin xyzcorp.com
```

### POP

Synonym for [END](#end).

### PRINT

```
Syntax: PRINT file [ options ]
  Prints the local file on a local printer with the given options.  Also see
  HELP SET PRINTER.
```

### PROMPT

```
Syntax: PROMPT [ text ]
  Enters interactive command level from within a script in such a way that
  the script can be continued with an END or RETURN command.  STOP, EXIT,
  SHOW STACK, TRACE, and Ctrl-C all have their normal effects.  The PROMPT
  command allows variables to be examined or changed, or any other commands
  to be given, in any number, prior to returning to the script, allowing
  Kermit to serve as its own debugger; adding the PROMPT command to a script
  is like setting a breakpoint.  If the optional text is included, it is
  used as the new prompt for this level, e.g. "prompt Breakpoint_1>".
```

### PSEND

```
Syntax: PSEND filespec position [name]

  Just like SEND, except sends the file starting at the given byte position.
```

### PTY

```
Sorry, help not available for "pty"
```

### PU

Synonym for [PUSH](#push).

### PURGE

```
Syntax: PURGE [ switches ] [ filespec ]
  Deletes backup files; that is, files whose names end in ".~n~", where
  n is a number.  PURGE by itself deletes all backup files in the current
  directory.  Switches:
 
/AFTER:date-time
  Specifies that only those files modified after the given date-time are
  to be purged.  HELP DATE for info about date-time formats.
 
/BEFORE:date-time
  Specifies that only those files modified before the given date-time
  are to be purged.
 
/NOT-AFTER:date-time
  Specifies that only those files modified at or before the given date-time
  are to be purged.
 
/NOT-BEFORE:date-time
  Specifies that only those files modified at or after the given date-time
  are to be purged.
 
/LARGER-THAN:number
  Specifies that only those files longer than the given number of bytes are
  to be purged.
 
/SMALLER-THAN:number
  Specifies that only those files smaller than the given number of bytes are
  to be purged.
 
/EXCEPT:pattern
  Specifies that any files whose names match the pattern, which can be a
  regular filename or may contain wildcards, are not to be purged.  To
  specify multiple patterns (up to 8), use outer braces around the group
  and inner braces around each pattern:
 
    /EXCEPT:{{pattern1}{pattern2}...}
 
/DOTFILES
  Include (purge) files whose names begin with ".".
 
/NODOTFILES
  Skip (don't purge) files whose names begin with ".".
 
/RECURSIVE
  Descends through the current or specified directory tree.
 
/KEEP:n
  Retain the 'n' most recent (highest-numbered) backup files for each file.
  By default, none are kept.  If /KEEP is given without a number, 1 is used.
 
/LIST
  Display each file as it is processed and say whether it is purged or kept.
  Synonyms: /LOG, /VERBOSE.
 
/NOLIST
  The PURGE command should operate silently (default).
  Synonyms: /NOLOG, /QUIET.
 
/HEADING
  Print heading and summary information.
 
/NOHEADING
  Don't print heading and summary information.
 
/PAGE
  When /LIST is in effect, pause at the end of each screenful, even if
  COMMAND MORE-PROMPTING is OFF.
 
/NOPAGE
  Don't pause, even if COMMAND MORE-PROMPTING is ON.
 
/ASK
  Interactively ask permission to delete each backup file.
 
/NOASK
  Purge backup files without asking permission.
 
/SIMULATE
  Inhibits the actual deletion of files; use to preview which files would
  actually be deleted.  Implies /LIST.
 
Use SET OPTIONS PURGE [ switches ] to change defaults; use SHOW OPTIONS to
display customized defaults.  Also see HELP DELETE, HELP WILDCARD.
```

### PUSH

Synonyms: !, @, PU, RUN, SPAWN

```
Syntax: !, @, RUN, PUSH, or SPAWN, optionally followed by a command.
  Gives the command to the local operating system's command processor, and
  displays the results on the screen.  If the command is omitted, enters the
  system's command line interpreter or shell; exit from it (the command for
  this is usually EXIT or QUIT or LOGOUT) to return to Kermit.
```

### PUT

Synonym for [SEND](#send).

### PUTENV

```
Syntax: PUTENV name value
  Creates or modifies the environment variable with the given name to have
  the given value.  Purpose: to pass parameters to subprocesses without
  having them appear on the command line.  If the value is blank (empty),
  the variable is deleted.  The result is visible to this instantiation of
  C-Kermit via \$(name) and to any inferior processes by whatever method
  they use to access environment variables.  The value may be enclosed in
  doublequotes or braces, but it need not be; if it is the outermost
  doublequotes or braces are removed.
 
  Note the syntax:
    PUTENV name value
  not:
    PUTENV name=value
 
  There is no equal sign between name and value, and the name itself may
  not include an equal sign.
```

### PWD

```
Syntax: PWD
Print the name of the current working directory.
```

### Q

Synonym for [QUIT](#quit).

### QUERY

Synonym: RQUERY

```
  QUERY and RQUERY are short forms of REMOTE QUERY.
```

### QUIT

Synonym: Q

```
Syntax: EXIT (or QUIT) [ number [ text ] ]
  Exits from the Kermit program, closing all open files and devices.
  If a number is given it becomes Kermit's exit status code.  If text is
  included, it is printed.  Also see SET EXIT.
```

### R

Synonym for [RECEIVE](#receive).

### RASG

Synonym: RASSIGN

```
  RASG and RASSIGN are short forms of REMOTE ASSIGN.
```

### RASSIGN

Synonym for [RASG](#rasg).

### RCD

Synonym: RCWD

```
  RCD and RCWD are short forms of REMOTE CD.
```

### RCDUP

```
  RCDUP is a short forms of REMOTE CDUP.
```

### RCOPY

```
  RCOPY is a short form of REMOTE COPY.
```

### RCWD

Synonym for [RCD](#rcd).

### RDELETE

```
  RDELETE is a short form of REMOTE RELETE.
```

### RDIRECTORY

```
  RDIRECTORY is a short form of REMOTE DIRECTORY.
```

### READ

```
Syntax: READ variablename
  Reads a line from the currently open READ or !READ file into the variable
  (see OPEN).
```

### RECEIVE

Synonym: R

```
Syntax: RECEIVE (or R) [ switches... ] [ as-name ]
  Wait for a file to arrive from the other Kermit, which must be given a
  SEND command.  If the optional as-name is given, the incoming file or
  files are stored under that name, otherwise it will be stored under
  the name it arrives with.  If the filespec denotes a directory, the
  incoming file or files will be placed in that directory.
 
Optional switches include:
 
/AS-NAME:text
  Specifies "text" as the name to store the incoming file under.
  You can also specify the as-name as a filename on the command line.
 
/BINARY
  Skips text-mode conversions unless the incoming file arrives with binary
  attribute
 
/COMMAND
  Receives the file into the standard input of a command, rather than saving
  it on disk.  The /AS-NAME or the "filename" on the RECEIVE command line
  is interpreted as the name of a command.
 
/EXCEPT:pattern
  Specifies that any files whose names match the pattern, which can be a
  regular filename, or may contain "*" and/or "?" metacharacters,
  are to be refused.  To specify multiple patterns (up to 8), use outer
  braces around the group, and inner braces around each pattern:
 
    /EXCEPT:{{pattern1}{pattern2}...}
 
/FILENAMES:{CONVERTED,LITERAL}
  Overrides the global SET FILE NAMES setting for this transfer only.
 
/FILTER:command
  Causes the incoming file to passed through the given command (standard
  input/output filter) before being written to disk.
 
/MOVE-TO:directory-name
  Specifies that each file that arrives should be moved to the specified
  directory after, and only if, it has been received successfully.
 
/PATHNAMES:{OFF,ABSOLUTE,RELATIVE,AUTO}
  Overrides the global SET RECEIVE PATHNAMES setting for this transfer.
 
/PIPES:{ON,OFF}
  Overrides the TRANSFER PIPES setting for this command only.  ON allows
  reception of files with names like "!tar xf -" to be automatically
  directed to a pipeline.
 
/PROTOCOL:name
  Use the given protocol to receive the incoming file(s).
 
/QUIET
  When receiving in local mode, this suppresses the file-transfer display.
 
/RECURSIVE
  Equivalent to /PATHNAMES:RELATIVE.
 
/RENAME-TO:string
  Specifies that each file that arrives should be renamed as specified
  after, and only if, it has been received successfully.  The string should
  normally contain variables like \v(filename) or \v(filenum).
 
/TEXT
  Forces text-mode conversions unless the incoming file has the binary
  attribute
 
/TRANSPARENT
  Inhibits character-set translation of incoming text files for the duration
  of the RECEIVE command without affecting subsequent commands.
 
Also see HELP SEND, HELP GET, HELP SERVER, HELP REMOTE.
```

### RED

Synonym for [REDIAL](#redial).

### REDI

Synonym for [REDIAL](#redial).

### REDIAL

Synonyms: RED, REDI

```
Redial the number given in the most recent DIAL commnd.
```

### REDIRECT

Synonym: <

```
Syntax: REDIRECT command
  Runs the given local command with its standard input and output redirected
  to the current SET LINE or SET HOST communications path.
  Synonym: < (Left angle bracket).
```

### REDO

Synonyms: ^, RR

```
 Syntax: REDO xxx (or) ^xxx
 Re-executes the most recent command starting with xxx.
```

### REGET

```
Syntax: REGET filespec

  Ask a server to RESEND a file to C-Kermit.
```

### REINPUT

```
Syntax: REINPUT n string
  Looks for the string in the text that has recently been INPUT, set SUCCESS
  or FAILURE accordingly.  Timeout, n, must be specified but is ignored.
```

### REM

Synonym for [REMOTE](#remote).

### REMO

Synonym for [REMOTE](#remote).

### REMOTE

Synonyms: REM, REMO

```
The REMOTE command sends file management instructions or other commands
to a Kermit or FTP server.  If you have a single connection, the command is
directed to the server you are connected to; if you have multiple connections
the command is directed according to your GET-PUT-REMOTE setting.
Type REMOTE ? to see a list of available remote commands.  Type HELP REMOTE
xxx to get further information about a particular remote command xxx.
 
All REMOTE commands except LOGIN and LOGOUT have R-command shortcuts;
for example, RDIR for REMOTE DIR, RCD for REMOTE CD, etc.
 
Also see: HELP SET LOCUS, HELP FTP, HELP SET GET-PUT-REMOTE.
```

### REMOVE

```
REMOVE BINARY-PATTERNS [ <pattern> [ <pattern> ... ] ]
  Removes the pattern(s), if any, from the SET FILE BINARY-PATTERNS list
 
REMOVE TEXT-PATTERNS [ <pattern> [ <pattern> ... ] ]
  Removes the given patterns from the SET FILE TEXT-PATTERNS list.
  Use SHOW PATTERNS to see the lists.  See HELP SET FILE for further info.
```

### RENAME

Synonyms: MOVE, MV

```
  If LOCUS is REMOTE or LOCUS is AUTO and you have an FTP connection,
  this command is equivalent to REMOTE RENAME (RREN).  Otherwise:
 
Syntax: RENAME or MOVE or MV [ switches ] name1 [ name2 ]
  Renames the source file (name1) to the target name2.  If name2 is a
  directory, name1 is allowed to contain wildcards, and the file(s) matching
  name1 are moved to directory name2, subject to rules of the underlying
  operating system regarding renaming across disk boundaries, etc. Switches:
 
  /LIST
    Print the filenames and status while renaming.  Synonyms: /LOG, /VERBOSE
 
  /NOLIST
    Rename silently (default). Synonyms: /NOLOG, /QUIET
 
  /COLLISION:{FAIL,SKIP,OVERWRITE}
    Tells what to do if a file with the given (or derived) new name already
    exists: fail (and stop without renaming any files); skip this file
    without renaming it and go on to the next one, if any; or overwrite (the
    existing file).  PROCEED is a synonym for SKIP.
 
  /SIMULATE
    Show what the effects of the RENAME command would be without actually
    renaming any files.
 
  When any of the following switches is given, name2 must either be the
  the name of a directory, or else omitted, and name1 is allowed to contain
  contain wildcards, allowing multiple files to be renamed at once. If name2
  is given, then all files matching name1 are moved to the name2 directory
  after being renamed.
 
  /LOWER:{ALL,UPPER}
    Converts letters in the filename to lowercase.  ALL means to convert
    all matching filenames, UPPER means to convert only those filenames
    that contain no lowercase letters.  The switch argument can be omitted,
    in which case ALL filenames are converted.
 
  /UPPER:{ALL,LOWER}
    Converts letters in the filename to uppercase.  ALL means to convert
    all matching filenames, LOWER means to convert only those filenames
    that contain no uppercase letters.  As with /LOWER, ALL is the default
    switch argument.
 
  /FIXSPACES:s
    Replaces all spaces in each matching filename by the string s, which may
    be empty, a single character, or a string of characters.  The default
    replacement (if no argument is given) is underscore (_).
 
  /REPLACE:{{string1}{string2}{options}}
    Replaces all or selected occurrences of string1 with string2 in the
    matching filenames.  The braces are part of the command.  The options
    string can contain the following characters:
     A: String matching is case-sensitive.
     a: String matching is case-insensitive.
     ^: String matching is anchored to the beginning of the filename.
     $: String matching is anchored to the end of the filename.
     1: Only the first occurrence of the string (if any) will be changed.
     2: Only the second occurrence, and so on for all digits up to 9.
     -: (before a digit) Occurrences are counted from the right.
     ~: (before occurrence) All occurences BUT the one given are changed.
 
  /CONVERT:cset1:cset2
    Converts each matching filename from character-set 1 to character-set 2.
    Character sets are the same as for SET FILE CHARACTER-SET.
 
  Global values for /LIST and COLLISION can be set with SET RENAME and
  displayed with SHOW RENAME.
```

### REP

Synonym for [TYPE](#type).

### REPLAY

Synonym for [TYPE](#type).

### REPUT

Synonym for [RESEND](#resend).

### RES

Synonym for [RESEND](#resend).

### RESE

Synonym for [RESEND](#resend).

### RESEND

Synonyms: REPUT, RES, RESE

```
Syntax: RESEND filespec [name]

  Resends the file or files, whose previous transfer was interrupted.
  Picks up from where previous transfer left off, IF the receiver kept the
  partially received file.  Works only for binary-mode transfers.
  Requires file-transfer partner to support recovery.  Synonym: REPUT.
```

### RESET

```
Closes all open files and logs.
```

### RET

Synonym for [RETURN](#return).

### RETRIEVE

```
Just like GET but asks the server to delete each file that has been
sent successfully.
```

### RETURN

Synonym: RET

```
Syntax: RETURN [ value ]
  Return from a macro.  An optional return value can be given for use with
  \fexecute(macro), which allows macros to be used like functions.
```

### REXIT

```
  REXIT is a short form of REMOTE EXIT.
```

### RHELP

```
  RHELP is a short form of REMOTE HELP.
```

### RHOST

```
  RHOST is a short form of REMOTE HOST.
```

### RKERMIT

```
  RKERMIT is a short form of REMOTE KERMIT.
```

### RLOGIN

```
Syntax: RLOGIN [ switches ] [ host [ username ] ]
  Equivalent to SET NETWORK TYPE TCP/IP, SET HOST host [ service ] /RLOGIN,
  IF SUCCESS CONNECT.  If host is omitted, the previous connection (if any)
  is resumed.  Depending on how Kermit has been built switches may be
  available to require Kerberos authentication and DES encryption.
```

### RM

Synonym for [DELETE](#delete).

### RMDIR

```
Removes a directory.  Also see LRMDIR, RRMDIR, SET LOCUS.
```

### RMESSAGE

Synonym: RMSG

```
  RMESSAGE and RMSG are short forms of REMOTE MESSAGE.
```

### RMKDIR

```
  RMKDIR is a short form of REMOTE MKDIR.
```

### RMSG

Synonym for [RMESSAGE](#rmessage).

### ROBUST

```
FAST, CAUTIOUS, and ROBUST are predefined macros that set several
file-transfer parameters at once to achieve the desired file-transfer goal.
FAST chooses a large packet size, a large window size, and a fair amount of
control-character unprefixing at the risk of possible failure on some
connections.  FAST is the default tuning in C-Kermit 7.0 and later.  In case
FAST file transfers fail for you on a particular connection, try CAUTIOUS.
If that fails too, try ROBUST.  You can also change the definitions of each
macro with the DEFINE command.  To see the current definitions, type
"show macro fast", "show macro cautious", or "show macro robust".
```

### RPRINT

```
  RPRINT is a short form of REMOTE PRINT.
```

### RPWD

```
  RPWD is a short form of REMOTE PWD.
```

### RQUERY

Synonym for [QUERY](#query).

### RR

Synonym for [REDO](#redo).

### RRENAME

```
  RRENAME is a short form of REMOTE RENAME.
```

### RRMDIR

```
  RRMDIR is a short form of REMOTE RMDIR.
```

### RSET

```
  RSET is a short form of REMOTE SET.
```

### RSPACE

```
  RSPACE is a short form of REMOTE SPACE.
```

### RTYPE

```
  RTYPE is a short form of REMOTE TYPE.
```

### RUN

Synonym for [PUSH](#push).

### RWHO

```
  RWHO is a short form of REMOTE WHO.
```

### S

Synonym for [SEND](#send).

### SAVE

```
Syntax: SAVE item filename { NEW, APPEND }
  Saves the requested material in the given file.  A new file is created
  by default; include APPEND at the end of the command to append to an
  existing file.  Items:
    KEYMAP               Saves the current key settings.
    COMMAND HISTORY      Saves the current command recall (history) buffer
```

### SC

Synonym for [SCRIPT](#script).

### SCR

Synonym for [SCRIPT](#script).

### SCREEN

```
Syntax: SCREEN { CLEAR, CLEOL, MOVE row column }
  Performs screen-formatting actions.  Correct operation of these commands
  depends on proper terminal setup on both ends of the connection -- mainly
  that the host terminal type is set to agree with the kind of terminal or
  the emulation you are viewing C-Kermit through.
 
SCREEN CLEAR
  Moves the cursor to home position and clears the entire screen.
  Synonyms: CLS, CLEAR SCREEN.
 
SCREEN CLEOL
  Clears from the current cursor position to the end of the line.
 
SCREEN MOVE row column
  Moves the cursor to the indicated row and column.  The row and column
  numbers are 1-based so on a 24x80 screen, the home position is 1 1 and
  the lower right corner is 24 80.  If a row or column number is given that
  too large for what Kermit or the operating system thinks is your screen
  size, the appropriate number is substituted.
 
Also see:
  SHOW VARIABLE TERMINAL, SHOW VARIABLE COLS, SHOW VAR ROWS, SHOW COMMAND.
```

### SCRIPT

Synonyms: SC, SCR

```
Syntax: SCRIPT text
  A limited and cryptic "login assistant", carried over from old C-Kermit
  releases for comptability, but not recommended for use.  Instead, please
  use the full script programming language described in chapters 17-19 of
  "Using C-Kermit".
 
  Login to a remote system using the text provided.  The login script
  is intended to operate similarly to UNIX uucp "L.sys" entries.
  A login script is a sequence of the form:
 
    expect send [expect send] . . .
 
  where 'expect' is a prompt or message to be issued by the remote site, and
  'send' is the names, numbers, etc, to return.  The send may also be the
  keyword EOT to send Control-D, or BREAK (or \\b) to send a break signal.
  Letters in send may be prefixed by ~ to send special characters:
 
  ~b backspace, ~s space, ~q '?', ~n linefeed, ~r return, ~c don't
  append a return, and ~o[o[o]] for octal of a character.  As with some
  UUCP systems, sent strings are followed by ~r unless they end with ~c.
 
  Only the last 7 characters in each expect are matched.  A null expect,
  e.g. ~0 or two adjacent dashes, causes a short delay.  If you expect
  that a sequence might not arrive, as with uucp, conditional sequences
  may be expressed in the form:
 
    -send-expect[-send-expect[...]]
 
  where dashed sequences are followed as long as previous expects fail.
```

### SEARCH

Synonym for [FIND](#find).

### SEND

Synonyms: PUT, S

```
Syntax: SEND (or S) [ switches...] [ filespec [ as-name ] ]
  Sends the file or files specified by filespec.  If the filespec is omitted
  the SEND-LIST is used (HELP ADD for more info).  The filespec may contain
  wildcard characters.  An 'as-name' may be given to specify the name(s)
  the files(s) are sent under; if the as-name is omitted, each file is
  sent under its own name.  Also see HELP MSEND, HELP WILDCARD.
  Optional switches include:
 
/ARRAY:<arrayname>
  Specifies that the data to be sent comes from the given array, such as
  \&a[].  A range may be specified, e.g. SEND /ARRAY:&a[100:199].  Leave
  the brackets empty or omit them altogether to send the whole 1-based array.
  Include /TEXT to have Kermit supply a line terminator at the end of each
  array element (and translate character sets if character-set translations
  are set up), or /BINARY to treat the array as one long string of characters
  to be sent as-is.  If an as-name is not specified, the array is sent with
  the name _ARRAY_X_, where "X" is replaced by actual array letter.
 
/AS-NAME:<text>
  Specifies <text> as the name to send the file under instead of its real
  name.  This is equivalent to giving an as-name after the filespec.
 
/BINARY
  Performs this transfer in binary mode without affecting the global
  transfer mode.
 
/TEXT
  Performs this transfer in text mode without affecting the global
  transfer mode.
 
/TRANSPARENT
  Inhibits character-set translation for text files for the duration of
  the SEND command without affecting subsequent commands.
 
/NOBACKUPFILES
  Skip (don't send) Kermit or EMACS backup files (files with names that
  end with .~n~, where n is a number).
 
/DOTFILES
  Include (send) files whose names begin with ".".
 
/NODOTFILES
  Don't send files whose names begin with ".".
 
/FOLLOWLINKS
  Send files that are pointed to by symbolic links.
 
/NOFOLLOWLINKS
  Skip over symbolic links (default).
 
/COMMAND
  Sends the output from a command, rather than the contents of a file.
  The first "filename" on the SEND command line is interpreted as the name
  of a command; the second (if any) is the as-name.
 
/FILENAMES:{CONVERTED,LITERAL}
  Overrides the global SET FILE NAMES setting for this transfer only.
 
/PATHNAMES:{OFF,ABSOLUTE,RELATIVE}
  Overrides the global SET SEND PATHNAMES setting for this transfer.
 
/FILTER:command
  Specifies a command (standard input/output filter) to pass the file through
  before sending it.
 
/DELETE
  Deletes the file (or each file in the group) after it has been sent
  successfully (applies only to real files).
 
/QUIET
  When sending in local mode, this suppresses the file-transfer display.
 
/RECOVER
  Used to recover from a previously interrupted transfer; SEND /RECOVER
  is equivalent RESEND (use in binary mode only).
 
/RECURSIVE
  Tells C-Kermit to look not only in the given or current directory for
  files that match the filespec, but also in all its subdirectories, and
  all their subdirectories, etc.
 
/RENAME-TO:name
  Tells C-Kermit to rename each source file that is sent successfully to
  the given name (usually you should include \v(filename) in the new name,
  which is replaced by the original filename.
 
/MOVE-TO:directory
  Tells C-Kermit to move each source file that is sent successfully to
  the given directory.
 
/STARTING:number
  Starts sending the file from the given byte position.
  SEND /STARTING:n filename is equivalent to PSEND filename n.
 
/SUBJECT:text
  Specifies the subject of an email message, to be used with /MAIL.  If the
  text contains spaces, it must be enclosed in braces.
 
/MAIL:address
  Sends the file as e-mail to the given address; use with /SUBJECT:.
 
/PRINT:options
  Sends the file to be printed, with optional options for the printer.
 
/PROTOCOL:name
  Uses the given protocol to send the file (Kermit, Zmodem, etc) for this
  transfer without changing global protocol.
 
/AFTER:date-time
  Specifies that only those files modified after the given date-time are
  to be sent.  HELP DATE for info about date-time formats.
 
/BEFORE:date-time
  Specifies that only those files modified before the given date-time
  are to be sent.
 
/NOT-AFTER:date-time
  Specifies that only those files modified at or before the given date-time
  are to be sent.
 
/NOT-BEFORE:date-time
  Specifies that only those files modified at or after the given date-time
  are to be sent.
 
/LARGER-THAN:number
  Specifies that only those files longer than the given number of bytes are
  to be sent.
 
/SMALLER-THAN:number
  Specifies that only those files smaller than the given number of bytes are
  to be sent.
 
/EXCEPT:pattern
  Specifies that any files whose names match the pattern, which can be a
  regular filename, or may contain "*" and/or "?" metacharacters,
  are not to be sent.  To specify multiple patterns (up to 8), use outer
  braces around the group, and inner braces around each pattern:
 
    /EXCEPT:{{pattern1}{pattern2}...}
 
/TYPE:{ALL,TEXT,BINARY}
  Send only files of the given type (see SET FILE SCAN).
 
/LISTFILE:filename
  Specifies the name of a file that contains the list of names of files
  that are to be sent.  The filenames should be listed one name per line
  in this file (but a name can contain wildcards).
 
Also see HELP RECEIVE, HELP GET, HELP SERVER, HELP REMOTE.
```

### SERVER

```
Syntax: SERVER
  Enter server mode on the current connection.  All further commands
  are taken in packet form from the other Kermit program.  Use FINISH,
  BYE, or REMOTE EXIT to get C-Kermit out of server mode.
```

### SET

```
  The SET command establishes communication, file, scripting, or other
  parameters.  The SHOW command can be used to display the values of
  SET parameters.  Help is available for each individual parameter;
  type HELP SET ? to see what's available.
```

### SEXPRESSION

Synonym: (

```
Syntax: (operation operand [ operand [ ... ] ])
 
  C-Kermit includes a simple LISP-like S-Expression parser operating on
  numbers only.  An S-Expression is always enclosed in parentheses.  The
  parentheses can contain (a) a number, (b) a variable, (c) a function that
  returns a number, or (d) an operator followed by one or more operands.
  Operands can be any of (a) through (c) or an S-Expression.  Numbers can be
  integers or floating-point.  Any operand that is not a number and does not
  start with backslash (\) is treated as a Kermit macro name.  Operators:
 
 Operator  Action                                 Example           Value
  EVAL (.)  Returns the contained value            (6)               6
  QUOTE (') Inhibits evaluation of following value (quote a)         a
  SETQ      Assigns a value to a global variable   (setq a 2)        2
  LET       Assigns a value to a local variable    (let b -1.3)     -1.3
  +         Adds all operands (1 or more)          (+ a b)           0.7
  -         Subtracts all operands (1 or more)     (- 9 5 2 1)       1
  *         Multiplies all operands (1 or more)    (* a (+ b 1) 3)  -1.8
  /         Divides all operands (1 or more)       (/ b a 2)        -0.325
  ^         Raise given number to given power      (^ 3 2)           9
  ++        Increments a variable                  (++ a 1.2)        3.2
  --        Decrements a variable                  (-- a)            1
  ABS       Absolute value of 1 operand            (abs (* a b 3))   7.8
  MAX       Maximum of all operands (1 or more)    (max 1 2 3 4)     4
  MIN       Minimum of all operands (1 or more)    (min 1 2 3 4)     1
  MOD       Modulus of all operands (1 or more)    (mod 7 4 2)       1
  TRUNCATE  Integer part of floating-point operand (truncate 1.333)  1
  CEILING   Ceiling of floating-point operand      (ceiling 1.25)    2
  FLOOR     Floor of floating-point operand        (floor 1.25)      1
  ROUND     Operand rounded to nearest integer     (round 1.75)      2
  ROUND     ...or to given number of decimals      (round 1.7584 2)  1.76
  SQRT      Square root of 1 operand               (sqrt 2)          1.414..
  EXP       e (2.71828..) to the given power       (exp -1)          0.367..
  SIN       Sine of angle expressed in radians     (sin (/ pi 2))    1.0
  COS       Cosine of given number                 (cos pi)         -1.0
  TAN       Tangent of given number                (tan pi)          0.0
  LOG       Natural log (base e) of given number   (log 2.7183)      1.000..
  LOG10     Log base 10 of given number            (log10 1000)      3.0
 
Predicate operators return 0 if false, 1 if true, and if it is the outermost
operator, sets SUCCESS or FAILURE accordingly:
 
  <         Operands in strictly descending order  (< 6 5 4 3 2 1)   1
  <=        Operands in descending order           (<= 6 6 5 4 3 2)  1
  !=        Operands are not equal                 (!= 1 1 1.0)      0
  =   (==)  All operands are equal                 (= 3 3 3 3)       1
  >         Operands in strictly ascending order   (> 1 2 3 4 5 6)   1
  >=        Operands in ascending order            (> 1 1 2 3 4 5)   1
  AND (&&)  Operands are all true                  (and 1 1 1 1 0)   0
  OR  (||)  At least one operand is true           (or 1 1 1 1 0)    1
  XOR       Logical Exclusive OR                   (xor 3 1)         0
  NOT (!)   Reverses truth value of operand        (not 3)           0
 
Bit-oriented operators:
 
  &         Bitwise AND                            (& 7 2)           2
  |         Bitwise OR                             (| 1 2 3 4)       7
  #         Bitwise Exclusive OR                   (# 3 1)           2
  ~         Reverses all bits                      (~ 3)            -4
 
Operators that work on truth values:
 
  IF        Conditional evaluation                 (if (1) 2 3)      2
 
Operators can also be names of Kermit macros that return either numeric
values or no value at all.
 
Built-in constants are:
 
  t         True (1)
  nil       False (empty)
  pi        The value of Pi (3.1415926...)
 
If SET SEXPRESSION TRUNCATE-ALL-RESULTS is ON, all results are trunctated
to integer values by discarding any fractional part.  Otherwise results
are floating-point if there fractional part and integer otherwise.
If SET SEXPRESSION ECHO-RESULT is AUTO (the default), the value of the
S-Expression is printed if the S-Expression is given at top level; if ON,
it is printed at any level; if OFF it is not printed.  At all levels, the
variable \v(sexpression) is set to the most recent S-Expression, and
\v(svalue) is set to its value.  You can use the \fsexpresssion() function
to evaluate an S-Expression anywhere in a Kermit command.
```

### SH

Synonym for [SHOW](#show).

### SHIFT

```
Syntax: SHIFT [ n ]
  Shifts script command line or macro or TAKE file argument variables
  \%1..9 or \&_[1..n] n places to the left; default n = 1.
```

### SHOW

Synonym: SH

```
  Display current values of various items (SET parameters, variables, etc).
  Type SHOW ? for a list of categories.
```

### SITE

```
Sorry, help not available for "site"
```

### SLEEP

Synonym for [PAUSE](#pause).

### SORT

```
Syntax: ARRAY verb operands...
 
Declares arrays and performs various operations on them.  Arrays have
the following syntax:
 
  \&a[n]
 
where "a" is a letter and n is a number or a variable with a numeric value
or an arithmetic expression.  The value of an array element can be anything
at all -- a number, a character, a string, a filename, etc.
 
The following ARRAY verbs are available:
 
[ ARRAY ] DECLARE arrayname[n] [ = initializers... ]
  Declares an array of the given size, n.  The resulting array has n+1
  elements, 0 through n.  Array elements can be used just like any other
  variables.  Initial values can be given for elements 1, 2, ... by
  including = followed by one or more values separated by spaces.  If you
  omit the size, the array is sized according to the number of initializers;
  if none are given the array is destroyed and undeclared if it already
  existed.  The ARRAY keyword is optional.  Synonym: [ ARRAY ] DCL.
 
[ ARRAY ] UNDECLARE arrayname
  Destroys and undeclares the given array.  Synonym: ARRAY DESTROY.
 
ARRAY SHOW [ arrayname ]
  Displays the contents of the given array.  A range specifier can be
  included to display a segment of the array, e.g. "array show \&a[1:24]."
  If the arrayname is omitted, all declared arrays are listed, but their
  contents is not shown.  Synonym: SHOW ARRAY.
 
ARRAY CLEAR arrayname
  Clears all elements of the array, i.e. sets them to empty values.
  You may include a range specifier to clear a segment of the array rather
  than the whole array, e.g. "array clear \%a[22:38]"
 
ARRAY SET arrayname value
  Sets all elements of the array to the given value.  You may specify a
  range to set a segment of the array, e.g. "array set \%a[2:9] 0"
 
ARRAY RESIZE arrayname number
  Changes the size of the given array, which must already exist, to the
  number given.  If the number is smaller than the current size, the extra
  elements are discarded; if it is larger, new empty elements are added.
 
ARRAY COPY array1 array2
  Copies array1 to array2.  If array2 has not been declared, it is created
  automatically.  If it array2 does exist, array1 is copied INTO it, as
  much as will fit.  Range specifiers may be given on one or both arrays.
 
ARRAY LINK array1 arra2
  Makes array1 a link to array2.
 
[ ARRAY ] SORT [ switches ] array-name [ array2 ]
  Sorts the given array lexically according to the switches.  Element 0 of
  the array is excluded from sorting by default.  The ARRAY keyword is
  optional.  If a second array name is given, that array is sorted according
  to the first one.  Switches:
 
  /CASE:{ON,OFF}
    If ON, alphabetic case matters; if OFF it is ignored.  If this switch is
    omitted, the current SET CASE setting applies.
 
  /KEY:number
    Position (1-based column number) at which comparisons begin, 1 by default.
 
  /NUMERIC
    Specifies a numeric rather than lexical sort.
 
  /RANGE:low[:high]
    The range of elements, low through high, to be sorted.  If this switch
    is not given, elements 1 through the dimensioned size are sorted.  If
    :high is omitted, the dimensioned size is used.  To include element 0 in
    a sort, use /RANGE:0 (to sort the whole array) or /RANGE:0:n (to sort
    elements 0 through n).  You can use a range specifier in the array name
    instead of the /RANGE switch.
 
  /REVERSE
    Sort in reverse order.  If this switch is not given, the array is sorted
    in ascending order.
 
Various functions are available for array operations; see HELP FUNCTION for
details.  These include \fdimension(), \farraylook(), \ffiles(), \fsplit(),
and many more.
```

### SP

Synonym for [SPACE](#space).

### SPA

Synonym for [SPACE](#space).

### SPACE

Synonyms: SP, SPA

```
Syntax: SPACE
  Display disk usage in current device and/or directory
```

### SPAWN

Synonym for [PUSH](#push).

### SSH

```
Syntax: SSH [ options ] <hostname> [ command ]
  Makes an SSH connection using the external ssh program via the SET SSH
  COMMAND string, which is "ssh -e none" by default.  Options for the
  external ssh program may be included.  If the hostname is followed by a
  command, the command is executed on the host instead of an interactive
  shell.
 
  Equivalent to SET HOST /PTY /CONNECT ssh -e none hostname
```

### STA

Synonym for [STATISTICS](#statistics).

### STAT

Synonym for [STATISTICS](#statistics).

### STATISTICS

Synonyms: STA, STAT

```
Syntax: STATISTICS [/BRIEF]
  Display statistics about most recent file transfer
```

### STATUS

```
STATUS is the same as SHOW STATUS; prints SUCCESS or FAILURE for the
previous command.
```

### STOP

```
Syntax: STOP [ number [ message ] ]
  Stop executing the current macro or TAKE file and return immediately to
  the Kermit prompt.  Number is a return code.  Message printed if given.
```

### SUCCEED

```
Always succeeds.
```

### SUPPORT

Synonym: BUG

```
Describes how to get technical support.
```

### SUSPEND

Synonym: Z

```
Syntax: SUSPEND or Z
  Suspends Kermit.  Continue Kermit with the appropriate system command,
  such as fg.
```

### SWITCH

```
Syntax: SWITCH <variable> { case-list }
  Selects from a group of commands based on the value of a variable.
  The case-list is a series of lines like these:
 
    :x, command, command, ..., break
 
  where "x" is a possible value for the variable.  At the end of the
  case-list, you can put a "default" label to catch when the variable does
  not match any of the labels:
 
    :default, command, command, ...
 
The case label "x" can be a character, a string, a variable, a function
invocation, a pattern, or any combination of these.  See HELP WILDCARDS
for information about patterns.
```

### TA

Synonym for [TAKE](#take).

### TAIL

```
Syntax: TAIL [ switches ] filename
  Equivalent to TYPE /TAIL filename; see HELP TYPE.
```

### TAKE

Synonym: TA

```
Syntax: TAKE filename [ arguments ]
  Tells Kermit to execute commands from the named file.  Optional argument
  words, are automatically assigned to the macro argument variables \%1
  through \%9.  Kermit command files may themselves contain TAKE commands,
  up to any reasonable depth of nesting.
```

### TAPI

```
 This command is not configured in this version of Kermit.
```

### TEL

Synonym for [TELNET](#telnet).

### TELNET

Synonym: TEL

```
Syntax: TELNET [ switches ] [ host [ service ] ]
  Equivalent to SET NETWORK TYPE TCP/IP, SET HOST host [ service ] /TELNET,
  IF SUCCESS CONNECT.  If host is omitted, the previous connection (if any)
  is resumed.  Depending on how Kermit has been built switches may be
  available to require a secure authentication method and bidirectional
  encryption.  See HELP SET TELNET for more info.
 
 /AUTH:<type> is equivalent to SET TELNET AUTH TYPE <type> and
   SET TELOPT AUTH REQUIRED with the following exceptions.  If the type
   is AUTO, then SET TELOPT AUTH REQUESTED is executed and if the type
   is NONE, then SET TELOPT AUTH REFUSED is executed.
 
 /ENCRYPT:<type> is equivalent to SET TELNET ENCRYPT TYPE <type>
   and SET TELOPT ENCRYPT REQUIRED REQUIRED with the following exceptions.
   If the type is AUTO then SET TELOPT AUTH REQUESTED REQUESTED is executed
   and if the type is NONE then SET TELOPT ENCRYPT REFUSED REFUSED is
   executed.
 
 /USERID:[<name>]
   This switch is equivalent to SET LOGIN USERID <name> or SET TELNET
   ENVIRONMENT USER <name>.  If a string is given, it sent to host during
   Telnet negotiations; if this switch is given but the string is omitted,
   no user ID is sent to the host.  If this switch is not given, your
   current USERID value, \v(userid), is sent.  When a userid is sent to the
   host it is a request to login as the specified user.
 
 /PASSWORD:[<string>]
   This switch is equivalent to SET LOGIN PASSWORD.  If a string is given,
   it is treated as the password to be used (if required) by any Telnet
   Authentication protocol (Kerberos Ticket retrieval, Secure Remote
   Password, or X.509 certificate private key decryption.)  If no password
   switch is specified a prompt is issued to request the password if one
   is required for the negotiated authentication method.
```

### TELOPT

```
TELOPT { AO, AYT, BREAK, CANCEL, EC, EL, EOF, EOR, GA, IP, DMARK, NOP, SE,
         SUSP, SB [ option ], DO [ option ], DONT [ option ],
         WILL [ option ], WONT [option] }
  This command lets you send all the Telnet protocol commands.  Note that
  certain commands do not require a response, and therefore can be used as
  nondestructive "probes" to see if the Telnet session is still open;
  e.g.:
 
    set host xyzcorp.com
    ...
    telopt nop
    telopt nop
    if fail stop 1 Connection lost
 
  TELOPT NOP is sent twice because the failure of the connection will not
  be detected until the second send is attempted.  This command is meant
  primarily as a debugging tool for the expert user.
```

### TERMINAL

```
Sorry, help not available for "terminal"
```

### TEXT

Synonym for [ASCII](#ascii).

### TOUCH

```
Syntax: TOUCH [ switches ] filespec
  Updates the modification time of the given file or files to the current
  date and time or to the date and time specified in the /MODTIME: switch.
  If the filespec is the name of a single file that does not exist, the file
  is created.  The following switches can be used to restrict the files
  to be touched according to various criteria:
 
   /FILES           Select files but not directories.
   /DIRECTORIES     Select directories but not files.
   /ALL           + Select both files and directories.
   /AFTER:          Select files modified after the given date
   /BEFORE:         Select files modified before the given date
   /LARGER:         Select files larger than the given size in bytes
   /SMALLER:        Select files smaller than the given size in bytes
   /EXCEPT:         Exclude the given files (list or pattern)
   /DOTFILES        Include files whose names start with dot (period).
   /NODOTFILES    + Don't include files whose names start with dot.
   /FOLLOWLINKS     For symbolic link touch the linked-to file, not the link
   /NOFOLLOWLINKS + Select the link itself, not the file it links to.
   /NOLINKS         Skip over symbolic links.
   /BACKUP        + Include backup files (names end with .~n~).
   /NOBACKUPFILES   Don't include backup files.
   /TYPE:           Select only files of the given type, TEXT or BINARY.
   /RECURSIVE       Descend through subdirectories.
   /NORECURSIVE   + Don't descend through subdirectories.
 
 Action switches:
 
   /MODTIME:        Changes the modification time for the selected files.
                     in numeric yyyy:mm:dd:hh:mm:ss format.
                     if hh:mm:ss omitted time is set to 00:00:00
   /SIMULATE        List files that would be touched, but don't touch them.
   /LIST            Show which files are being touched.
 
Factory defaults are marked with +.  Use HELP DATE to learn the date-time
formats usable with /MODTIME:.  If a /MODTIME: switch is not given, each
selected file gets a modification time equal to the current clock time.
You can use the /SIMULATE switch in combination with other switches to see
which files will be affected without actually changing their dates.
```

### TRACE

```
Syntax: TRACE { /ON, /OFF } { ASSIGNMENTS, COMMAND-LEVEL, ALL }
  Turns tracing of the given object on or off.
```

### TRANSLATE

Synonym for [CONVERT](#convert).

### TRANSMIT

Synonyms: XM, XMIT

```
Syntax: TRANSMIT [ switches ] filename
  Sends the contents of a file, without any error checking or correction,
  to the computer on the other end of your SET LINE or SET HOST connection
  (or if C-Kermit is in remote mode, displays it on the screen).  The
  filename is the name of a single file (no wildcards) to be sent or, if
  the /PIPE switch is included, the name of a command whose output is to be
  sent.
 
  The file is sent according to your current FILE TYPE setting (BINARY or
  TEXT), which you can override with a /BINARY or /TEXT switch without
  changing the global setting.  In text mode, it is sent a line at a time,
  with carriage return at the end of each line (as if you were typing it at
  your keyboard), and C-Kermit waits for a linefeed to echo before sending
  the next line; use /NOWAIT to eliminate the feedback requirement.  In
  binary mode, it is sent a character at a time, with no feedback required.
 
  Normally the transmitted material is echoed to your screen.  Use SET
  TRANSMIT ECHO OFF or the /NOECHO switch to suppress echoing.  Note that
  TRANSMIT /NOECHO /NOWAIT /BINARY is a special case, that more or less
  blasts the file out at full speed.
 
  Character sets are translated according to your current FILE and TERMINAL
  CHARACTER-SET settings when TRANSMIT is in text mode.  Include /TRANSPARENT
  to disable character-set translation in text mode (/TRANSPARENT implies
  /TEXT).
 
  There can be no guarantee that the other computer will receive the file
  correctly and completely.  Before you start the TRANSMIT command, you
  must put the other computer in data collection mode, for example by
  starting a text editor.  TRANSMIT may be interrupted by Ctrl-C.  Synonym:
  XMIT.  See HELP SET TRANSMIT for further information.
```

### TYPE

Synonyms: REPLAY, REP

```
Syntax: TYPE [ switches... ] file
  Displays a file on the screen.  Pauses automatically at end of each
  screenful if COMMAND MORE-PROMPTING is ON.  Optional switches:
 
  /PAGE
     Pause at the end of each screenful even if COMMAND MORE-PROMPTING OFF.
     Synonym: /MORE
  /NOPAGE
     Don't pause at the end of each screen even if COMMAND MORE-PROMPTING ON.
  /HEAD:n
     Only type the first 'n' lines of the file.
  /TAIL:n
     Only type the last 'n' lines of the file.
  /MATCH:pattern
     Only type lines that match the given pattern.  HELP WILDCARDS for info
     info about patterns.  /HEAD and /TAIL apply after /MATCH.
  /PREFIX:string
     Print the given string at the beginning of each line.
  /NUMBER
     Add line numbers (conflicts with /PREFIX)
  /WIDTH:number
     Truncate each line at the given column number before printing.
  /COUNT
     Count lines (and matches) and print the count(s) but not the lines.
  /CHARACTER-SET:name
     Translates from the named character set.
  /TRANSLATE-TO:name
     Translates to the named character set (default = current file charset).
  /TRANSPARENT
     Inhibits character-set translation.
  /INTERPRET
     Shows the file with Kermit backslash escapes interpreted.
  /OUTPUT:name
     Sends results to the given file.  If this switch is omitted, the
     results appear on your screen.  This switch overrides any express or
     implied /PAGE switch.
 
You can use SET OPTIONS TYPE to set the defaults for /PAGE or /NOPAGE and
/WIDTH.  Use SHOW OPTIONS to see current TYPE options.
```

### UNDCL

Synonym for [UNDECLARE](#undeclare).

### UNDECLARE

Synonym: UNDCL

```
Sorry, help not available for "undeclare"
```

### UNDEFINE

```
Syntax:  UNDEFINE variable-name
  Undefines a macro or variable.
```

### USER

```
 Equivalent to FTP USER.
```

### V

Synonym for [DIRECTORY](#directory).

### VDIRECTORY

Synonym for [DIRECTORY](#directory).

### VERSION

Synonym: ABOUT

```
Syntax: VERSION
Displays the program version number.
```

### VOID

```
Syntax: VOID text
  Like ECHO but doesn't print anything; can be used to invoke functions
  when you don't need to display or use their results.
```

### WAIT

```
Syntax: WAIT { number-of-seconds, hh:mm:ss } [ <what> ]
 
Examples:
  wait 5 cd cts
  wait 23:59:59 cd
 
  Waits up to the given number of seconds or the given time of day for the
  specified item or event, which can be FILE, the name(s) of one or more
  modem signals, or nothing.  If nothing is specified, WAIT acts like SLEEP.
  If one or more modem signal names are given, Kermit waits for the specified
  modem signals to appear on the serial communication device.
  Sets FAILURE if the signals do not appear in the given time or interrupted
  from the keyboard during the waiting period.
 
Signals:
  cd  = Carrier Detect;
  dsr = Dataset Ready;
  cts = Clear To Send;
  ri  = Ring Indicate.
 
If you want Kermit to wait for a file event, then the syntax is:
 
  WAIT <time> FILE { CREATION, DELETION, MODIFICATION } <filename>
 
where <time> is as above, and <filename> is the name of a single file.
Kermit waits up to the given amount of time for the specified event to occur
with the specified file, succeeds if it does, fails if it doesn't.
```

### WDIRECTORY

```
  WDIRECTORY is shorthand for DIRECTORY /SORT:DATE /REVERSE;
  it produces a listing in reverse chronological order.  See the DIRECTORY
  command for further information.
```

### WERMIT

Synonym for [CKERMIT](#ckermit).

### WHERE

```
Syntax: WHERE
  Tells where your transferred files went.
```

### WHILE

```
Syntax: WHILE condition { commandlist }
  WHILE loop.  Execute the comma-separated commands in the bracketed
  commandlist while the condition is true.  Conditions are the same as for
  IF commands.
```

### WHO

```
Syntax: WHO [ user ]
Displays info about the user.
```

### WILDCARDS

```
A "wildcard" is a notation used in a filename to match multiple files.
For example, in "send *.txt" the asterisk is a wildcard.  Kermit commands
that accept filenames also accepts wildcards, except commands that are
allowed to operate on only one file, such as TRANSMIT.
This version of Kermit accepts the following wildcards:
 
* Matches any sequence of zero or more characters.  For example, "ck*.c"
  matches all files whose names start with "ck" and end with ".c"
  including "ck.c".
 
? Matches any single character.  For example, "ck?.c" matches all files
  whose names are exactly 5 characters long and start with "ck" and end
  with ".c".  When typing commands at the prompt, you must precede any
  question mark to be used for matching by a backslash (\) to override the
  normal function of question mark in interactive commands, which is to
  provide menus and file lists.  You don't, however, need to quote filename
  question marks in command files (script programs).
 
[abc]
  Square brackets enclosing a list of characters matches any character in
  the list.  Example: ckuusr.[ch] matches ckuusr.c and ckuusr.h.
 
[a-z]
  Square brackets enclosing a range of characters matches any character in
  the range; a hyphen (-) separates the low and high elements of the range.
  For example, [a-z] matches any character from a to z.
 
[acdm-z]
  Lists and ranges may be combined.  This example matches a, c, d, or any
  letter from m through z.
 
{string1,string2,...}
  Braces enclose a list of strings to be matched.  For example:
  ck{ufio,vcon,cmai}.c matches ckufio.c, ckvcon.c, or ckcmai.c.  The strings
  may themselves contain *, ?, [abc], [a-z], or other lists of strings.
 
To force a special pattern character to be taken literally, precede it with
a backslash, e.g. [a\-z] matches a, hyphen, or z rather than a through z.
Or tell Kermit to SET WILDCARD-EXPANSION OFF before entering or referring
to the filename.
 
Similar notation can be used in general-purpose string matching.  Type HELP
PATTERNS for details.  Also see HELP SET MATCH.
```

### WR

Synonym for [WRITE](#write).

### WRI

Synonym for [WRITE](#write).

### WRIT

Synonym for [WRITE](#write).

### WRITE

Synonyms: WR, WRI, WRIT

```
Syntax: WRITE name text
  Writes the given text to the named log or file.  The text text may include
  backslash codes, and is not terminated by a newline unless you include the
  appropriate code.  The name parameter can be any of the following:
 
   DEBUG-LOG
   ERROR (standard error)
   FILE (the OPEN WRITE, OPEN !WRITE, or OPEN APPEND file, see HELP OPEN)
   PACKET-LOG
   SCREEN (compare with ECHO)
   SESSION-LOG
   TRANSACTION-LOG
```

### WRITE-LINE

Synonym: WRITELN

```
WRITE-LINE (WRITELN) is just like WRITE, but includes a line terminator
at the end of text.  See WRITE.
```

### WRITELN

Synonym for [WRITE-LINE](#write-line).

### XECHO

```
Syntax: XECHO text
  Just like ECHO but does not add a line terminator to the text.  See ECHO.
```

### XIF

```
Syntax: XIF condition { commandlist } [ ELSE { commandlist } ]
  Obsolete.  Same as IF (see HELP IF).
```

### XLATE

Synonym for [CONVERT](#convert).

### XM

Synonym for [TRANSMIT](#transmit).

### XMESSAGE

Synonym: XMSG

```
Syntax: XMESSAGE text-to-print-if-debugging
  Like MESSAGE, except does not include a line terminator at the end.
  Prints the given text to stdout if SET DEBUG MESSAGE is ON; prints it
  to stderr if SET DEBUG MESSAGE is STDERR; doesn't print it at all if SET
  DEBUG MESSAGE is OFF.  Synonym: XMSG.
```

### XMIT

Synonym for [TRANSMIT](#transmit).

### XMSG

Synonym for [XMESSAGE](#xmessage).

### Z

Synonym for [SUSPEND](#suspend).

## SET/SHOW Parameters

### SET ALARM

```
Syntax: SET ALARM [ { seconds, hh:mm:ss } ]
  Number of seconds from now, or time of day, after which IF ALARM
  will succeed.  0, or no time at all, means no alarm.
```

Compile-time default, from `SHOW ALARM`:

```
(no alarm set)
```

### SET ASK-TIMER

```
Syntax: SET ASK-TIMER number
  For use with ASK, ASKQ, GETOK, and GETC.  If ASK-TIMER is set to a number
  greater than 0, these commands will time out after the given number of
  seconds with no response.  This command is "sticky", so to revert to
 untimed ASKs after a timed one, use SET ASK-TIMER 0.  Also see IF ASKTIMEOUT.
```

### SET ATTRIBUTES

```
Syntax: SET ATTRIBUTES name ON or OFF
 
  Use this command to enable (ON) or disable (OFF) the transmission of
  selected file attributes along with each file, and to handle or ignore
  selected incoming file attributes, including:
 
   CHARACTER-SET:  The transfer character set for text files
   DATE:           The file's creation date
   DISPOSITION:    Unusual things to do with the file, like MAIL or PRINT
   LENGTH:         The file's length
   PROTECTION:     The file's protection (permissions)
   SYSTEM-ID:      Machine/Operating system of origin
   TYPE:           The file's type (text or binary)
 
You can also specify ALL to select all of them.  Examples:
 
   SET ATTR DATE OFF
   SET ATTR LENGTH ON
   SET ATTR ALL OFF
 
Also see HELP SET SEND and HELP SET RECEIVE.
```

Compile-time default, from `SHOW ATTRIBUTES`:

```
Attributes: on
 Blocksize: on
 Date: on
 Disposition: on
 Encoding (Character Set): on
 Length: on
 Type (text/binary): on
 System ID: on
 System Info: on
 Permissions In:  on
 Permissions Out: on
```

### SET AUTHENTICATION

```
Synatx: SET AUTHENTICATION <auth_type> <parameter> <value>
  Sets defaults for the AUTHENTICATE command:
 
In all of the following commands "SSL" and "TLS" are aliases.
 
SET AUTHENTICATION { SSL, TLS } CIPHER-LIST <list of ciphers>
Applies to both SSL and TLS.  A colon separated list of any of the following
(case sensitive) options depending on the options chosen when OpenSSL was 
compiled: 
 
  Key Exchange Algorithms:
    "kRSA"      RSA key exchange
    "kDHr"      Diffie-Hellman key exchange (key from RSA cert)
    "kDHd"      Diffie-Hellman key exchange (key from DSA cert)
    "kEDH"      Ephemeral Diffie-Hellman key exchange (temporary key)
    "kKRB5"     Kerberos 5
 
  Authentication Algorithm:
    "aNULL"     No authentication
    "aRSA"      RSA authentication
    "aDSS"      DSS authentication
    "aDH"       Diffie-Hellman authentication
    "aKRB5"     Kerberos 5
 
  Cipher Encoding Algorithm:
    "eNULL"     No encodiing
    "DES"       DES encoding
    "3DES"      Triple DES encoding
    "RC4"       RC4 encoding
    "RC2"       RC2 encoding
    "IDEA"      IDEA encoding
 
  MAC Digest Algorithm:
    "MD5"       MD5 hash function
    "SHA1"      SHA1 hash function
    "SHA"       SHA hash function (should not be used)
 
  Aliases:
    "SSLv2"     all SSL version 2.0 ciphers (should not be used)
    "SSLv3"     all SSL version 3.0 ciphers
    "EXP"       all export ciphers (40-bit)
    "EXPORT56"  all export ciphers (56-bit)
    "LOW"       all low strength ciphers (no export)
    "MEDIUM"    all ciphers with 128-bit encryption
    "HIGH"      all ciphers using greater than 128-bit encryption
    "RSA"       all ciphers using RSA key exchange
    "DH"        all ciphers using Diffie-Hellman key exchange
    "EDH"       all ciphers using Ephemeral Diffie-Hellman key exchange
    "ADH"       all ciphers using Anonymous Diffie-Hellman key exchange
    "DSS"       all ciphers using DSS authentication
    "KRB5"      all ciphers using Kerberos 5 authentication
    "NULL"      all ciphers using no encryption
 
Each item in the list may include a prefix modifier:
 
    "+"         move cipher(s) to the current location in the list
    "-"         remove cipher(s) from the list (may be added again by
                a subsequent list entry)
    "!"         kill cipher from the list (it may not be added again
                by a subsequent list entry)
 
If no modifier is specified the entry is added to the list at the current 
position.  "+" may also be used to combine tags to specify entries such as 
"RSA+RC4" describes all ciphers that use both RSA and RC4.
 
For example, all available ciphers not including ADH key exchange:
 
  ALL:!ADH:RC4+RSA:+HIGH:+MEDIUM:+LOW:+SSLv2:+EXP
 
All algorithms including ADH and export but excluding patented algorithms: 
 
  HIGH:MEDIUM:LOW:EXPORT56:EXP:ADH:!kRSA:!aRSA:!RC4:!RC2:!IDEA
 
The OpenSSL command 
 
  openssl.exe ciphers -v <list of ciphers> 
 
may be used to list all of the ciphers and the order described by a specific
<list of ciphers>.
 
SET AUTHENTICATION { SSL, TLS } CRL-DIR <directory>
specifies a directory that contains certificate revocation files where each
file is named by the hash of the certificate that has been revoked.
 
  OpenSSL expects the hash symlinks to be made like this:
 
    ln -s crl.pem `openssl crl -hash -noout -in crl.pem`.r0
 
  Since not all file systems have symlinks you can use the following command
  in Kermit to copy the crl.pem file to the hash file name.
 
     copy crl.pem {\fcommand(openssl.exe crl -hash -noout -in crl.pem).r0}
 
  This produces a hash based on the issuer field in the CRL such 
  that the issuer field of a Cert may be quickly mapped to the 
  correct CRL.
 
SET AUTHENTICATION { SSL, TLS } CRL-FILE <filename>
specifies a file that contains a list of certificate revocations.
 
SET AUTHENTICATION { SSL, TLS } DEBUG { ON, OFF }
specifies whether debug information should be displayed about the SSL/TLS
connection.  When DEBUG is ON, the VERIFY command does not terminate
connections when set to FAIL-IF-NO-PEER-CERT when a certificate is
presented that cannot be successfully verified.  Instead each error
is displayed but the connection automatically continues.
 
SET AUTHENTICATION { SSL, TLS } DH-PARAM-FILE <filename>
  Specifies a file containing DH parameters which are used to generate
  temporary DH keys.  If a DH parameter file is not provided Kermit uses a
  fixed set of parameters depending on the negotiated key length.  Kermit
  provides DH parameters for key lengths of 512, 768, 1024, 1536, and 2048
  bits.
 
SET AUTHENTICATION { SSL, TLS } DSA-CERT-CHAIN-FILE <filename>
  Specifies a file containing a DSA certificate chain to be sent along with
  the DSA-CERT to the peer.  This file must only be specified if Kermit is
  being used as a server and the DSA certificate was signed by an
  intermediary certificate authority.
 
SET AUTHENTICATION { SSL, TLS } DSA-CERT-FILE <filename>
  Specifies a file containing a DSA certificate to be sent to the peer to 
  authenticate the host or end user.  The file may contain the matching DH 
  private key instead of using the DSA-KEY-FILE command.
 
SET AUTHENTICATION { SSL, TLS } DSA-KEY-FILE <filename>
Specifies a file containing the private DH key that matches the DSA 
certificate specified with DSA-CERT-FILE.  This command is only necessary if
the private key is not appended to the certificate in the file specified by
DSA-CERT-FILE.
 
  Note: When executing a script in the background or when it is
  running as an Internet Kermit Service Daemon, Kermit cannot support 
  encrypted private keys.  When attempting to load a private key that is
  encrypted, a prompt will be generated requesting the passphrase necessary
  to decrypt the keyfile.  To automate access to the private key you must
  decrypt the encrypted keyfile and create an unencrypted keyfile for use
  by Kermit.  This can be accomplished by using the following command and
  the passphrase:
 
  openssl dsa -in <encrypted-key-file> -out <unencrypted-key-file>
 
SET AUTHENTICATION { SSL, TLS } RANDOM-FILE <filename>
  Specifies a file containing random data to be used as seed for the
  Pseudo Random Number Generator.  The contents of the file are
  overwritten with new random data on each use.
 
SET AUTHENTICATION { SSL, TLS } RSA-CERT-CHAIN-FILE <filename>
  Specifies a file containing a RSA certificate chain to be sent along with
  the RSA-CERT to the peer.  This file must only be specified if Kermit is
  being used as a server and the RSA certificate was signed by an
  intermediary certificate authority.
 
SET AUTHENTICATION { SSL, TLS } RSA-CERT-FILE <filename>
  Specifies a file containing a RSA certificate to be sent to the peer to 
  authenticate the host or end user.  The file may contain the matching RSA 
  private key instead of using the RSA-KEY-FILE command.
 
SET AUTHENTICATION { SSL, TLS } RSA-KEY-FILE <filename>
  Specifies a file containing the private RSA key that matches the RSA
  certificate specified with RSA-CERT-FILE.  This command is only necessary
  if the private key is not appended to the certificate in the file specified
  by RSA-CERT-FILE.  
 
  Note: When executing a script in the background or when it is
  running as an Internet Kermit Service Daemon, Kermit cannot support 
  encrypted private keys.  When attempting to load a private key that is
  encrypted, a prompt will be generated requesting the passphrase necessary
  to decrypt the keyfile.  To automate access to the private key you must
  decrypt the encrypted keyfile and create an unencrypted keyfile for use
  by Kermit.  This can be accomplished by using the following command and
  the passphrase:
 
  openssl rsa -in <encrypted-key-file> -out <unencrypted-key-file>
 
SET AUTHENTICATION { SSL, TLS } VERBOSE { ON, OFF }
  Specifies whether information about the authentication (ie, the
  certificate chain) should be displayed upon making a connection.
 
SET AUTHENTICATION { SSL, TLS } VERIFY { NO,PEER-CERT,FAIL-IF-NO-PEER-CERT }
  Specifies whether certificates should be requested from the peer verified;
  whether they should be verified when they are presented; and whether they
  should be required.  When set to NO (the default for IKSD), Kermit does
  not request that the peer send a certificate; if one is presented it is
  ignored.  When set to PEER-CERT (the default when not IKSD), Kermit
  requests a certificate be sent by the peer.  If presented, the certificate
  is verified.  Any errors during the verification process result in
  queries to the end user.  When set to FAIL-IF-NO-PEER-CERT, Kermit
  requests a certificate be sent by the peer.  If the certificate is not
  presented or fails to verify, the connection is terminated without
  querying the user.
 
  If an anonymous cipher (i.e., ADH) is desired, the NO setting must be
  used.  Otherwise, the receipt of the peer certificate request is
  interpreted as a protocol error and the negotiation fails.
 
  If you wish to allow the peer to authenticate using either an X509
  certificate to userid mapping function or via use of a ~/.tlslogin file
  you must use either PEER-CERT or FAIL-IF-NO-PEER-CERT.  Otherwise, any
  certificates that are presented is ignored.  In other words, use NO if you
  want to disable the ability to use certificates to authenticate a peer.
 
SET AUTHENTICATION { SSL, TLS } VERIFY-DIR <directory>
  Specifies a directory that contains root CA certificate files used to
  verify the certificate chains presented by the peer.  Each file is named
  by a hash of the certificate.
 
  OpenSSL expects the hash symlinks to be made like this:
 
    ln -s cert.pem `openssl x509 -hash -noout -in cert.pem`.0
 
  Since not all file systems have symlinks you can use the following command
  in Kermit to copy the cert.pem file to the hash file name.
 
    copy cert.pem {\fcommand(openssl.exe x509 -hash -noout -in cert.pem).0}
 
  This produces a hash based on the subject field in the cert such that the
  certificate may be quickly found.
 
SET AUTHENTICATION { SSL, TLS } VERIFY-FILE <file>
  Specifies a file that contains root CA certificates to be used for
  verifying certificate chains.
 
```

Compile-time default, from `SHOW AUTHENTICATION`:

```
 Authentication:      Kerberos 4 (not installed)
 Authentication:      Kerberos 5 (not installed)
 Authentication:      SSL/TLS (OpenSSL 3.5.6 7 Apr 2026)
 RSA Certs file: (none)
 RSA Certs Chain file: (none)
 RSA Key file: (none)
 DSA Certs file: (none)
 DSA Certs Chain file: (none)
 DH Key file: (none)
 DH Param file: (none)
 CRL file: (none)
 CRL dir: (none)
 Random file: (none)
 Verify file: (none)
 Verify dir: (none)
 Cipher list: HIGH:MEDIUM:LOW:+ADH:+EXP
    TLS_AES_256_GCM_SHA384
    TLS_CHACHA20_POLY1305_SHA256
    TLS_AES_128_GCM_SHA256
    ECDHE-ECDSA-AES256-GCM-SHA384
    ECDHE-RSA-AES256-GCM-SHA384
    DHE-RSA-AES256-GCM-SHA384
    ECDHE-ECDSA-CHACHA20-POLY1305
    ECDHE-RSA-CHACHA20-POLY1305
    DHE-RSA-CHACHA20-POLY1305
    ECDHE-ECDSA-AES128-GCM-SHA256
    ECDHE-RSA-AES128-GCM-SHA256
    DHE-RSA-AES128-GCM-SHA256
    ECDHE-ECDSA-AES256-SHA384
    ECDHE-RSA-AES256-SHA384
    DHE-RSA-AES256-SHA256
    ECDHE-ECDSA-AES128-SHA256
    ECDHE-RSA-AES128-SHA256
    DHE-RSA-AES128-SHA256
    ECDHE-ECDSA-AES256-SHA
    ECDHE-RSA-AES256-SHA
    DHE-RSA-AES256-SHA
    ECDHE-ECDSA-AES128-SHA
    ECDHE-RSA-AES128-SHA
    DHE-RSA-AES128-SHA
    RSA-PSK-AES256-GCM-SHA384
    DHE-PSK-AES256-GCM-SHA384
    RSA-PSK-CHACHA20-POLY1305
    DHE-PSK-CHACHA20-POLY1305
    ECDHE-PSK-CHACHA20-POLY1305
    AES256-GCM-SHA384
    PSK-AES256-GCM-SHA384
    PSK-CHACHA20-POLY1305
    RSA-PSK-AES128-GCM-SHA256
    DHE-PSK-AES128-GCM-SHA256
    AES128-GCM-SHA256
    PSK-AES128-GCM-SHA256
    AES256-SHA256
    AES128-SHA256
    ECDHE-PSK-AES256-CBC-SHA384
    ECDHE-PSK-AES256-CBC-SHA
    SRP-RSA-AES-256-CBC-SHA
    SRP-AES-256-CBC-SHA
    RSA-PSK-AES256-CBC-SHA384
    DHE-PSK-AES256-CBC-SHA384
    RSA-PSK-AES256-CBC-SHA
    DHE-PSK-AES256-CBC-SHA
    AES256-SHA
    PSK-AES256-CBC-SHA384
    PSK-AES256-CBC-SHA
    ECDHE-PSK-AES128-CBC-SHA256
    ECDHE-PSK-AES128-CBC-SHA
    SRP-RSA-AES-128-CBC-SHA
    SRP-AES-128-CBC-SHA
    RSA-PSK-AES128-CBC-SHA256
    DHE-PSK-AES128-CBC-SHA256
    RSA-PSK-AES128-CBC-SHA
    DHE-PSK-AES128-CBC-SHA
    AES128-SHA
    PSK-AES128-CBC-SHA256
    PSK-AES128-CBC-SHA
 Certs OK? no
 Debug mode: off
 Verbose mode: off
 Verify mode: peer-cert
 SSL only? no
 TLS only? no
 SSL raw? no
 TLS raw? no
 Authentication:      SRP (not installed)
 Authentication:      NTLM (not installed)
```

### SET BACKGROUND

Synonyms: B, BA, BATCH

```
Syntax: SET BACKGROUND { OFF, ON }
 
  SET BACKGROUND OFF forces prompts and messages to appear on your screen
  even though Kermit thinks it is running in the background.
```

### SET B

Synonym for [SET BACKGROUND](#set-background).

### SET BA

Synonym for [SET BACKGROUND](#set-background).

### SET BATCH

Synonym for [SET BACKGROUND](#set-background).

### SET SPEED

Synonym: BAUD

```
Syntax: SET SPEED number
  Speed for serial-port communication device specified in most recent
  SET LINE command, in bits per second.  Type SET SPEED ? for a list of
  possible speeds.  Some of the speeds shown might not be supported on the
  computer you are using.  Has no effect on job's controlling terminal.
```

### SET BAUD

Synonym for [SET SPEED](#set-speed).

### SET BELL

```
Syntax: SET BELL { OFF, ON }
  ON (the default) enables ringing of the terminal bell (beep) except where
  it is disabled in certain circumstances, e.g. by SET TRANSFER BELL.  OFF
  disables ringing of the bell in all circumstances, overriding any specific
  SET xxx BELL selections.
```

### SET BLOCK-CHECK

```
Syntax: SET BLOCK-CHECK number
 
Type of block check to be used for error detection on file-transfer
packets: 1, 2, 3, 4, or 5.  This command must be given to the file
sender prior to the transfer.
 
Type 1 is standard and supported by all Kermit protocol implementations,
  but it's only a 6-bit checksum, represented in a single printable ASCII
  character.  It's fine for reliable connections (error-correcting modems,
  TCP/IP, etc) but type 3 is recommended for connections where errors can
  occur.
 
Type 2 is a 12-bit checksum represented in two printable characters.
 
Type 3 is a 16-bit cyclic redundancy check, the strongest error
  detection method supported by Kermit protocol, represented in three
  printable characters.
 
Type 4 (alias "BLANK-FREE-2") is a 12-bit checksum guaranteed to
  contain no blanks in its representation; this is needed for connections
  where trailing blanks are stripped from incoming lines of text.
 
Type 5 (alias "FORCE-3") means to force a Type 3 block check on
  every packet, including the first packet, which normally has a type 1
  block check.  This is for use in critical applications on noisy
  connections.  As with types 2, 3, and 4, if the Kermit file
  transfer partner does not support this type, the transfer fails
  immediately at the beginning of the transfer.
```

### SET BROWSER

```
Syntax: SET BROWSER [ pathname [ options ] ]
  Specifies the name of your preferred browser plus any command-line
  options.  SHOW BROWSER displays it.
```

Compile-time default, from `SHOW BROWSER`:

```
 browser: (none)
```

### SET BUFFERS

```
Syntax: SET BUFFERS n1 [ n2 ]
 
  Changes the overall amount of memory allocated for SEND and RECEIVE packet
  buffers, respectively.  Bigger numbers let you have longer packets and
  more window slots.  If n2 is omitted, the same value as n1 is used.
 
  NOTE: This command is not needed in this version of Kermit, which is
  already configured for maximum-size packet buffers.
```

### SET CARRIER-WATCH

```
Syntax: SET CARRIER-WATCH { AUTO, OFF, ON }
 
  Attempts to control treatment of carrier (the Data Carrier Detect signal)
  on serial communication (SET LINE or SET PORT) devices.  ON means that
  carrier is required at all times.  OFF means carrier is never required.
  AUTO (the default) means carrier is required at all times except during
  the DIAL command.  Correct operation of carrier-watch depends on the
  capabilities of the underlying OS, drivers, devices, and cables.  If you
  need to CONNECT to a serial device that is not asserting carrier, and
  Kermit won't let you, use SET CARRIER-WATCH OFF.  Use SHOW COMMUNICATIONS
  to display the CARRIER-WATCH setting.
```

### SET CASE

```
Syntax: SET CASE { ON, OFF }
  Tells whether alphabetic case is significant in string comparisons
  done by INPUT, IF, and other commands.  This setting is local to the
  current macro or command file, and inherited by subordinates.
```

### SET CD

```
Syntax: SET CD { HOME <path>, PATH <path>, MESSAGE { ON, OFF, FILE <list> } }
 
SET CD HOME <path>
  Specified which directory to change to if CD or KCD is given without a
  pathname.  If this command is not given, your login or HOME directory is
  used.
 
SET CD PATH <path>
  Overrides normal CDPATH environment variable, which tells the CD command
  where to look for directories to CD to if you don't specify them fully.
  The format is:
 
    set cd path :directory:directory:...
 
  in other words, a list of directories separated by colons, with a colon
  at the beginning, e.g.:
 
    set cd path :/usr/olga:/usr/ivan/public:/tmp
 
SET CD MESSAGE { ON, OFF }
  Default is OFF.  When ON, this tells Kermit to look for a file with a
  certain name in any directory that you CD to, and if it finds one, to
  display it on your screen when you give the CD command.  The filename,
  or list of names, is given in the SET CD MESSAGE FILE command.
 
SET CD MESSAGE FILE name
  or:
SET CD MESSAGE FILE {{name1}{name2}...{name8}}
  Specify up to 8 filenames to look for when when CDing to a new directory
  and CD MESSAGE is ON.  The first one found, if any, in the new directory
  is displayed.  The default list is:
 
   {{./.readme}{README.TXT}{READ.ME}}
 
Synonym: SET SERVER CD-MESSAGE FILE.
 
Type SHOW CD to view current CD settings.  Also see HELP SET SERVER.
```

Compile-time default, from `SHOW CD`:

```
 current directory:  /home/jgoerzen/tree/ckermit
 previous directory: (none)
 cd home:            /home/jgoerzen/
 cd path:            (none)
 cd message:         off
 server cd-message:  off
 cd message file:    {{./.readme}{README.TXT}{READ.ME}}
```

### SET CLEAR-CHANNEL

Synonyms: CL, CLE, CLEA, CLEAR, CLEARCHANNEL

```
Syntax: SET CLEAR-CHANNEL { ON, OFF, AUTO }
  Tells Kermit whether its connection is transparent to all 8-bit bytes.
  Default is AUTO, meaning Kermit figures it out from the connection type.
  When both sender and receiver agree channel is clear, SET PREFIXING NONE
  is used automatically.
```

### SET CL

Synonym for [SET CLEAR-CHANNEL](#set-clear-channel).

### SET CLE

Synonym for [SET CLEAR-CHANNEL](#set-clear-channel).

### SET CLEA

Synonym for [SET CLEAR-CHANNEL](#set-clear-channel).

### SET CLEAR

Synonym for [SET CLEAR-CHANNEL](#set-clear-channel).

### SET CLEARCHANNEL

Synonym for [SET CLEAR-CHANNEL](#set-clear-channel).

### SET DISCONNECT

Synonym: CLOSE-ON-DISCONNECT

```
Syntax: SET DISCONNECT { ON, OFF }
  Whether to close and release a SET LINE device automatically upon
  disconnection; OFF = keep device open (default); ON = close and release.
```

### SET CLOSE-ON-DISCONNECT

Synonym for [SET DISCONNECT](#set-disconnect).

### SET COMMAND

Synonyms: CMD, CONSOLE

```
Syntax: SET COMMAND parameter value
 
SET COMMAND AUTODOWNLOAD { ON, OFF }
  Enables/Disables automatic recognition of Kermit packets while in
  command mode.  ON by default.
 
SET COMMAND BYTESIZE { 7, 8 }
  Informs Kermit of the bytesize of the communication path between itself
  and your keyboard and screen.  8 is assumed.  SET COMMAND BYTE 7 only if
  8-bit characters cannot pass.
 
SET COMMAND ERROR { 0,1,2,3 }
  Sets the verbosity level of command error messages; the higher the number,
  the more verbose the message.  The default is 1.  Higher values are
  useful only for debugging scripts.
 
SET COMMAND HEIGHT <number>
  Informs Kermit of the number of rows in your command screen for the
  purposes of More?-prompting.
 
SET COMMAND WIDTH <number>
  Informs Kermit of the number of characters across your screen for
  purposes of screen formatting.
 
SET COMMAND MORE-PROMPTING { ON, OFF }
  ON (the default) enables More?-prompting when Kermit needs to display
  text that does not fit vertically on your screen.  OFF allows the text to
  scroll by without intervention.  If your command window has scroll bars,
  you might prefer OFF.
 
SET COMMAND RECALL-BUFFER-SIZE number
  How big you want Kermit's command recall buffer to be.  By default, it
  holds 10 commands.  You can make it any size you like, subject to memory
  constraints of the computer.  A size of 0 disables command recall.
  Whenever you give this command, previous command history is lost.
 
SET COMMAND QUOTING { ON, OFF }
  Whether to treat backslash and question mark as special characters (ON),
  or as ordinary data characters (OFF) in commands.  ON by default.
 
SET COMMAND DOUBLEQUOTING { ON, OFF }
  Whether to allow doublequotes (") to be used to enclose fields,
  filenames, directory names, and macro arguments that might contain
  spaces.  ON by default; use OFF to force compatibility with older
  versions.
 
SET COMMAND RETRY { ON, OFF }
  Whether to reprompt you with the correct but incomplete portion of a
  syntactically incorrect command.  ON by default.
 
Use SHOW COMMAND to display these settings.
```

Compile-time default, from `SHOW COMMAND`:

```
 Command autodownload: on
 Command bytesize: 8 bits
 Command error-display: 1
 Command recall-buffer-size: 10
 Command retry: on
 Command interruption: on
 Command quoting: on
 Command doublequoting: on
 Command more-prompting: off
 Command height: 24
 Command width:  80
 Locus:          auto (local)
 Hints:          on
 Quiet:          off
 Maximum command length: 32763
 Maximum number of macros: 16384
 Macros defined: 11
 Maximum macro depth: 128
 Maximum TAKE depth: 54
 ON_UNKNOWN_COMMAND: (not defined)
 Suspend: on
 Access to external commands and programs allowed
```

### SET CMD

Synonym for [SET COMMAND](#set-command).

### SET CONSOLE

Synonym for [SET COMMAND](#set-command).

### SET CONTROL-CHARACTER

Synonym: CON

```
Syntax: SET CONTROL-CHARACTER { PREFIXED, UNPREFIXED } { <code>..., ALL }
 
  <code> is the numeric ASCII code for a control character 1-31,127-159,255.
  The word "ALL" means all characters in this range.
 
  PREFIXED <code> means the given control character must be converted to a
  printable character and prefixed, the default for all control characters.
 
  UNPREFIXED <code> means you think it is safe to send the given control
  character as-is, without a prefix.  USE THIS OPTION AT YOUR OWN RISK!
 
  SHOW CONTROL to see current settings.  SET CONTROL PREFIXED ALL is
  recommended for safety.  You can include multiple <code> values in one
  command, separated by spaces.
```

### SET CON

Synonym for [SET CONTROL-CHARACTER](#set-control-character).

### SET COUNT

```
Syntax:  SET COUNT number
 Example: SET COUNT 5
  Set up a loop counter, for use with IF COUNT.  Local to current macro
  or command file, inherited by subordinate macros and command files.
```

Compile-time default, from `SHOW COUNT`:

```
 0
```

### SET DELAY

Synonyms: D, DE

```
Syntax: SET DELAY number
  Number of seconds to wait before sending first packet after SEND command.
```

### SET D

Synonym for [SET DELAY](#set-delay).

### SET DE

Synonym for [SET DELAY](#set-delay).

### SET DEBUG

```
Syntax: SET DEBUG { SESSION, ON, OFF, TIMESTAMP, MESSAGES }
 
SET DEBUG ON
  Opens a debug log file named debug.log in the current directory.
  Use LOG DEBUG if you want specify a different log file name or path.
 
SET DEBUG OFF
  Stops debug logging and session debugging.
 
SET DEBUG SESSION
  Displays control and 8-bit characters symbolically during CONNECT mode.
  Equivalent to SET TERMINAL DEBUG ON.
 
SET DEBUG TIMESTAMP { ON, OFF }
  Enables/Disables timestamps on debug log entries.
 
SET DEBUG MESSAGES { ON, OFF, STDERR } [C-Kermit 9.0]
  Enables/Disables messages printed by the DEBUG command.
  SET DEBUG OFF causes DEBUG messages not to be printed.
  SET DEBUG ON sends DEBUG messages to standard output (stdout);
  SET DEBUG STDERR sends DEBUG messages to standard error (stderr);
```

### SET DEFAULT

```
Syntax: SET DEFAULT directory
  Change directory.  Equivalent to CD command.
```

Compile-time default, from `SHOW DEFAULT`:

```
/home/jgoerzen/tree/ckermit
```

### SET DESTINATION

```
Not available - "help set destination"
```

### SET DIAL

Synonyms: DI, DIA

```
The SET DIAL command establishes or changes all parameters related to
dialing the telephone.  Also see HELP DIAL and HELP SET MODEM.  Use SHOW
DIAL to display all of the SET DIAL values.
 
SET DIAL COUNTRY-CODE <number>
  Tells Kermit the telephonic country-code of the country you are dialing
  from, so it can tell whether a portable-format phone number from your
  dialing directory will result in a national or an international call.
  Examples: 1 for USA, Canada, Puerto Rico, etc; 7 for Russia, 39 for Italy,
  351 for Portugal, 47 for Norway, 44 for the UK, 972 for Israel, 81 for
  Japan, ...
 
  If you have not already set your DIAL INTL-PREFIX and LD-PREFIX, then this
  command sets default values for them: 011 and 1, respectively, for country
  code 1; 00 and 0, respectively, for all other country codes.  If these are
  not your true international and long-distance dialing prefixes, then you
  should follow this command by DIAL INTL-PREFIX and LD-PREFIX to let Kermit
  know what they really are.
 
SET DIAL AREA-CODE [ <number> ]
  Tells Kermit the area or city code that you are dialing from, so it can
  tell whether a portable-format phone number from the dialing directory is
  local or long distance.  Be careful not to include your long-distance
  dialing prefix as part of your area code; for example, the area code for
  central London is 171, not 0171.
 
SET DIAL CONFIRMATION {ON, OFF}
  Kermit does various transformations on a telephone number retrieved from
  the dialing directory prior to dialing (use LOOKUP <name> to see them).
  In case the result might be wrong, you can use SET DIAL CONFIRM ON to have
  Kermit ask you if it is OK to dial the number, and if not, to let you type
  in a replacement.
 
SET DIAL CONNECT { AUTO, ON, OFF }
  Whether to CONNECT (enter terminal mode) automatically after successfully
  dialing.  ON means to do this; OFF means not to.  AUTO (the default) means
  do it if the DIAL command was given interactively, but don't do it if the
  DIAL command was issued from a macro or command file.  If you specify ON
  or AUTO, you may follow this by one of the keywords VERBOSE or QUIET, to
  indicate whether the verbose 4-line 'Connecting...' message is to be
  displayed if DIAL succeeds and Kermit goes into CONNECT mode.
 
SET DIAL CONVERT-DIRECTORY {ASK, ON, OFF}
  The format of Kermit's dialing directory changed in version 5A(192).  This
  command tells Kermit what to do when it encounters an old-style directory:
  ASK you whether to convert it, or convert it automatically (ON), or leave
  it alone (OFF).  Old-style directories can still be used without
  conversion, but the parity and speed fields are ignored.
 
SET DIAL DIRECTORY [ filename [ filename [ filename [ ... ] ] ] ]
  The name(s) of your dialing directory file(s).  If you do not supply any
  filenames, the  dialing directory feature is disabled and all numbers are
  dialed literally as given in the DIAL command.  If you supply more than
  one directory, all of them are searched.
 
SET DIAL SORT {ON, OFF}
  When multiple entries are obtained from your dialing directory, they are
  sorted in "cheapest-first" order.  If this does not produce the desired
  effect, SET DIAL SORT OFF to disable sorting, and the numbers will be
  dialed in the order in which they were found.
 
SET DIAL DISPLAY {ON, OFF}
  Whether to display dialing progress on the screen; default is OFF.
 
SET DIAL HANGUP {ON, OFF}
  Whether to hang up the phone prior to dialing; default is ON.
 
SET DIAL IGNORE-DIALTONE {ON, OFF}
  Whether to ignore dialtone when dialing; default is OFF.
 
SET DIAL MACRO [ name ]
  Specify the name of a macro to execute on every phone number dialed, just
  prior to dialing it, in order to perform any last-minute alterations.
 
SET DIAL METHOD {AUTO, DEFAULT, TONE, PULSE}
  Whether to use the modem's DEFAULT dialing method, or to force TONE or
  PULSE dialing.  AUTO (the default) means to choose tone or pulse dialing
  based on the country code.  (Also see SET DIAL TONE-COUNTRIES and SET DIAL
  PULSE-COUNTRIES.)
 
SET DIAL PACING number
  How many milliseconds to pause between sending each character to the modem
  dialer.  The default is -1, meaning to use the number from the built-in
 modem database.
  
SET DIAL PULSE-COUNTRIES [ cc [ cc [ ... ] ] ]
  Sets the list of countries in which pulse dialing is required.  Each cc
  is a country code.
 
SET DIAL TEST { ON, OFF }
  OFF for normal dialing.  Set to ON to test dialing procedures without
  actually dialing.
 
SET DIAL TONE-COUNTRIES [ cc [ cc [ ... ] ] ]
  Sets the list of countries in which tone dialing is available.  Each cc
  is a country code.
 
SET DIAL TIMEOUT number
  How many seconds to wait for a dialed call to complete.  Use this command
  to override the DIAL command's automatic timeout calculation.  A value
  of 0 turns off this feature and returns to Kermit's automatic dial
  timeout calculation.
 
SET DIAL RESTRICT { INTERNATIONAL, LOCAL, LONG-DISTANCE, NONE }
  Prevents placing calls of the type indicated, or greater.  For example
  SET DIAL RESTRICT LONG prevents placing of long-distance and international
  calls.  If this command is not given, there are no restrictions.  Useful
  when dialing a list of numbers fetched from a dialing directory.
 
SET DIAL RETRIES <number>
  How many times to redial each number if the dialing result is busy or no
  no answer, until the call is successfully answered.  The default is 0
  because automatic redialing is illegal in some countries.
 
SET DIAL INTERVAL <number>
  How many seconds to pause between automatic redial attempts; default 10.
 
The following commands apply to all phone numbers, whether given literally
or found in the dialing directory:
 
SET DIAL PREFIX [ text ]
  Establish a prefix to be applied to all phone numbers that are dialed,
  for example to disable call waiting.
 
SET DIAL SUFFIX [ text ]
  Establish a suffix to be added after all phone numbers that are dialed.
 
The following commands apply only to portable-format numbers obtained from
the dialing directory; i.e. numbers that start with a "+" sign and
country code, followed by area code in parentheses, followed by the phone
number.
 
SET DIAL LC-AREA-CODES [ <list> ]
  Species a list of area codes to which dialing is local, i.e. does not
  require the LD-PREFIX.  Up to 32 area codes may be listed, separated by
  spaces.  Any area codes in this list will be included in the final dial
  string so do not include your own area code if it should not be dialed.
 
SET DIAL LC-PREFIX [ <text> ]
  Specifies a prefix to be applied to local calls made from portable dialing
  directory entries.  Normally no prefix is used for local calls.
 
SET DIAL LC-SUFFIX [ <text> ]
  Specifies a suffix to be applied to local calls made from portable dialing
  directory entries.  Normally no suffix is used for local calls.
 
SET DIAL LD-PREFIX [ <text> ]
  Your long-distance dialing prefix, to be used with portable dialing
  directory entries that result in long-distance calls.
 
SET DIAL LD-SUFFIX [ <text> ]
  Long-distance dialing suffix, if any, to be used with portable dialing
  directory entries that result in long-distance calls.  This would normally
  be used for appending a calling-card number to the phone number.
 
SET DIAL FORCE-LONG-DISTANCE { ON, OFF }
  Whether to force long-distance dialing for calls that normally would be
  local.  For use (e.g.) in France.
 
SET DIAL TOLL-FREE-AREA-CODE [ <number> [ <number> [ ... ] ] ]
  Tells Kermit the toll-free area code(s) in your country.
 
SET DIAL TOLL-FREE-PREFIX [ <text> ]
  You toll-free dialing prefix, in case it is different from your long-
  distance dialing prefix.
 
SET DIAL INTL-PREFIX <text>
  Your international dialing prefix, to be used with portable dialing
  directory entries that result in international calls.
 
SET DIAL INTL-SUFFIX <text>
  International dialing suffix, if any, to be used with portable dialing
  directory entries that result in international calls.
 
SET DIAL PBX-OUTSIDE-PREFIX <text>
  Use this to tell Kermit how to get an outside line when dialing from a
  Private Branch Exchange (PBX).
 
SET DIAL PBX-EXCHANGE <text> [ <text> [ ... ] ]
  If PBX-OUTSIDE-PREFIX is set, then you can use this command to tell Kermit
  the leading digits of one or more local phone numbers that identify it as
  being on your PBX, so it can make an internal call by deleting those digits
  from the phone number.
 
SET DIAL PBX-INTERNAL-PREFIX <text>
  If PBX-EXCHANGE is set, and Kermit determines from it that a call is
  internal, then this prefix, if any, is added to the number prior to
  dialing.  Use this if internal calls from your PBX require a special prefix.
```

Compile-time default, from `SHOW DIAL`:

```
 Communication device not yet selected with SET LINE
 Modem type: generic, speed: 0, carrier: auto
 Dial status:  -1 = (none)
 Dial directory: (none)
 Dial method:  auto            Dial sort: on
 Dial hangup:  on              Dial display: off
 Dial retries: (auto)          Dial interval: 10
 Dial timeout: 0 (auto)        Redial number: (none)
 Dial confirmation: off        Dial convert-directory: ask
 Dial ignore-dialtone: off     Dial pacing: -1
 Dial prefix:                  (none)
 Dial suffix:                  (none)
 Dial country-code:            (none)      Dial connect:  auto verbose
 Dial area-code:               (none)      Dial restrict: none
 Dial lc-area-codes:           (none)
 Dial lc-prefix:               (none)
 Dial lc-suffix:               (none)
 Dial ld-prefix:               (none)
 Dial ld-suffix:               (none)
 Dial force-long-distance      off
 Dial intl-prefix:             (none)
 Dial intl-suffix:             (none)
 Dial toll-free-area-code:     (none)
 Dial pulse-countries:         (none)
 Dial tone-countries:          1 31 32 33 352 353 354 358 39 44 45 46 47 49 
 Dial toll-free-prefix:        (none)
 Dial pbx-exchange:            (none)
 Dial pbx-inside-prefix:       (none)
 Dial pbx-outside-prefix:      (none)
 Dial macro:                   (none)
```

### SET DI

Synonym for [SET DIAL](#set-dial).

### SET DIA

Synonym for [SET DIAL](#set-dial).

### SET DUPLEX

```
Syntax: SET DUPLEX { FULL, HALF }
  During CONNECT: FULL means remote host echoes, HALF means Kermit
  does its own echoing.
```

### SET EDITOR

```
Syntax: SET EDITOR pathname [ options ]
  Specifies the name of your preferred editor, plus any command-line
  options.  SHOW EDITOR displays it.
```

Compile-time default, from `SHOW EDITOR`:

```
 editor:  (none)
```

### SET EOF

```
Not available - "help set eof"
```

### SET ESCAPE-CHARACTER

```
Syntax: SET ESCAPE number
  Decimal ASCII value for escape character during CONNECT, normally 28
  (Control-\).  Type the escape character followed by C to get back to the
  C-Kermit prompt or followed by ? to see other options.
 
You may also enter the escape character as ^X (circumflex followed by a
letter or one of: @, ^, _, [, \, or ], to indicate a control character;
for example, SET ESC ^_ sets your escape character to Ctrl-Underscore.
 
You can also specify an 8-bit character (128-255) as your escape character,
either by typing it literally or by entering its numeric code.
```

### SET EVALUATE

```
Not available - "help set evaluate"
```

### SET EXIT

```
Syntax: SET EXIT HANGUP { ON, OFF }
  When ON (which is the default), C-Kermit executes an implicit HANGUP and
  CLOSE command on the communications device or connection when it exits.
  When OFF, Kermit skips this sequence.
 
Syntax: SET EXIT MESSAGE { ON, OFF, STDERR }
  Allows the text (if any) from an EXIT command (see HELP EXIT) to be
  supressed (OFF), printed normally (ON, the default), or sent to STDERR.
 
Syntax: SET EXIT ON-DISCONNECT { ON, OFF }
  When ON, C-Kermit EXITs automatically when a network connection
  is terminated either by the host or by issuing a HANGUP command.
 
Syntax: SET EXIT STATUS number
  Set C-Kermit's program return code to the given number, which can be a
  constant, variable, function result, or arithmetic expression.
 
Syntax: SET EXIT WARNING { ON, OFF, ALWAYS }
  When EXIT WARNING is ON, issue a warning message and ask for confirmation
  before EXITing if a connection to another computer might still be open.
  When EXIT WARNING is ALWAYS, confirmation is always requested.  When OFF
  it is never requested.  The default is ON.
```

Compile-time default, from `SHOW EXIT`:

```
 Exit warning on
 Exit message: on
 Exit on-disconnect: off
 Exit hangup: on
 Current exit status: 0
```

### SET EXTERNAL-PROTOCOL

```
Not available - "help set external-protocol"
```

### SET F-ACK-BUG

```
Not available - "help set f-ack-bug"
```

### SET F-ACK-PATH

```
Not available - "help set f-ack-path"
```

### SET FILE

```
Syntax: SET FILE parameter value
 
Sets file-related parameters.  Use SHOW FILE to view them.  Also see SET
(and SHOW) TRANSFER and PROTOCOL.
 
SET FILE TYPE { TEXT, BINARY }
  How file contents are to be treated during file transfer in the absence
  of any other indication.  TYPE can be TEXT for conversion of record format
  and character set, which is usually needed when transferring text files
  between unlike platforms (such as UNIX and Windows), or BINARY for no
  conversion if TRANSFER MODE is MANUAL, which is not the default.  Use
  BINARY with TRANSFER MODE MANUAL for executable programs or binary data or
  whenever you wish to duplicate the original contents of the file, byte for
  byte.  In most modern Kermit programs, the file sender informs the receiver
  of the file type automatically.  However, when sending files from C-Kermit
  to an ancient or non-Columbia Kermit implementation, you might need to set
  the corresponding file type at the receiver as well.
 
  When TRANSFER MODE is AUTOMATIC (as it is by default), various automatic
  methods (depending on the platform) are used to determine whether a file
  is transferred in text or binary mode; these methods (which might include
  content scan (see SET FILE SCAN below), filename pattern matching (SET FILE
  PATTERNS), client/server "kindred-spirit" recognition, or source file
  record format) supersede the FILE TYPE setting but can, themselves, be
  superseded by including a /BINARY or /TEXT switch in the SEND, GET, or
  RECEIVE command.
 
  When TRANSFER MODE is MANUAL, the automatic methods are skipped for sending
  files; the FILE TYPE setting is used instead, which can be superseded on
  a per-command basis with a /TEXT or /BINARY switch.
 
SET FILE BYTESIZE { 7, 8 }
  Normally 8.  If 7, Kermit truncates the 8th bit of all file bytes.
 
SET FILE CHARACTER-SET name
  Tells the encoding of the local file, ASCII by default.
  The names ITALIAN, PORTUGUESE, NORWEGIAN, etc, refer to 7-bit ISO-646
  national character sets.  LATIN1 is the 8-bit ISO 8859-1 Latin Alphabet 1
  for Western European languages.
  NEXT is the 8-bit character set of the NeXT workstation.
  The CPnnn sets are for PCs.  MACINTOSH-LATIN is for the Macintosh.
  LATIN2 is ISO 8859-2 for Eastern European languages that are written with
  Roman letters.  Mazovia is a PC code page used in Poland.
  KOI-CYRILLIC, CYRILLIC-ISO, and CP866 are 8-bit Cyrillic character sets.
  SHORT-KOI is a 7-bit ASCII coding for Cyrillic.  BULGARIA-PC is a PC code
  page used in Bulgaria
  HEBREW-ISO is ISO 8859-8 Latin/Hebrew.  CP862 is the Hebrew PC code page.
  HEBREW-7 is like ASCII with the lowercase letters replaced by Hebrew.
  GREEK-ISO is ISO 8859-7 Latin/Greek.  CP869 is the Greek PC code page.
  ELOT-927 is like ASCII with the lowercase letters replaced by Greek.
  JAPANESE-EUC, JIS7-KANJI, DEC-KANJI, and SHIFT-JIS-KANJI are Japanese
  Kanji character sets.
  UCS-2 is the 2-byte form of the Universal Character Set.
  UTF-8 is the serialized form of the Universal Character Set.
  Type SET FILE CHAR ? for a complete list of file character sets.
 
SET FILE DEFAULT 7BIT-CHARACTER-SET
  When automatically switching among different kinds of files while sending
  this tells the character set to be used for 7-bit text files.
 
SET FILE DEFAULT 8BIT-CHARACTER-SET
  This tells the character set to be used for 8-bit text files when
  switching automatically among different kinds of files.
 
SET FILE COLLISION option
  Tells what to do when a file arrives that has the same name as
  an existing file.  The options are:
   BACKUP - Rename the old file to a new, unique name and store
     the incoming file under the name it was sent with.
   OVERWRITE - Overwrite (replace) the existing file; doesn't work for
     a Kermit server unless you also tell it to ENABLE DELETE.
   APPEND - Append the incoming file to the end of the existing file.
   REJECT (default) - Refuse and/or discard the incoming file (= DISCARD).
   RENAME - Give the incoming file a unique name.
   UPDATE - Accept the incoming file only if newer than the existing file.
 
SET FILE DESTINATION { DISK, PRINTER, SCREEN, NOWHERE }
  DISK (default): Store incoming files on disk.
  PRINTER:        Send incoming files to SET PRINTER device.
  SCREEN:         Display incoming files on screen (local mode only).
  NOWHERE:        Do not put incoming files anywhere (use for calibration).
 
SET FILE DISPLAY option
  Selects the format of the file transfer display for local-mode file
  transfer.  The choices are:
 
  BRIEF      A line per file, showing size, mode, status, and throughput.
  SERIAL     One dot is printed for every K bytes transferred.
  CRT        Numbers are continuously updated on a single screen line.
             This format can be used on any video display terminal.
  FULLSCREEN A fully formatted 24x80 screen showing lots of information.
             This requires a terminal or terminal emulator.
  NONE       No file transfer display at all.
 
SET FILE DOWNLOAD-DIRECTORY [ <directory-name> ]
  The directory into which all received files should be placed.  By default,
  received files go into your current directory.
 
SET FILE EOF { CTRL-Z, LENGTH }
  End-Of-File detection method, normally LENGTH.  Applies only to text-mode
  transfers.  When set to CTRL-Z, this makes the file sender treat the first
  Ctrl-Z in the input file as the end of file (EOF), and it makes the file
  receiver tack a Ctrl-Z onto the end of the output file if it does not
  already end with Ctrl-Z.
 
SET FILE END-OF-LINE { CR, CRLF, LF }
  Use this command to specify nonstandard line terminators for text files.
 
SET FILE INCOMPLETE { AUTO, KEEP, DISCARD }
  What to do with an incompletely received file: KEEP, DISCARD, or AUTO.
  AUTO (the default) means DISCARD if transfer is in text mode, KEEP if it
  is in binary mode.
 
SET FILE LISTSIZE number
  Changes the size of the internal wildcard expansion list.  Use SHOW FILE
  to see the current size.  Use this command to increase the size if you get
  a "?Too many files" error.  Also see SET FILE STRINGSPACE.
 
SET FILE NAMES { CONVERTED, LITERAL }
  File names are normally CONVERTED to "common form" during transmission
  (e.g. lowercase to uppercase, extra periods changed to underscore, etc).
  LITERAL means use filenames literally (useful between like systems).  Also
  see SET SEND PATHNAMES and SET RECEIVE PATHNAMES.
 
SET FILE OUTPUT { { BUFFERED, UNBUFFERED } [ size ], BLOCKING, NONBLOCKING }
  Lets you control the disk output buffer for incoming files.  Buffered
  blocking writes are normal.  Nonblocking writes might be faster on some
  systems but might also be risky, depending on the underlying file service.
  Unbuffered writes might be useful in critical applications to ensure that
  cached disk writes are not lost in a crash, but will probably also be
  slower.  The optional size parameter after BUFFERED or UNBUFFERED lets you
  change the disk output buffer size; this might make a difference in
  performance.
 
SET FILE PATTERNS { ON, OFF, AUTO }
  ON means to use filename pattern lists to determine whether to send a file
  in text or binary mode.  OFF means to send all files in the prevailing
  mode.  AUTO (the default) is like ON if the other Kermit accepts Attribute
  packets and like OFF otherwise.  FILE PATTERNS are used only if FILE SCAN
  is OFF (see SET FILE SCAN).
 
SET FILE BINARY-PATTERNS [ <pattern> [ <pattern> ... ] ]
  Zero or more filename patterns which, if matched, cause a file to be sent
  in binary mode when FILE PATTERNS are ON.  HELP WILDCARDS for a description
  of pattern syntax.  SHOW PATTERNS to see the current file pattern lists.
 
SET FILE TEXT-PATTERNS [ <pattern> [ <pattern> ... ] ]
  Zero or more filename patterns which, if matched, cause a file to be sent
  in text mode when FILE PATTERNS is ON; if a file does not match a text or
  binary pattern, the prevailing SET FILE TYPE is used.
 
SET FILE SCAN { ON [ size ], OFF }
  If TRANSFER MODE is AUTOMATIC and FILE SCAN is ON (as it is by default)
  Kermit peeks at the file's contents to see if it's text or binary.  Use
  SET FILE SCAN OFF to disable file peeking, while still keeping TRANSFER
  MODE automatic to allow name patterns and other methods.  The optional
  size is the number of file bytes to scan, 49152 by default.  -1 means to
  scan the whole file.  Also see SET FILE PATTERNS.
 
SET FILE STRINGSPACE number
  Changes the size (in bytes) of the internal buffer that holds lists of
  filenames such as wildcard expansion lists.  Use SHOW FILE to see the
  current size.  Use this command to increase the size if you get a
  "?String space exhausted" error.  Also see SET FILE LISTSIZE.
 
SET FILE UCS BOM { ON, OFF }
  Whether to write a Byte Order Mark when creating a UCS-2 file.
 
SET FILE UCS BYTE-ORDER { BIG-ENDIAN, LITTLE-ENDIAN }
  Byte order to use when creating UCS-2 files, and to use when reading UCS-2
  files that do not start with a Byte Order Mark.
 
SET FILE SYSTEM-ID code
  Kermit system ID code to pretend to be. Valid options are:
    0:  anonymous       A1: Apple II      A3: Macintosh
    D7: VMS             DA: RSTS/E        DB: RT11
    F3: AOS/VS          I1: VM/CMS        I2: TSO
    I4: MUSIC           I7: CICS          I9: ROSCOE
    K2: Atari ST        L3: Amiga         MV: Stratus VOS
    N3: Aegis           U1: UNIX          U8: MS-DOS
    UD: OS-9            UN: MS-Windows    UO: OS/2
 
SET FILE WARNING { ON, OFF }
  SET FILE WARNING is superseded by the newer command, SET FILE
  COLLISION.  SET FILE WARNING ON is equivalent to SET FILE COLLISION RENAME
  and SET FILE WARNING OFF is equivalent to SET FILE COLLISION OVERWRITE.
```

Compile-time default, from `SHOW FILE`:

```
 Transfer mode:           manual
 File patterns:           automatic (but disabled by TRANSFER-MODE MANUAL)
 File scan:               on 49152
 File type:               binary
 File names:              converted
 Send pathnames:          off
 Receive pathnames:       auto
 Match dot files:         no
 Wildcard-expansion:      on (kermit)
 File collision:          discard
 File destination:        disk
 File incomplete:         auto
 File bytesize:           8
 File character-set:      ascii
 File default 7-bit:      ascii
 File default 8-bit:      latin1-iso
 File UCS bom:            on
 File UCS byte-order:     little-endian
 Computer byteorder:      little-endian
 File end-of-line:        lf
 File eof:                length
 File download-directory: (your current directory)
 Send move-to:            (none)
 Send rename-to:          (none)
 Receive move-to:         (none)
 Receive rename-to:       (none)
 Initialization file:     (none)
 Root set:                (none)
 Disk output buffer:      32768 (writes are buffered, blocking)
 Stringspace:             2000000000
 Listsize:                102400
 Longest filename:        4096
 Longest pathname:        4096
 Last file sent:          (none)
 Last file received:      (none)

 Also see:
 SHOW PROTOCOL, SHOW XFER, SHOW PATTERNS, SHOW STREAMING, SHOW CHARACTER-SETS
```

### SET FLOW-CONTROL

Synonym: FL

```
Syntax: SET FLOW [ switch ] value
 
  Selects the type of flow control to use during file transfer, terminal
  connection, and script execution.
 
  Switches let you associate a particular kind of flow control with each
  kind of connection: /REMOTE, /MODEM, /DIRECT-SERIAL, /TCPIP, etc; type
  "set flow ?" for a list of available switches.  Then whenever you make
  a connection, the associated flow-control is chosen automatically.
  The flow-control values are NONE, KEEP, XON/XOFF, and possibly RTS/CTS
  and some others; again, type "set flow ?" for a list.  KEEP tells Kermit
  not to try to change the current flow-control method for the connection.
 
  If you omit the switch and simply supply a value, this value becomes the
  current flow control type, overriding any default value that might have
  been chosen in your most recent SET LINE, SET PORT, or SET HOST, or other
  connection-establishment command.
 
  Type SHOW FLOW-CONTROL to see the current defaults for each connection type
  as well as the current connection type and flow-control setting.  SHOW
  COMMUNICATIONS also shows the current flow-control setting.
```

Compile-time default, from `SHOW FLOW-CONTROL`:

```
Connection type:        remote
Current flow-control:   none
Switches automatically: yes

Defaults by connection type:
  remote        : none
  direct-serial : none
  modem         : rts/cts
  tcp/ip        : none
  ssh           : none
  pipe          : none
```

### SET FL

Synonym for [SET FLOW-CONTROL](#set-flow-control).

### SET FLAG

```
Not available - "help set flag"
```

### SET FTP

Synonym: FT

```
Syntax: SET FTP parameter value
  Type "help set ftp ?" for a list of parameters.
  Type "help set ftp xxx" for information about setting
  parameter xxx.  Type "show ftp" for current values.
```

Compile-time default, from `SHOW FTP`:

```
FTP connection:                 (none)
Not logged in

SET FTP values:

 ftp anonymous-password:        (default)
 ftp auto-login:                on
 ftp auto-authentication:       on
 ftp timeout:                   0
 ftp type:                      text
 ftp get-filetype-switching:    on
 ftp dates:                     on
 ftp error-action:              proceed
 ftp filenames:                 auto
 ftp debug                      off
 ftp passive-mode:              on
 ftp permissions:               off
 ftp verbose-mode:              off
 ftp send-port-commands:        on
 ftp unique-server-names:       off
 ftp collision:                 discard
 ftp server-time-offset:        (none)
 ftp character-set-translation: off
 ftp server-character-set:      utf8
 file character-set:            ascii
 ftp display:                   fullscreen
 enabled:                       AUTH FEAT MDTM MLST SIZE
 get-put-remote:                auto

Available security methods:    

 ftp authtype:                  (none)
 ftp auto-encryption:           on
 ftp credential-forwarding:     off
 ftp command-protection-level:  clear
 ftp data-protection-level:     clear
 ftp secure proxy:              (not set)
```

### SET FT

Synonym for [SET FTP](#set-ftp).

### SET FTP-CLIENT

```
Syntax: SET FTP [ pathname [ options ] ]
  Specifies the name of your ftp client, plus any command-line options.
  SHOW FTP displays it.
```

### SET FUNCTION

```
SET FUNCTION DIAGNOSTICS { ON, OFF }
  Whether to issue diagnostic messages for illegal function calls and
  references to nonexistent built-in variables.  ON by default.
 
SET FUNCTION ERROR { ON, OFF }
  Whether an illegal function call or reference to a nonexistent built-in
  variable should cause a command to fail.  OFF by default.
```

### SET GET-PUT-REMOTE

```
Syntax: SET GET-PUT-REMOTE { AUTO, FTP, KERMIT}
  Tells Kermit whether GET, PUT, and REMOTE commands should be directed
  at a Kermit server or an FTP server.  The default is AUTO, meaning that
  if you have only one active connection, the appropriate action is taken
  when you give a GET, PUT, or REMOTE command.  SET GET-PUT-REMOTE FTP forces
  Kermit to treat GET, PUT, and REMOTE as FTP client commands; setting this
  to KERMIT forces these commands to be treated as Kermit client commands.
  NOTE: PUT includes SEND, MPUT, MSEND, and all other similar commands.
  Also see HELP REMOTE, HELP SET LOCUS, HELP FTP.
```

### SET HANDSHAKE

```
Syntax: SET HANDSHAKE { NONE, XON, LF, BELL, ESC, CODE number }
  Character to use for half duplex line turnaround handshake during file
  transfer.  C-Kermit waits for this character from the other computer
  before sending its next packet.  Default is NONE; you can give one of the
  other names like BELL or ESC, or use SET HANDSHAKE CODE to specify the
  numeric code value of the handshake character.  Type SET HANDSH ? for a
  complete list of possibilities.
```

### SET HINTS

```
Not available - "help set hints"
```

### SET HOST

```
SET HOST [ switches ] hostname-or-address [ service ] [ protocol-switch ]
  Establishes a connection to the specified network host on the currently
  selected network type.  For TCP/IP connections, the default service is
  TELNET; specify a different TCP port number or service name to choose a
  different service.
 
  A hostname or address containing colons of its own (an IPv6 address
  literal, such as ::1) must be enclosed in square brackets to attach a
  port, e.g. [::1]:23, or given bare in brackets with no port, e.g. [::1],
  since otherwise Kermit cannot tell which colon separates the port.
 
  Which IP address family actually gets used for a hostname that has
  both IPv4 and IPv6 addresses is controlled by SET TCP ADDRESS-FAMILY. For
  SET HOST * (listen for an incoming connection), the same setting
  controls which family (or families) are listened on.
 
  The first set of switches can be:
 
 /NETWORK-TYPE:name
   Makes the connection on the given type of network.  Equivalent to SET
   NETWORK TYPE name prior to SET HOST, except that the selected network
   type is used only for this connection.  Type "set host /net:?" to see
   a list.  /NETWORK-TYPE:COMMAND means to make the connection through the
   given system command, such as "rlogin" or "cu".
 
 /CONNECT
   Enter CONNECT (terminal) mode automatically if the connection is successful.
 
 /SERVER
   Enter server mode automatically if the connection is successful.
 
 /USERID:[<name>]
   This switch is equivalent to SET LOGIN USERID <name> or SET TELNET
   ENVIRONMENT USER <name>.  If a string is given, it sent to host during
   Telnet negotiations; if this switch is given but the string is omitted,
   no user ID is sent to the host.  If this switch is not given, your
   current USERID value, \v(userid), is sent.  When a userid is sent to the
   host it is a request to login as the specified user.
 
 /PASSWORD:[<string>]
   This switch is equivalent to SET LOGIN PASSWORD.  If a string is given,
   it is treated as the password to be used (if required) by any Telnet
   Authentication protocol (Kerberos Ticket retrieval, Secure Remote
   Password, or X.509 certificate private key decryption.)  If no password
   switch is specified a prompt is issued to request the password if one
   is required for the negotiated authentication method.
 
The protocol-switches can be:
 
 /NO-TELNET-INIT
   Do not send initial Telnet negotiations even if this is a Telnet port.
 
 /RAW-SOCKET
   This is a connection to a raw TCP socket.
 
 /RLOGIN
   Use Rlogin protocol even if this is not an Rlogin port.
 
 /TELNET
   Send initial Telnet negotiations even if this is not a Telnet port.
 
 /SSL
   Perform SSL negotiations.
 
 /SSL-TELNET
   Perform SSL negotiations and if successful start Telnet negotiations.
 
 /TLS
   Perform TLS negotiations.
 
 /TLS-TELNET
   Perform TLS negotiations and if successful start Telnet negotiations.
 
Examples:
  SET HOST kermit.columbia.edu
  SET HOST /CONNECT kermit.columbia.edu
  SET HOST * 1649
  SET HOST /SERVER * 1649
  SET HOST 128.59.39.2
  SET HOST madlab.sprl.umich.edu 3000
  SET HOST xyzcorp.com 2000 /RAW-SOCKET
  SET HOST /CONNECT /COMMAND rlogin xyzcorp.com
 
The TELNET command is equivalent to SET NETWORK TYPE TCP/IP,
SET HOST name [ port ] /TELNET, IF SUCCESS CONNECT
 
The SSH command is equivalent to SET HOST /PTY /CONNECT ssh -e none hostname
 
Also see SET NETWORK, SSH, TELNET, SET TELNET.
```

### SET INPUT

Synonyms: I, IN

```
Syntax: SET INPUT parameter value
 
SET INPUT AUTODOWNLOAD { ON, OFF }
  Controls whether autodownloads are allowed during INPUT command execution.
 
SET INPUT BUFFER-LENGTH number-of-bytes
  Removes the old INPUT buffer and creates a new one with the given length.
 
SET INPUT CANCELLATION { ON, OFF }
  Whether an INPUT in progress can be can interrupted from the keyboard.
 
SET INPUT CASE { IGNORE, OBSERVE }
  Tells whether alphabetic case is to be significant in string comparisons.
  This setting is local to the current macro or command file, and is
  inherited by subordinate macros and take files.
 
SET INPUT ECHO { ON, OFF }
  Tells whether to display arriving characters read by INPUT on the screen.
 
SET INPUT SCALE-FACTOR <number>
  A number to multiply all INPUT timeouts by, which may include a fractional
  part, e.g. 2.5.  All INPUT commands that specify a timeout in seconds
  (as opposed to a specific time of day) have their time limit adjusted
  automatically by this factor, which is also available in the built-in
  read-only variable \v(inscale).  The default value is 1.0.
 
SET INPUT SILENCE <number>
  The maximum number to seconds of silence (no input at all) before the
  INPUT command times out, 0 for no maximum.
 
SET INPUT TIMEOUT-ACTION { PROCEED, QUIT }
  Tells whether to proceed or quit from a script program if an INPUT command
  fails.  PROCEED (default) allows use of IF SUCCESS / IF FAILURE commands.
  This setting is local to the current macro or command file, and is
  inherited by subordinate macros and take files.
```

Compile-time default, from `SHOW INPUT`:

```
 Input autodownload:     off
 Input cancellation:     on
 Input case:             ignore
 Input buffer-length:    4096
 Input echo:             on
 Input silence:          0 (seconds)
 Input timeout:          proceed
 Input scale-factor:     1.0
 Last INPUT:             -1 (INPUT command not yet given)
```

### SET I

Synonym for [SET INPUT](#set-input).

### SET IN

Synonym for [SET INPUT](#set-input).

### SET IKS

```
SET IKS ANONYMOUS INITFILE filename
  The initialization file to be executed for anonymous logins.  By default
  it is .kermrc in the anonymous root directory.  This option is independent
  of the SET IKS INITFILE command which applies only to real users.
 
SET IKS ANONYMOUS LOGIN { ON, OFF }
  Whether anonymous logins are allowed. By default they are allowed, so this
  option need be included only to disallow them (or for clarity, to emphasize
  they are allowed). Anonymous login occurs when the username "anonymous"
  or "ftp" is given, with any password (as with ftpd).
 
SET IKS ANONYMOUS ROOT <directory>
  Specifies a directory tree to which anonymous users are restricted after
  login.
 
SET IKS BANNERFILE <filename>
  The name of a file containing a message to be printed after the user logs
  in, in place of the normal message (copyright notice, "Type HELP or ? for
  help", etc).
 
SET IKS CDFILE <filelist>
  When cdmessage is on, this is the name of the "read me" file to be shown.
  Normally you would specify a relative (not absolute) name, since the file
  is opened using the literal name you specified, after changing to the new
  directory.  Example:
 
    SET IKS CDFILE READ.ME
 
  You can also give a list of up to 8 filenames by (a) enclosing each
  filename in braces, and (b) enclosing the entire list in braces.  Example:
 
    SET IKS CDFILE {{READ.ME}{aareadme.txt}{README}{read-this-first}}
 
  When a list is given, it is searched from left to right and the first
  file found is displayed.
 
SET IKS CDMESSAGE {ON, OFF, 0, 1, 2}
  For use in the Server-Side Server configuration; whenever the client
  tells the server to change directory, the server sends the contents of a
  "read me" file to the client's screen.  This feature is ON by default,
  and operates in client/server mode only when ON or 1.  If set to 2 or
  higher, it also operates when the CD command is given at the IKSD> prompt.
  Synonym: SET IKS CDMSG.
 
SET IKS DATABASE { ON, OFF }
  This command determines whether entries are inserted into the SET IKS
  DBFILE (IKSD active sessions database).
 
SET IKS DBFILE <filename>
  Specifies the file which should be used for storing runtime status
  information about active connections.  The default is a file called
  "iksd.db" in the /var/log directory.
 
 
SET IKS HELPFILE <filename>
  Specifies the name of a file to be displayed if the user types HELP
  (not followed by a specific command or topic), in place of the built-in
  top-level help text.  The file need not fit on one screen; more-prompting
  is used if the file is more than one screen long if COMMAND MORE-PROMPTING
  is ON, as it is by default.
 
SET IKS INITFILE <filename>
  Execute <filename> rather than the normal initialization file for real
  users; this option does not apply to anonymous users.
 
SET IKS NO-INITFILE { ON, OFF }
  Do not execute an initialization file, even if a real user is logging in.
 
SET IKS SERVER-ONLY { ON, OFF }
  If this option is included on the IKSD command line, the Client Side Server
  configuration is disabled, and the user will not get a Username: or
  Password: prompt, and will not be able to access the IKSD command prompt.
  A FINISH command sent to the IKSD will log it out and close the
  connection, rather than returning it to its prompt.
 
SET IKS TIMEOUT <number>
  This sets a limit (in seconds) on the amount of time the client has to log
  in once the connection is made.  If successful login does not occur within
  the given number of seconds, the connection is closed.  The default timeout
  is 300 seconds (5 minutes).  A value of 0 or less indicates there is to be
  no limit.
 
SET IKS USERFILE <filename>
  This file contains a list of local usernames that are to be denied access
  to Internet Kermit Service.  The default is /etc/ftpusers.  This can be the
  same file that is used by wuftpd, and the syntax is the same: one username
  per line; lines starting with "#" are ignored.  Use this option to
  specify the name of a different forbidden-user file, or use
  "set iks userfile /dev/null" to disable this feature in case there is a
   /etc/ftpusers file but you don't want to use it.
 
SET IKS XFERLOG { ON, OFF }
  Whether a file-transfer log should be kept.  Off by default.  If "on",
  but no SET IKSD XFERFILE command is given, /var/log/iksd.log is used.
 
SET IKS XFERFILE <filename>
  Use this option to specify an iksd log file name.  If you include this
  option, it implies SET IKS XFERFILE ON.
```

### SET INCOMPLETE

```
Syntax: SET INCOMPLETE { DISCARD, KEEP }
  Whether to discard or keep incompletely received files, default is KEEP.
```

### SET KEY

```
Syntax: SET KEY k text
Or:     SET KEY CLEAR
  Configure the key whose "scan code" is k to send the given text when
  pressed during CONNECT mode.  SET KEY CLEAR restores all the default
  key mappings.  If there is no text, the default key binding is restored
  for the key k.  SET KEY mappings take place before terminal character-set
  translation.
 
  To find out the scan code and mapping for a particular key, use the
  SHOW KEY command.
```

### SET LINE

Synonyms: L, PORT

```
Syntax: SET LINE (or SET PORT) [ switches ] [ devicename ]
  Selects a serial-port device to use for making connections.
  Typical device name for this platform: /dev/ttyS0.
  The default device name is /dev/tty (i.e. none).
  If you do not give a SET LINE command or if you give a SET LINE command
  with no device name, or if you specify /dev/tty as the device name,
  Kermit will be in "remote mode", suitable for use on the far end of a
  connection, e.g. as the file-transfer partner of your desktop communication
  software.  If you SET LINE to a specific device other than /dev/tty,
  Kermit is in "local mode", suitable for making a connection to another
  computer.  SET LINE alone resets Kermit to remote mode.
  To use a modem to dial out, first SET MODEM TYPE (e.g., to USR), then
  SET LINE xxx, then SET SPEED, then give a DIAL command.
  For direct null-modem connections, use SET MODEM TYPE NONE, SET LINE xxx,
  then SET FLOW, SET SPEED, and CONNECT.

Optional switches:
  /CONNECT - Enter CONNECT mode automatically if SET LINE succeeds.
  /SERVER  - Enter server mode automatically if SET LINE succeeds.

Also see HELP SET MODEM, HELP SET DIAL, HELP SET SPEED, HELP SET FLOW.
```

### SET L

Synonym for [SET LINE](#set-line).

### SET PORT

Synonym for [SET LINE](#set-line).

### SET LANGUAGE

```
Syntax: SET LANGUAGE name
  Selects language-specific translation rules for text-mode file transfers.
  Used with SET FILE CHARACTER-SET and SET TRANSFER CHARACTER-SET when one
  of these is ASCII.
```

### SET LOCAL-ECHO

```
Syntax: SET LOCAL-ECHO { OFF, ON }
  During CONNECT: OFF means remote host echoes, ON means Kermit
  does its own echoing.  Synonym for SET DUPLEX { FULL, HALF }.
```

### SET LOCALE

```
Syntax: SET LOCALE [ locale-string ]
  Changes the locale for language and character-set to the one given.  The
  local-string is in the format required by your computer, such as
  en_US.US-ASCII or es_VE.ISO8859-1.  C-Kermit's SET LOCALE command affects
  C-Kermit itself and any subprocesses, but does not affect the environment
  from which C-Kermit was invoked.
```

Compile-time default, from `SHOW LOCALE`:

```
Locale enabled:
  LC_COLLATE="C"
  LC_CTYPE="C.UTF-8"
  LC_MONETARY="C"
  LC_MESSAGES="C"
  LC_NUMERIC="C"
  LC_TIME="C"
  LANG="(null)"
```

### SET LOCUS

```
Syntax: SET LOCUS { AUTO, LOCAL, REMOTE }
  Specifies whether unprefixed file management commands should operate
  locally or (when there is a connection to a remote FTP or Kermit
  server) sent to the server.  The affected commands are: CD (CWD), PWD,
  CDUP, DIRECTORY, DELETE, RENAME, MKDIR, and RMDIR.  To force any of
  these commands to be executed locally, give it an L-prefix: LCD, LDIR,
  etc.  To force remote execution, use the R-prefix: RCD, RDIR, and so
  on.  SHOW COMMAND shows the current Locus.
 
  By default, the Locus for file management commands is switched
  automatically whenever you make or close a connection: if you make an
  FTP connection, the Locus becomes REMOTE; if you close an FTP connection
  or make any other kind of connection, the Locus becomes LOCAL.
 
  If you give a SET LOCUS LOCAL or SET LOCUS REMOTE command, this sets
  the locus as indicated and disables automatic switching.
  SET LOCUS AUTO restores automatic switching.
```

### SET LOGIN

```
Not available - "help set login"
```

### SET MACRO

```
Syntax: SET MACRO parameter value
  Controls the behavior of macros.
 
SET MACRO ECHO { ON, OFF }
  Tells whether commands executed from a macro definition should be
  displayed on the screen.  OFF by default; use ON for debugging.
 
SET MACRO ERROR { ON, OFF }
  Tells whether a macro should be automatically terminated upon a command
  error.  This setting is local to the current macro, and inherited by
  subordinate macros.
```

### SET MATCH

```
SET MATCH { DOTFILE, FIFO } { ON, OFF }
  Tells whether wildcards should match dotfiles (files whose names begin
  with period) or UNIX FIFO special files.  MATCH FIFO default is OFF.
  MATCH DOTFILE default is OFF in UNIX, ON elsewhere.
```

### SET MODEM

```
Syntax: SET MODEM <parameter> <value> ...
 
Note: Many of the SET MODEM parameters are configured automatically when
you SET MODEM TYPE, according to the modem's capabilities.  SHOW MODEM to
see them.  Also see HELP DIAL and HELP SET DIAL.
 
SET MODEM TYPE <name>
 Tells Kermit which kind of modem you have, so it can issue the
 appropriate modem-specific commands for configuration, dialing, and
 hanging up.  For a list of the modem types known to Kermit, type "set
 modem type ?".  The default modem type is GENERIC, which should work
 with any AT command-set modem that is configured for error correction,
 data compression, and hardware flow control.  Use SET MODEM TYPE NONE
 for direct serial, connections.  Use SET MODEM TYPE USER-DEFINED to use
 a type of modem that is not built in to Kermit, and then use SET MODEM
 CAPABILITIES, SET MODEM, DIAL-COMMAND, and SET MODEM COMMAND to tell
 Kermit how to configure and control it.
 
SET MODEM CAPABILITIES <list>
  Use this command for changing Kermit's idea of your modem's capabilities,
  for example, if your modem is supposed to have built-in error correction
  but in fact does not.  Also use this command to define the capabilities
  of a USER-DEFINED modem.  Capabilities are:
 
    AT      AT-commands
    DC      data-compression
    EC      error-correction
    HWFC    hardware-flow
    ITU     v25bis-commands
    SWFC    software-flow
    KS      kermit-spoof
    SB      speed-buffering
    TB      Telebit
 
SET MODEM CARRIER-WATCH { AUTO, ON, OFF }
  Synonym for SET CARRIER-WATCH (q.v.)
 
SET MODEM COMPRESSION { ON, OFF }
  Enables/disables the modem's data compression feature, if any.
 
SET MODEM DIAL-COMMAND <text>
  The text replaces Kermit's built-in modem dialing command.  It must
  include '%s' (percent s) as a place-holder for the telephone numbers
  given in your DIAL commands.
 
SET MODEM ERROR-CORRECTION { ON, OFF }
  Enables/disables the modem's error-correction feature, if any.
 
SET MODEM ESCAPE-CHARACTER number
  Numeric ASCII value of modem's escape character, e.g. 43 for '+'.
  For Hayes-compatible modems, Kermit uses three copies, e.g. "+++".
 
SET MODEM FLOW-CONTROL {AUTO, NONE, RTS/CTS, XON/XOFF}
  Selects the type of local flow control to be used by the modem.
 
SET MODEM HANGUP-METHOD { MODEM-COMMAND, RS232-SIGNAL, DTR }
  How hangup operations should be done.  MODEM-COMMAND means try to
  escape back to the modem's command processor and give a modem-specific
  hangup command.  RS232-SIGNAL means turn off the DTR signal.  DTR is a
  synonym for RS232-SIGNAL.
 
SET MODEM KERMIT-SPOOF {ON, OFF}
  If the selected modem type supports the Kermit protocol directly,
  use this command to turn its Kermit protocol function on or off.
 
SET MODEM MAXIMUM-SPEED <number>
  Specify the maximum interface speed for the modem.
 
SET MODEM NAME <text>
  Descriptive name for a USER-DEFINED modem.
 
SET MODEM SPEAKER {ON, OFF}
  Turns the modem's speaker on or off during dialing.
 
SET MODEM SPEED-MATCHING {ON, OFF}
  ON means that C-Kermit changes its serial interface speed to agree with
  the speed reported by the modem's CONNECT message, if any.  OFF means
  Kermit should not change its interface speed.
 
SET MODEM VOLUME {LOW, MEDIUM, HIGH}
  Selects the desired modem speaker volume for when the speaker is ON.
 
SET MODEM COMMAND commands are used to override built-in modem commands for
each modem type, or to fill in commands for the USER-DEFINED modem type.
Omitting the optional [ text ] restores the built-in modem-specific command,
if any:
 
SET MODEM COMMAND AUTOANSWER {ON, OFF} [ text ]
  Modem commands to turn autoanswer on and off.
 
SET MODEM COMMAND COMPRESSION {ON, OFF} [ text ]
  Modem commands to turn data compression on and off.
 
SET MODEM COMMAND ERROR-CORRECTION {ON, OFF} [ text ]
  Modem commands to turn error correction on and off.
 
SET MODEM COMMAND HANGUP [ text ]
  Command that tells the modem to hang up the connection.
 
SET MODEM COMMAND IGNORE-DIALTONE [ text ]
  Command that tells the modem not to wait for dialtone before dialing.
 
SET MODEM COMMAND INIT-STRING [ text ]
  The 'text' is a replacement for C-Kermit's built-in initialization command
  for the modem.
 
SET MODEM COMMAND PREDIAL-INIT [ text ]
  A second INIT-STRING that is to be sent to the modem just prior to dialing.
 
SET MODEM COMMAND HARDWARE-FLOW [ text ]
  Modem command to enable hardware flow control (RTS/CTS) in the modem.
 
SET MODEM COMMAND SOFTWARE-FLOW [ text ]
  Modem command to enable local software flow control (Xon/Xoff) in modem.
 
SET MODEM COMMAND SPEAKER { ON, OFF } [ text ]
  Modem command to turn the modem's speaker on or off.
 
SET MODEM COMMAND NO-FLOW-CONTROL [ text ]
  Modem command to disable local flow control in the modem.
 
SET MODEM COMMAND PULSE [ text ]
  Modem command to select pulse dialing.
 
SET MODEM COMMAND TONE [ text ]
  Modem command to select tone dialing.
 
SET MODEM COMMAND VOLUME { LOW, MEDIUM, HIGH } [ text ]
  Modem command to set the modem's speaker volume.
```

Compile-time default, from `SHOW MODEM`:

```
 Communication device not yet selected with SET LINE
 Modem type: generic
 Generic high-speed AT command set

 Modem capabilities:     AT SB EC DC HWFC
 Modem carrier-watch:    auto
 Modem maximum-speed:    115200 bps
 Modem error-correction: on
 Modem compression:      on
 Modem speed-matching:   off (interface speed is locked)
 Modem flow-control:     auto
 Modem hangup-method:    modem-command
 Modem speaker:          on
 Modem volume:           medium
 Modem kermit-spoof:     off
 Modem escape-character: 43 (= "+")

MODEM COMMANDs (* = set automatically by SET MODEM TYPE):

 * Init-string:          (none)
 * Dial-mode-string:     (none)
 * Dial-mode-prompt:     (none)
 * Dial-command:         ATD%s\{13}
 * Compression on:       (none)
 * Compression off:      (none)
 * Error-correction on:  (none)
 * Error-correction off: (none)
 * Autoanswer on:        ATS0=1\{13}
 * Autoanswer off:       ATS0=0\{13}
 * Speaker on:           (none)
 * Speaker off:          (none)
 * Volume low:           (none)
 * Volume medium:        (none)
 * Volume high:          (none)
 * Hangup-command:       ATQ0H0\{13}
 * Hardware-flow:        (none)
 * Software-flow:        (none)
 * No-flow-control:      (none)
 * Pulse:                ATP\{13}
 * Tone:                 ATT\{13}
 * Ignore-dialtone:      ATX3\{13}
 * Predial-init:         (none)

 For more info: SHOW DIAL and SHOW COMMUNICATIONS
```

### SET NETWORK

```
Syntax: SET NETWORK { TYPE network-type, DIRECTORY [ file(s)... ] }
 
Select the type of network to be used with SET HOST connections:
 
  SET NETWORK TYPE COMMAND   ; Make a connection through an external command
  SET NETWORK TYPE TCP/IP    ; Internet: Telnet, Rlogin, etc.
 
If only one network type is listed above, that is the default network for
SET HOST commands.  Also see SET HOST, TELNET, RLOGIN.
 
SET NETWORK DIRECTORY [ file [ file [ ... ] ] ]
  Specifies the name(s) of zero or more network directory files, similar to
  dialing directories (HELP DIAL for details).  The general format of a
  network directory entry is:
 
    name network-type address [ network-specific-info ] [ ; comment ]
 
  For TCP/IP, the format is:
 
    name tcp/ip ip-hostname-or-address [ socket ] [ ; comment ]
 
You can have multiple network directories and you can have multiple entries
with the same name.  SET HOST <name> and TELNET <name> commands look up the
given <name> in the directory and, if found, fill in the additional items
from the entry, and then try all matching entries until one succeeds.
```

Compile-time default, from `SHOW NETWORK`:

```
Network directory: (none)
SSH COMMAND: ssh -e none

Supported networks:
 TCP/IP

SET TCP parameters:
 Reverse DNS lookup: automatic
 DNS Service Records lookup: off
 Keepalive: on
 Linger: off
 DontRoute: off
 Nodelay: off
 Send buffer: (default size)
 Receive buffer: (default size)
 address-family: auto
 address: (none)
 address6: (none)
 http-proxy: (none)

SET TELNET parameters:
 echo: local
 NVT newline-mode: on (cr-lf)
 authentication: requested   in use: NULL
  credentials forwarding disabled
 encryption: requested       in use: plain text in both directions
 kermit: u, requested; me, requested;  u, n/a me, n/a;
 BINARY newline-mode: raw (cr)
 binary-mode: u, accepted;  me, accepted; u, NVT; me, NVT
 binary-transfer-mode: off
 bug binary-me-means-u-too: off
 bug binary-u-means-me-too: off
 bug sb-implies-will-do: on
 bug auth-krb5-des: on
 terminal-type: none (xterm will be used)
 environment: on
   ACCOUNT: 
   DISPLAY: 
   JOB    : 
   PRINTER: 
   USER   : jgoerzen
   SYSTEM : UNIX
  LOCATION: 
 .Xauthority-file: /home/jgoerzen/.Xauthority

Active network connection:
 Host: none, via: tcp/ip
```

### SET OUTPUT

```
SET OUTPUT PACING <number>
  How many milliseconds to pause after sending each OUTPUT character,
  normally 0.
 
SET OUTPUT SPECIAL-ESCAPES { ON, OFF }
  Whether to process the special OUTPUT-only escapes \B, \L, and \N.
  Normally ON (they are processed).
```

Compile-time default, from `SHOW OUTPUT`:

```
 Output pacing:          0 (milliseconds)
 Output special-escapes: on
```

### SET OPTIONS

```
Syntax: SET OPTIONS command [ switches... ]
  For use with commands that have switches; sets the default switches for
  the given command.  Type SET OPTIONS ? for a list of amenable commands.
```

Compile-time default, from `SHOW OPTIONS`:

```
 DELETE /NOASK /NODOTFILES /NOLIST /NOHEADING

 DIRECTORY /ALL /VERBOSE /BACKUP /NOHEADING /SORT:NAME /ASCENDING

 PURGE /NOASK /NODOTFILES /KEEP:0 /NOLIST /NOHEADING

 TYPE  (no options set)
```

### SET SLEEP

Synonyms: PAUSE, WAIT

```
Syntax: SET SLEEP CANCELLATION { ON, OFF }
  Tells whether SLEEP (PAUSE) or WAIT commands can be interrupted from the
  keyboard; ON by default.
```

### SET PAUSE

Synonym for [SET SLEEP](#set-sleep).

### SET WAIT

Synonym for [SET SLEEP](#set-sleep).

### SET PARITY

```
SET PARITY NONE
  Chooses 8 data bits and no parity.
 
SET PARITY { EVEN, ODD, MARK, SPACE }
  Chooses 7 data bits plus the indicated kind of parity.
  Forces 8th-bit prefixing during file transfer.
 
SET PARITY HARDWARE { EVEN, ODD }
  Chooses 8 data bits plus the indicated kind of parity.
 
Also see SET TERMINAL BYTESIZE, SET SERIAL, and SET STOP-BITS.
```

### SET PROMPT

Synonym: PR

```
Syntax: SET PROMPT [ text ]
 
Prompt text for this program, normally 'C-Kermit>'.  May contain backslash
codes for special effects.  Surround by { } to preserve leading or trailing
spaces.  If text omitted, prompt reverts to C-Kermit>.  Prompt can include
variables like \v(dir) or \v(time) to show current directory or time.
```

### SET PR

Synonym for [SET PROMPT](#set-prompt).

### SET PRINTER

```
Syntax: SET PRINTER [ { |command, filename } ]
  Specifies the command (such as "|lpr") or filename to be used by the
  PRINT command.  If a filename is given, each PRINT command appends to the
  given file.  If the SET PRINTER argument contains spaces, it must be
  enclosed in braces, e.g. "set printer {| lpr -Plaser}". If the argument
  is omitted the default value is restored.  SHOW PRINTER lists the current
  printer.  See HELP PRINT for further info.
```

Compile-time default, from `SHOW PRINTER`:

```
Printer: (default)
```

### SET PREFIXING

```
Syntax: SET PREFIXING { ALL, CAUTIOUS, MINIMAL }
  Selects the degree of control-character prefixing.  Also see HELP SET CONTROL.
```

Compile-time default, from `SHOW CONTROL-PREFIXING`:

```
control quote = 35, applied to (0 = unprefixed, 1 = prefixed):

    0: 1    16: 1           128: 0   144: 1 
    1: 1    17: 1           129: 1   145: 1 
    2: 0    18: 0           130: 0   146: 0 
    3: 1    19: 1           131: 1   147: 1 
    4: 1    20: 0           132: 1   148: 0 
    5: 0    21: 1           133: 0   149: 1 
    6: 0    22: 0           134: 0   150: 0 
    7: 0    23: 0           135: 0   151: 0 
    8: 0    24: 1           136: 0   152: 0 
    9: 0    25: 1           137: 0   153: 0 
   10: 1    26: 1           138: 1   154: 1 
   11: 0    27: 0           139: 0   155: 0 
   12: 0    28: 1           140: 0   156: 1 
   13: 1    29: 1           141: 1   157: 1 
   14: 1    30: 1           142: 0   158: 1 
   15: 1    31: 0   127: 0  143: 0   159: 0   255: 1
```

### SET PROTOCOL

```
Syntax: SET PROTOCOL { KERMIT, XMODEM, YMODEM, ZMODEM } [ s1 s2 s3 s4 s5 s6 ]
  Selects protocol to use for transferring files.  s1 and s2 are commands to
  output prior to SENDing with this protocol, to automatically start the
  RECEIVE process on the other end in binary or text mode, respectively.
  If the protocol is KERMIT, s3 is the command to start a Kermit server on
  the remote computer, and there are no s4-s6 commands.  Otherwise, s3 and
  s4 are commands used on this computer for sending files with this protocol
  in binary or text mode, respectively; s5 and s6 are the commands for
  receiving files with this protocol.  Use "%s" in any of these strings
  to represent the filename(s).  Use { braces } if any command contains
  spaces.  Examples:
 
    set proto kermit {kermit -YQir} {kermit -YQTr} {kermit -YQx}
    set proto ymodem rb {rb -a} {sb %s} {sb -a %s} rb rb
 
External protocols require REDIRECT and external file transfer programs that
use redirectable standard input/output.
 
  SHOW PROTOCOL displays the current settings.
```

Compile-time default, from `SHOW PROTOCOL`:

```
Protocol: Kermit

Protocol Parameters:   Send    Receive
 Timeout (used= 8):      8       15        Cancellation:    on 3 3
 Padding:                0        0        Block Check:      3
 Pad Character:          0        0        Delay:            1
 Pause:                  0        0        Attributes:      on
 Packet Start:           1        1        Max Retries:     10
 Packet End:            13       13        8th-Bit Prefix: ('&' but not used)
 Packet Length:         90     4000        Repeat Prefix:  ('~' but not used)
 Maximum Length:      9024     9024        Window Size:     30 set, 0 used
 Buffer Size:       290015   290015        Locking-Shift:    enabled, not used

 Auto-upload command (binary): kermit -ir
 Auto-upload command (text):   kermit -r
 Auto-server command:          kermit -x
 Packet timeouts: dynamic 1:0  Send backup: on
 Transfer mode:   manual       Transfer slow-start: on, crc: off
 Transfer pipes:  off          Transfer character-set: transparent
 Send filter:     (none)
 Receive filter:  (none)

Also see:
 SHOW FILE, SHOW XFER, SHOW PATTERNS, SHOW STREAMING, SHOW CHARACTER-SETS
```

### SET QUIET

Synonym: Q

```
Syntax: SET QUIET {ON, OFF}
  Normally OFF.  ON disables most information messages during interactive
  operation.
```

### SET Q

Synonym for [SET QUIET](#set-quiet).

### SET Q8FLAG

```
Not available - "help set q8flag"
```

### SET QNX-PORT-LOCK

```
Not available - "help set qnx-port-lock"
```

### SET RECEIVE

Synonyms: REC, RECV

```
Syntax: SET RECEIVE parameter value
  Specifies parameters for inbound packets:
 
SET RECEIVE CHARACTER-SET { AUTOMATIC, MANUAL }
  Whether to automatically switch to an appropriate file-character set based
  on the transfer character-set announcer, if any, of an incoming text file.
  AUTOMATIC by default.  Also see HELP ASSOCIATE.
 
SET RECEIVE CONTROL-PREFIX number
  ASCII value of prefix character used for quoting control characters in
  packets that Kermit receives, normally 35 (number sign).  Don't change
  this unless something is wrong with the other Kermit program.
 
SET RECEIVE END-OF-PACKET number
  ASCII value of control character that terminates incoming packets,
  normally 13 (carriage return).
 
SET RECEIVE IGNORE-CHARACTER number
  ASCII value of character to be discarded when receiving packets, such as
  line folding characters.
 
SET RECEIVE MOVE-TO [ directory ]
  If a directory name is specified, then every file that is received
  successfully is moved to the given directory immediately after reception
  is complete.  Omit the directory name to remove any previously set move-to
  directory.
 
SET RECEIVE PACKET-LENGTH number
  Maximum length packet the other Kermit should send.
 
SET RECEIVE PADDING number
  Number of prepacket padding characters to ask for (normally 0).
 
SET RECEIVE PAD-CHARACTER number
  ASCII value of control character to use for padding (normally 0).
 
SET RECEIVE PATHNAMES {OFF, ABSOLUTE, RELATIVE, AUTO}
  If a recognizable path (directory, device) specification appears in an
  incoming filename, strip it OFF before trying to create the output file.
  Otherwise, then if any of the directories in the path don't exist, Kermit
  tries to create them, relative to your current or download directory, or
  absolutely, as specified.  RELATIVE means force all incoming names, even
  if they are absolute, to be relative to your current or download directory.
  AUTO, which is the default, means RELATIVE if the file sender indicates in
  advance that this is a recursive transfer, otherwise OFF.
 
SET RECEIVE PAUSE number
  Milliseconds to pause between packets, normally 0.
 
SET RECEIVE PERMISSIONS { ON, OFF }
  Whether to copy file permissions from inbound Attribute packets.
 
SET RECEIVE RENAME-TO [ template ]
  If a template is specified, then every file that is received successfully
  is renamed according to the given template immediately after it is received.
  The template should include variables like \v(filename) or \v(filenumber).
  Omit the template to remove any template previously set.
 
SET RECEIVE START-OF-PACKET number
  ASCII value of character that marks start of inbound packet.
 
SET RECEIVE TIMEOUT number
  Number of seconds the other Kermit should wait for a packet before sending
  a NAK or retransmitting.
```

### SET REC

Synonym for [SET RECEIVE](#set-receive).

### SET RECV

Synonym for [SET RECEIVE](#set-receive).

### SET RELIABLE

```
Syntax: SET RELIABLE { ON, OFF, AUTO }
  Tells Kermit whether its connection is reliable.  Default is AUTO,
  meaning Kermit should figure it out for itself.
```

### SET RENAME

```
SET RENAME LIST { ON, OFF }
  Tells whether the RENAME command should list its results by default.

SET RENAME COLLISION { FAIL, PROCEED, OVERWRITE }
  Establishes the default action when renaming a file would destroy an
  existing file.  See HELP RENAME.
```

Compile-time default, from `SHOW RENAME`:

```
 rename collision: overwrite
 rename list:      off
```

### SET REPEAT

```
Syntax: SET REPEAT { COUNTS { ON, OFF }, PREFIX <code> }
  SET REPEAT COUNTS turns the repeat-count compression mechanism ON and OFF.
  The default is ON.  SET REPEAT PREFIX <code> sets the repeat-count prefix
  character to the given code.  The default is 126 (tilde).
```

### SET RETRY-LIMIT

```
Syntax: SET RETRY number
  In Kermit protocol file transfers: How many times to retransmit a
  particular packet before giving up; 0 = no limit.
```

### SET ROOT

```
Syntax: SET ROOT directoryname
  Sets the root for file access to the given directory and disables access
  to system and shell commands and external programs.  Once this command
  is given, no files or directories outside the tree rooted by the given
  directory can be opened, read, listed, deleted, renamed, or accessed in
  any other way.  This command can not be undone by a subsequent SET ROOT
  command.  Primarily for use with server mode, to restrict access of
  clients to a particular directory tree.  Synonym: CHROOT.
```

### SET SCRIPT

```
Syntax: SET SCRIPT ECHO { OFF, ON }
  Disables/Enables echoing of SCRIPT command operation.
```

### SET SEND

```
Syntax: SET SEND parameter value
  Specifies parameters for outbound files or packets.
 
SET SEND BACKUP { ON, OFF }
  Tells whether to include backup files when sending file groups.  Backup
  files are those created by Kermit, EMACS, etc, when creating a new file
  that has the same name as an existing file.  A backup file has a version
  appended to its name, e.g. oofa.txt.~23~.  ON is the default, meaning
  don't exclude backup files.  Use OFF to exclude backup files from group
  transfers.
 
SET SEND CHARACTER-SET { AUTOMATIC, MANUAL }
  Whether to automatically switch to an appropriate file-character when a
  SET TRANSFER CHARACTER-SET command is given, or vice versa.  AUTOMATIC by
  default.  Also see HELP ASSOCIATE.
 
SET SEND CONTROL-PREFIX number
  ASCII value of prefix character used for quoting control characters in
  packets that Kermit sends, normally 35 (number sign).
 
SET SEND DOUBLE-CHARACTER number
  ASCII value of character to be doubled when sending packets, such as an
  X.25 PAD escape character.
 
SET SEND END-OF-PACKET number
  ASCII value of control character to terminate an outbound packet,
  normally 13 (carriage return).
 
SET SEND MOVE-TO [ directory ]
  If a directory name is specified, then every file that is sent successfully
  is moved to the given directory immediately after it is sent.
  Omit the directory name to remove any previously set move-to directory.
 
SET SEND PACKET-LENGTH number
  Maximum length packet to send, even if other Kermit asks for longer ones.
  This command can not be used to force packets to be sent that are longer
  than the length requested by the receiver.  Use this command only to
  force shorter ones.
 
SET SEND PADDING number
  Number of prepacket padding characters to send.
 
SET SEND PAD-CHARACTER number
  ASCII value of control character to use for padding.
 
SET SEND PATHNAMES {OFF, ABSOLUTE, RELATIVE}
  Include the path (device, directory) portion with the file name when
  sending it as specified; ABSOLUTE means to send the whole pathname,
  RELATIVE means to include the pathname relative to the current directory.
  Applies to the actual filename, not to the "as-name".  The default is
  OFF.
 
SET SEND PAUSE number
  Milliseconds to pause between packets, normally 0.
 
SET SEND PERMISSIONS { ON, OFF }
  Whether to include file permissions in outbound Attribute packets.
 
SET SEND RENAME-TO [ template ]
  If a template is specified, then every file that is sent successfully
  is renamed according to the given template immediately after it is sent.
  The template should include variables like \v(filename) or \v(filenumber).
  Omit the template to remove any template previously set.
 
SET SEND START-OF-PACKET number
  ASCII value of character to mark start of outbound packet.
 
SET SEND TIMEOUT number [ { DYNAMIC [ min max ] ], FIXED } ]
  Number of seconds to wait for a packet before sending NAK or
  retransmitting.  Include the word DYNAMIC after the number in the
  SET SEND TIMEOUT command to have Kermit compute the timeouts dynamically
  throughout the transfer based on the packet rate.  Include the word FIXED
  to use the "number" given throughout the transfer.  DYNAMIC is the
  default.  After DYNAMIC you may include minimum and maximum values.
  SET SEND TIMEOUT -1 FIXED means no timeouts.
```

### SET SERVER

Synonym: SER

```
SET SERVER CD-MESSAGE {ON,OFF}
  Tells whether the server, after successfully executing a REMOTE CD
  command, should send the contents of the new directory's READ.ME
  (or similar) file to your screen.
 
SET SERVER CD-MESSAGE FILE name
  Tells the name of the file to be displayed as a CD-MESSAGE, such as
  READ.ME (SHOW SERVER tells the current CD-MESSAGE FILE name).
  To specify more than one filename to look for, use {{name1}{name2}..}.
  Synonym: SET CD MESSAGE FILE <list>.
 
SET SERVER DISPLAY {ON,OFF}
  Tells whether local-mode C-Kermit during server operation should put a
  file transfer display on the screen.  Default is OFF.
 
SET SERVER GET-PATH [ directory [ directory [ ... ] ] ]
  Tells the C-Kermit server where to look for files whose names it receives
  from client GET commands when the names are not fully specified pathnames.
  Default is no GET-PATH, so C-Kermit looks only in its current directory.
 
SET SERVER IDLE-TIMEOUT seconds
  Idle time limit while in server mode, 0 for no limit.
  NOTE: SERVER IDLE-TIMEOUT and SERVER TIMEOUT are mutually exclusive.
 
SET SERVER KEEPALIVE {ON,OFF}
  Tells whether C-Kermit should send "keepalive" packets while executing
  REMOTE HOST commands, which is useful in case the command takes a long
  time to produce any output and therefore might cause the operation to time
  out.  ON by default; turn it OFF if it causes trouble with the client or
  slows down the server too much.
 
SET SERVER LOGIN [ username [ password [ account ] ] ]
  Sets up a username and optional password which must be supplied before
  the server will respond to any commands other than REMOTE LOGIN.  The
  account is ignored.  If you enter SET SERVER LOGIN by itself, then login
  is no longer required.  Only one SET SERVER LOGIN command can be in effect
  at a time; C-Kermit does not support multiple user/password pairs.
 
SET SERVER TIMEOUT n
  Server command wait timeout interval, how often the C-Kermit server issues
  a NAK while waiting for a command packet.  Specify 0 for no NAKs at all.
  Default is 0.
```

Compile-time default, from `SHOW SERVER`:

```
Function:          Status:
 GET                Remote only
 SEND               Remote only
 MAIL               Disabled
 PRINT              Disabled
 REMOTE ASSIGN      Remote only
 REMOTE CD/CWD      Remote only
 REMOTE COPY        Remote only
 REMOTE DELETE      Remote only
 REMOTE DIRECTORY   Remote only
 REMOTE HOST        Remote only
 REMOTE QUERY       Remote only
 REMOTE MKDIR       Remote only
 REMOTE RMDIR       Remote only
 REMOTE RENAME      Remote only
 REMOTE SET         Remote only
 REMOTE SPACE       Remote only
 REMOTE TYPE        Remote only
 REMOTE WHO         Remote only
 BYE                Remote only
 FINISH             Remote only
 EXIT               Remote only
 ENABLE             Remote only
Server timeout:      0
Server idle-timeout: 0
Server keepalive     on
Server cd-message    off
Server display:      on
Server login:        (none)
Server get-path:     (none)
```

### SET SER

Synonym for [SET SERVER](#set-server).

### SET SERIAL

```
Syntax: SET SERIAL dps
  d is data length in bits, 7 or 8; p is first letter of parity; s is stop
  bits, 1 or 2.  Examples: "set serial 7e1", "set serial 8n1".
```

### SET SESSION-LOG

Synonym: SESSION-L

```
Syntax:
 SET SESSION-LOG { BINARY, DEBUG, NULL-PADDED, TEXT, TIMESTAMPED-TEXT }
  If BINARY, record all CONNECT characters in session log.  If TEXT, strip
  out CR, NUL, and XON/XOFF characters.  DEBUG is the same as BINARY but
  also includes Telnet negotiations on TCP/IP connections.
```

### SET SESSION-L

Synonym for [SET SESSION-LOG](#set-session-log).

### SET SEXPRESSION

```
SET SEXPRESSION { DEPTH-LIMIT, ECHO-RESULT, TRUNCATE-ALL-RESULTS }
  DEPTH-LIMIT sets a limit on the depth of nesting or recursion in
  S-Expressions to prevent the program from crashing from memory exhaustion.
  ECHO-RESULT tells whether S-Expression results should be displayed as
  a result of evaluating an expression; the default is to display only at
  top (interactive) level; OFF means never display; ON means always display.
  TRUNCATE-ALL-RESULTS ON means the results of all arithmetic operations
  should be forced to integers (whole numbers) by discarding any fractional
  part.  The default is OFF.  SHOW SEXPRESSION displays the current settings.
```

Compile-time default, from `SHOW SEXPRESSION`:

```
 sexpression echo-result: automatic
 sexpression depth-limit: 1000

 maximum depth reached:   0
 longest result returned: 0

 truncate all results:    off

 last sexpression:        (none)
 last value:              (none)
```

### SET SSH

```
Syntax: SET SSH COMMAND command
  Specifies the external command to be used to make an SSH connection.
  By default it is "ssh -e none" (ssh with no escape character).
```

Compile-time default, from `SHOW SSH`:

```
 SSH is external.

 ssh command: ssh -e none
```

### SET STARTUP-FILE

```
Not available - "help set startup-file"
```

### SET STOP-BITS

```
Syntax: SET STOP-BITS { 1, 2 }
  Number of stop bits to use on SET LINE connections, normally 1.
```

### SET STREAMING

```
Syntax: SET STREAMING { ON, OFF, AUTO }
  Tells Kermit whether streaming protocol can be used during Kermit file
  transfers.  Default is AUTO, meaning use it if connection is reliable.
```

Compile-time default, from `SHOW STREAMING`:

```
 Reliable:     automatic
 Clearchannel: automatic
 Streaming:    automatic

 Streaming will be done if requested.
 Last transfer: no streaming, 0 cps.
```

### SET SUSPEND

```
Syntax: SET SUSPEND { OFF, ON }
  Disables SUSPEND command, suspend signals, and <esc-char>Z during CONNECT.
```

### SET TAKE

```
Syntax: SET TAKE parameter value
 
  Controls behavior of TAKE command:
 
SET TAKE ECHO { ON, OFF }
  Tells whether commands read from a TAKE file should be displayed on the
  screen (if so, each command is shown at the time it is read, and labeled
  with a line number).
 
SET TAKE ERROR { ON, OFF }
  Tells whether a TAKE command file should be automatically terminated when
  a command fails.  This setting is local to the current command file, and
  inherited by subordinate command files.
```

### SET TCP

```
SET TCP ADDRESS <ip-address>
  This allows a specific local IPv4 address on a multihomed host to be used
  instead of allowing the TCP/IP stack to choose.  This may be necessary
  when using authentication or listening for an incoming connection.
  Specify no <ip-address> to remove the preference.  <ip-address> must
  be an IPv4 literal.
 
  This setting only affects IPv4 connections and listeners.  It is
  applied to an IPv4 candidate when SET TCP ADDRESS-FAMILY is AUTO or
  IPV4, and has no effect on IPv6 candidates.  See SET TCP ADDRESS6 for
  the IPv6 equivalent.  The two are independent.
 
SET TCP ADDRESS6 <ipv6-address>
  Like SET TCP ADDRESS, but for IPv6.  It gives a specific IPv6 address
  on a multihomed host to use as the local address for outgoing IPv6
  connections and the IPv6 listening socket, instead of letting the
  TCP/IP stack choose.  <ipv6-address> must be an IPv6 literal.  Specify
  no <ipv6-address> to remove the preference.  Only affects IPv6
  connections and listeners.
 
SET TCP KEEPALIVE { ON, OFF }
  Setting this ON might help to detect broken connections more quickly.
  (default is ON.)
 
SET TCP LINGER { ON [timeout], OFF }
  Setting this ON ensures that a connection doesn't close before all
  outstanding data has been transferred and acknowledged.  The timeout is
  measured in 10ths of milliseconds.  The default is ON with a timeout of 0.
 
SET TCP NODELAY { ON, OFF }
  ON means send short TCP packets immediately rather than waiting
  to accumulate a bunch of them before transmitting (Nagle Algorithm).
  (default is OFF.)
 
SET TCP RECVBUF <number>
SET TCP SENDBUF <number>
   TCP receive and send buffer sizes.  (default is -1, use system defaults.)
 
These items let you tune TCP networking performance on a per-connection
basis by adjusting parameters you normally would not have access to.  You
should use these commands only if you feel that the TCP/IP protocol stack
that Kermit is using is giving you inadequate performance, and then only if
you understand the concepts (see, for example, the Comer TCP/IP books), and
then at your own risk.  These settings are displayed by SHOW NETWORK.  Not
all options are necessarily available in all Kermit versions; it depends on
the underlying TCP/IP services.
 
The following TCP and/or IP parameter(s) may also be changed:
 
SET TCP ADDRESS-FAMILY { IPV4, IPV6, AUTO }
  Selects which IP address family to use for incoming and outgoing TCP/IP
  connections (SET HOST, TELNET, FTP, and the like).  IPV4 or IPV6
  restrict connections to that family only.  AUTO, the default, lets
  Kermit try both, in the order the system resolver returns them for
  the given hostname -- typically IPv6 first if this host has working
  IPv6 connectivity, falling back to IPv4 if that fails, the same way
  ordinary Telnet clients behave.
 
SET TCP REVERSE-DNS-LOOKUP { AUTO, ON, OFF }
  Tells Kermit whether to perform reverse DNS lookup on TCP/IP connections
  so Kermit can determine the actual hostname of the host it is connected
  to, which is useful for connections to host pools, and is required for
  Kerberos connections to host pools and for incoming connections.  If the
  other host does not have a DNS entry, the reverse lookup could take a long
  time (minutes) to fail, but the connection will still be made.  Turn this
  option OFF for speedier connections if you do not need to know exactly
  which host you are connected to and you are not using Kerberos.  AUTO, the
  default, means the lookup is done on hostnames, but not on numeric IP
  addresses unless Kerberos support is installed.
 
SET TCP DNS-SERVICE-RECORDS {ON, OFF}
  Tells Kermit whether to try to use DNS SRV records to determine the
  host and port number upon which to find an advertised service.  For
  example, if a host wants regular Telnet connections redirected to some
  port other than 23, this feature allows Kermit to ask the host which
  port it should use.  Since not all domain servers are set up to answer
  such requests, this feature is OFF by default.
 
SET TCP HTTP-PROXY [<hostname or ip-address>[:<port>]]
  If a hostname or ip-address is specified, Kermit will use the Proxy
  server when attempting outgoing connections.  If no hostname or
  ip-address is specified, any previously specified Proxy server will
  be removed.  If no port number is specified, the "http" service
  will be used.
```

Compile-time default, from `SHOW TCP`:

```
SET TCP parameters:
 Reverse DNS lookup: automatic
 DNS Service Records lookup: off
 Keepalive: on
 Linger: off
 DontRoute: off
 Nodelay: off
 Send buffer: (default size)
 Receive buffer: (default size)
 address-family: auto
 address: (none)
 address6: (none)
 http-proxy: (none)
```

### SET TELNET

Synonym: TEL

```
Syntax: SET TELNET parameter value
 
For TCP/IP TELNET connections, which are in NVT (ASCII) mode by default:
 
SET TELNET AUTHENTICATION TYPE { AUTOMATIC, KERBEROS_IV, KERBEROS_V, ...
  ..., SSL, SRP, NONE } [...]
  AUTOMATIC is the default.  Available options can vary depending on the
  features Kermit was built to support and the operating system
  configuration; type SET TELNET AUTHENTICATION TYPE ? for a list.
 
  When Kermit is the Telnet client:
    AUTOMATIC allows the host to choose the preferred type of authentication.
    NONE instructs Kermit to refuse all authentication methods when the
    authentication option is negotiated.  A list of one or more other values
    allow a specific subset of the supported authentication methods to be
    used.
 
  When Kermit is the Telnet server:
    AUTOMATIC results in available authentication methods being offered
    to the telnet client in the following order:
 
      KERBEROS_V, KERBEROS_IV, SRP, SSL, NTLM
 
  NONE results in no authentication methods being offered to the Telnet
  server when the authentication option is negotiated.  The preferred
  method of disabling authentication is:
 
    SET TELOPT /SERVER AUTHENTICATION REFUSE
 
  A list of one or more authentication methods specifies the order those
  methods are to be offered to the telnet client.
 
SET TELNET AUTHENTICATION ENCRYPT-FLAG { ANY, NONE, TELOPT }
  Use this command to specify which AUTH telopt encryption flags may be
  accepted in client mode or offered in server mode.  The default is ANY.
 
SET TELNET AUTHENTICATION HOW-FLAG { ANY, ONE-WAY, MUTUAL }
  Use this command to specify which AUTH telopt how flags may be
  accepted in client mode or offered in server mode.  The default is ANY.
 
SET TELNET BINARY-TRANSFER-MODE { ON, OFF }
  When ON (OFF by default) and BINARY negotiations are not REFUSED Kermit
  will attempt to negotiate BINARY mode in each direction before the start
  of each file transfer.  After the transfer is complete BINARY mode will
  be restored to the pre-transfer state.
 
SET TELNET BINARY-TRANSFER-MODE { ON, OFF }
  Set this command to ON if you want to force Kermit to negotiate
  Telnet Binary in both directions when performing file transfers.
  Default is OFF.  Alias SET TELNET BINARY-XFER-MODE.
 
SET TELNET BUG AUTH-KRB5-DES { ON, OFF }
  Default is ON.  Disable this bug to enable the use of encryption types
  other than DES such as 3DES or CAST-128 when the Kerberos 5 session key
  is longer than 8 bytes.
 
SET TELNET BUG BINARY-ME-MEANS-U-TOO { ON, OFF }
  Set this to ON to try to overcome TELNET binary-mode misnegotiations by
  Kermit's TELNET partner.
 
SET TELNET BUG BINARY-U-MEANS-ME-TOO { ON, OFF }
  Set this to ON to try to overcome TELNET binary-mode misnegotiations by
  Kermit's TELNET partner.
 
SET TELNET BUG INFINITE-LOOP-CHECK { ON, OFF }
  Set this to ON to prevent Kermit from responding to a telnet negotiation
  sequence that enters an infinite loop.  The default is OFF because this
  should never occur.
 
SET TELNET BUG SB-IMPLIES-WILL-DO { ON, OFF }
  Set this to ON to allow Kermit to respond to telnet sub-negotiations if
  the peer forgets to respond to WILL with DO or to DO with WILL.
 
SET TELNET DEBUG { ON, OFF }
  Set this to ON to display telnet negotiations as they are sent and
  received.
 
SET TELNET DELAY-SB { ON, OFF }
  When ON, telnet subnegotiation responses are delayed until after all
  authentication and encryption options are either successfully negotiated
  or refused. This ensures that private data is protected.  When OFF, telnet
  subnegotiation responses are sent immediately.  The default is ON.
 
SET TELNET ECHO { LOCAL, REMOTE }
  Kermit's initial echoing state for TELNET connections, LOCAL by default.
  After the connection is made, TELNET negotiations determine the echoing.
 
SET TELNET ENCRYPTION TYPE { AUTOMATIC, CAST128_CFB64, CAST128_OFB64, 
  CAST5_40_CFB64, CAST5_40_OFB64, DES_CFB64, DES_OFB64, NONE }
  AUTOMATIC allows the host to choose the preferred type of encryption.
  Other values allow a specific encryption method to be specified.
  AUTOMATIC is the default.  The list of options will vary depending
  on the encryption types selected at compilation time.
 
SET TELNET ENVIRONMENT { variable-name [ value ] }
  This feature lets Kermit send the values of certain environment variables
  to the other computer if it asks for them.  The variable-name can be any
  of the "well-known" variables "USER", "JOB", "ACCT", "PRINTER",
  "SYSTEMTYPE", or "DISPLAY".  Some Telnet servers, if given a USER
  value in this way, will accept it and therefore not prompt you for user
  name when you log in.  The default values are taken from your environment;
  use this command to change or remove them.  See RFC1572 for details.
 
SET TELNET FORWARD-X XAUTHORITY-FILE <file>
  If your X Server requires X authentication and the location of the
  .Xauthority file is not defined by the XAUTHORITY environment variable,
  use this command to specify the location of the .Xauthority file.
  
SET TELNET LOCATION [ text ]
  Location string to send to the Telnet server if it asks.  By default this
  is picked up from the LOCATION environment variable.  Give this command
  with no text to disable this feature.
 
SET TELNET NEWLINE-MODE { NVT, BINARY-MODE } { OFF, ON, RAW }
  Determines how carriage returns are handled on TELNET connections.  There
  are separate settings for NVT (ASCII) mode and binary mode.  ON (default
  for NVT mode) means CRLF represents CR.  OFF means CR followed by NUL
  represents CR.  RAW (default for BINARY mode) means CR stands for itself.
 
SET TELNET PROMPT-FOR-USERID <prompt>
  Specifies a custom prompt to be used when prompting for a userid.  Kermit
  prompts for a userid if the command:
 
    SET LOGIN USERID {}
 
  has been issued prior to a Telnet authentication negotiation for an
  authentication type that requires the transmission of a name, such as
  Secure Remote Password.
 
SET TELNET REMOTE-ECHO { ON, OFF }
  Applies only to incoming connections created with:
    SET HOST * <port> /TELNET
  This command determines whether Kermit will actually echo characters
  received from the remote when it has negotiated to do so.  The default
  is ON.  Remote echoing may be turned off when it is necessary to read
  a password with the INPUT command.
 
SET TELNET TERMINAL-TYPE name
  The terminal type to send to the remote TELNET host.  If none is given,
  your local terminal type is sent.
 
SET TELNET WAIT-FOR-NEGOTIATIONS { ON, OFF }
  Each Telnet option must be fully negotiated either On or Off before the
  session can continue.  This is especially true with options that require
  subnegotiations such as Authentication, Encryption, and Kermit; for
  proper support of these options Kermit must wait for the negotiations to
  complete.  Of course, Kermit has no way of knowing whether a reply is
  delayed or not coming at all, and so will wait a minute or more for
  required replies before continuing the session.  If you know that Kermit's
  Telnet partner will not be sending the required replies, you can set this
  option of OFF to avoid the long timeouts.  Or you can instruct Kermit to
  REFUSE specific options with the SET TELOPT command.
```

Compile-time default, from `SHOW TELNET`:

```
SET TELNET parameters:
 echo: local
 NVT newline-mode: on (cr-lf)
 authentication: requested   in use: NULL
  credentials forwarding disabled
 encryption: requested       in use: plain text in both directions
 kermit: u, requested; me, requested;  u, n/a me, n/a;
 BINARY newline-mode: raw (cr)
 binary-mode: u, accepted;  me, accepted; u, NVT; me, NVT
 binary-transfer-mode: off
 bug binary-me-means-u-too: off
 bug binary-u-means-me-too: off
 bug sb-implies-will-do: on
 bug auth-krb5-des: on
 terminal-type: none (xterm will be used)
 environment: on
   ACCOUNT: 
   DISPLAY: 
   JOB    : 
   PRINTER: 
   USER   : jgoerzen
   SYSTEM : UNIX
  LOCATION: 
 .Xauthority-file: /home/jgoerzen/.Xauthority
```

### SET TEL

Synonym for [SET TELNET](#set-telnet).

### SET TELOPT

```
SET TELOPT [ { /CLIENT, /SERVER } ] <option> -
    { ACCEPTED, REFUSED, REQUESTED, REQUIRED } -
    [ { ACCEPTED, REFUSED, REQUESTED, REQUIRED } ]
  SET TELOPT lets you specify policy requirements for Kermit's handling of
  Telnet option negotiations.  Setting an option REQUIRED causes Kermit
  to offer the option to the peer and disconnect if the option is refused.
  REQUESTED causes Kermit to offer an option to the peer.  ACCEPTED results
  in no offer but Kermit will attempt to negotiate the option if it is
  requested.  REFUSED instructs Kermit to refuse the option if it is
  requested by the peer.
 
  Some options are negotiated in two directions and accept separate policies
  for each direction; the first keyword applies to Kermit itself, the second
  applies to Kermit's Telnet partner; if the second keyword is omitted, an
  appropriate (option-specific) default is applied.  You can also include a
  /CLIENT or /SERVER switch to indicate whether the given policies apply
  when Kermit is the Telnet client or the Telnet server; if no switch is
  given, the command applies to the client.
 
  Note that some of Kermit's Telnet partners fail to refuse options that
  they do not recognize and instead do not respond at all.  In this case it
  is possible to use SET TELOPT to instruct Kermit to REFUSE the option
  before connecting to the problem host, thus skipping the problematic
  negotiation.
 
  Use SHOW TELOPT to view current Telnet Option negotiation settings.
  SHOW TELNET displays current Telnet settings.
```

Compile-time default, from `SHOW TELOPT`:

```
Telnet Option          Me (client)   U (client)  Me (server)   U (server)

000 BINARY                ACCEPTED     ACCEPTED     ACCEPTED     ACCEPTED
                              WONT         DONT                          
001 ECHO                   REFUSED     ACCEPTED    REQUESTED      REFUSED
                              WONT         DONT                          
003 SUPPRESS-GO-AHEAD     ACCEPTED     ACCEPTED    REQUESTED    REQUESTED
                              WONT         DONT                          
023 SEND-LOCATION        REQUESTED      REFUSED      REFUSED      REFUSED
                              WONT         DONT                          
024 TERMINAL-TYPE        REQUESTED      REFUSED      REFUSED    REQUESTED
                              WONT         DONT                          
031 NAWS                 REQUESTED      REFUSED      REFUSED    REQUESTED
                              WONT         DONT                          
035 XDISPLOC               REFUSED      REFUSED      REFUSED      REFUSED
                              WONT         DONT                          
037 AUTHENTICATION       REQUESTED      REFUSED      REFUSED    REQUESTED
                              WONT         DONT                          
038 ENCRYPTION           REQUESTED    REQUESTED    REQUESTED    REQUESTED
                              WONT         DONT                          
039 NEW-ENVIRONMENT      REQUESTED      REFUSED      REFUSED    REQUESTED
                              WONT         DONT                          
044 COM-PORT-CONTROL     REQUESTED      REFUSED      REFUSED      REFUSED
                              WONT         DONT                          
046 START-TLS             ACCEPTED      REFUSED      REFUSED    REQUESTED
                              WONT         DONT                          
047 KERMIT               REQUESTED    REQUESTED    REQUESTED    REQUESTED
                              WONT         DONT                          
049 FORWARD-X              REFUSED     ACCEPTED      REFUSED      REFUSED
                              WONT         DONT                          
```

### SET TEMP-DIRECTORY

Synonym: TMP-DIRECTORY

```
Syntax: SET TEMP-DIRECTORY [ <directory-name> ]
  Tells Kermit to use the given directory for creating temporary files.
  These are used (for example) in FTP downloads and by the CHANGE command.
  If you don't issue this command, C-Kermit picks a directory automatically
  based on the operating system and any environment variables you might have
  set.  Use SHOW TEMP-DIRECTORY or SHOW VARIABLE \v(tmpdir) to see Kermit's
  current temporary directory setting.  Synonym: SET TMP-DIRECTORY.
```

Compile-time default, from `SHOW TEMP-DIRECTORY`:

```
 /tmp/
```

### SET TMP-DIRECTORY

Synonym for [SET TEMP-DIRECTORY](#set-temp-directory).

### SET TERMINAL

```
Syntax: SET TERMINAL parameter value
 
SET TERMINAL TYPE ...
  This command is not available because this version of Kermit does not
  include a terminal emulator.  Instead, it is a "semitransparent pipe"
  (or a totally transparent one, if you configure it that way) to the
  computer or service you have made a connection to.  Your console,
  workstation window, or the terminal emulator or terminal from which you
  are running Kermit provides the emulation.
 
SET TERMINAL APC { ON, OFF, NO-INPUT, UNCHECKED, UNCHECKED-NO-INPUT }
  Controls execution of Application Program Commands sent by the host while
  C-Kermit is in CONNECT mode.  ON allows execution of "safe" commands and
  disallows potentially dangerous commands such as DELETE, RENAME, OUTPUT,
  and RUN.  OFF prevents execution of APCs.  UNCHECKED allows execution of
  all APCs.  OFF is the default.
 
SET TERMINAL AUTODOWNLOAD { ON, OFF, ERROR { STOP, CONTINUE } }
  Enables/disables automatic switching into file-transfer mode when a valid
  Kermit or ZMODEM packet of the appropriate type is received during CONNECT
  mode.  Default is OFF.
 
  When TERMINAL AUTODOWNLOAD is ON, the TERMINAL AUTODOWNLOAD ERROR setting
  tells what to do if an error occurs during a file transfer or other
  protocol operation initiated by the terminal emulator: STOP (the default)
  means to remain in command mode so you can see what happened; CONTINUE
  means to resume the CONNECT session (e.g. so a far-end script can continue
  its work).
 
SET TERMINAL BYTESIZE { 7, 8 }
  Use 7- or 8-bit characters between Kermit and the remote computer during
  terminal sessions.  The default is 8.
 
SET TERMINAL CHARACTER-SET <remote-cs> [ <local-cs> ]
  Specifies the character set used by the remote host, <remote-cs>, and the
  character set used by C-Kermit locally, <local-cs>.  If you don't specify
  the local character set, the current FILE CHARACTER-SET is used.  When
  you specify two different character sets, C-Kermit translates between them
  during CONNECT.  By default, both character sets are TRANSPARENT, and
  no translation is done.
 
SET TERMINAL CR-DISPLAY { CRLF, NORMAL }
  Specifies how incoming carriage return characters are to be displayed
  on your screen.
 
SET TERMINAL DEBUG { ON, OFF }
  Turns terminal session debugging on and off.  When ON, incoming control
  characters are displayed symbolically, rather than be taken as formatting
  commands.  SET TERMINAL DEBUG ON implies SET TELNET DEBUG ON.
 
SET TERMINAL ECHO { LOCAL, REMOTE }
  Specifies which side does the echoing during terminal connection.
 
SET TERMINAL ESCAPE-CHARACTER { ENABLED, DISABLED }
  Turns on/off the ability to escape back from CONNECT mode using the SET
  ESCAPE character.  If you disable it, Kermit returns to its prompt only
  when the connection is closed by the other end.  USE WITH EXTREME CAUTION.
  Also see HELP SET ESCAPE.
 
SET TERMINAL HEIGHT <number>
  Tells C-Kermit how many rows (lines) are on your CONNECT-mode screen.
 
SET TERMINAL IDLE-TIMEOUT <number>
  Sets the limit on idle time in CONNECT mode to the given number of
  seconds.  0 (the default) means no limit.
 
SET TERMINAL IDLE-ACTION { EXIT, HANGUP, OUTPUT [ text ], RETURN }
  Specifies the action to be taken when a CONNECT session is idle for the
  number of seconds given by SET TERMINAL IDLE-TIMEOUT.  The default action
  is to RETURN to command mode.  EXIT exits from Kermit; HANGUP hangs up the
  connection, and OUTPUT sends the given text to the host without leaving
  CONNECT mode; if no text is given a NUL (0) character is sent.
 
SET TERMINAL IDLE-ACTION { TELNET-NOP, TELNET-AYT }
  For TELNET connections only: Sends the indicated Telnet protocol message:
  No Operation (NOP) or "Are You There?" (AYT).
 
SET TERMINAL LF-DISPLAY { CRLF, NORMAL }
  Specifies how incoming linefeed characters are to be displayed
  on your screen.
 
SET TERMINAL LOCKING-SHIFT { OFF, ON }
  Tells Kermit whether to use Shift-In/Shift-Out (Ctrl-O and Ctrl-N) to
  switch between 7-bit and 8-bit characters during CONNECT.  OFF by default.
 
SET TERMINAL NEWLINE-MODE { OFF, ON }
  Tells whether to send CRLF (Carriage Return and Line Feed) when you type
  CR (press the Return or Enter key) in CONNECT mode.
 
SET TERMINAL PRINT { ON, OFF }
  Enables and disables host-initiated transparent printing in CONNECT mode.
 
SET TERMINAL TRIGGER <string>
  Specifies a string that, when detected during any subsequent CONNECT
  session, is to cause automatic return to command mode.  Give this command
  without a string to cancel the current trigger.  See HELP CONNECT for
  additional information.
 
SET TERMINAL WIDTH <number>
 Tells Kermit how many columns (characters) are on your CONNECT-mode screen.
 
Type SHOW TERMINAL to see current terminal settings.
```

Compile-time default, from `SHOW TERMINAL`:

```
Terminal parameters:
   Bytesize: Command: 8 bits              Terminal: 8 bits         
                Type: xterm                  Print: off            
                Echo: remote         Locking-shift: off            
        Newline-mode: off               Cr-display: normal         
                 APC: off             Autodownload: on, error stop 
              Height: -1                     Width: -1             
               Debug: off              Session log: (none)         
        Idle-timeout: 0                Idle-action: return
          Lf-display: normal               Suspend: on             
             Trigger: (none)       

 Escape character: Ctrl-\ (ASCII 28, FS): enabled
 Terminal character-set: ascii (remote) ascii (local)
```

### SET TRANSACTION-LOG

```
Syntax: SET TRANSACTION-LOG { BRIEF, FTP, VERBOSE }
  Selects the transaction-log format; BRIEF and FTP have one line per file;
  FTP is compatible with FTP log.  VERBOSE (the default) has more info.
```

### SET TRANSFER

Synonym: XFER

```
Syntax: SET TRANSFER (or XFER) parameter value
 
Choices:
 
SET TRANSFER BELL { OFF, ON }
  Whether to ring the terminal bell at the end of a file transfer.
 
SET TRANSFER CANCELLATION { OFF, ON [ <code> [ <number> ] ] }
  OFF disables remote-mode packet-mode cancellation from the keyboard.
  ON enables it.  The optional <code> is the control character to use for
  cancellation; the optional <number> is how many consecutive occurrences
  of the given control character are required for cancellation.
 
SET TRANSFER INTERRUPTION { ON, OFF }
  TRANSFER INTERRUPTION is normally ON, allowing for interruption of a file
  transfer in progress by typing certain characters while the file-transfer
  display is active.  SET TRANSFER INTERRUPTION OFF disables interruption
  of file transfer from the keyboard in local mode.
 
SET TRANSFER CRC-CALCULATION { OFF, ON }
  Tells whether Kermit should accumulate a Cyclic Redundancy Check for 
  each file transfer.  Normally ON, in which case the CRC value is available
  in the \v(crc16) variable after the transfer.  Adds some overhead.  Use
  SET TRANSFER CRC OFF to disable.
 
SET TRANSFER CHARACTER-SET name
  Selects the character set used to represent textual data in Kermit
  packets.  Text characters are translated to/from the FILE CHARACTER-SET.
  Choices:
 
  TRANSPARENT (no translation, the default)
  ASCII
  LATIN1 (ISO 8859-1 Latin Alphabet 1)
  LATIN2 (ISO 8859-2 Latin Alphabet 2)
  LATIN9 (ISO 8859-15 Latin Alphabet 9)
  CYRILLIC-ISO (ISO 8859-5 Latin/Cyrillic)
  GREEK-ISO (ISO 8859-7 Latin/Greek)
  HEBREW-ISO (ISO 8859-8 Latin/Hebrew)
  JAPANESE-EUC (JIS X 0208 Kanji + Roman and Katakana)
  UCS-2 (ISO 10646 / Unicode 2-byte form)
  UTF-8 (ISO 10646 / Unicode 8-bit serialized transformation format)
 
SET TRANSFER TRANSLATION { ON, OFF }
  Enables and disables file-transfer character-set translation.  It's
  enabled by default.
 
SET TRANSFER DISPLAY { BRIEF, CRT, FULLSCREEN, NONE, SERIAL }
  Choose the desired format for the progress report to be displayed on
  your screen during file transfers when Kermit is in local mode.
  FULLSCREEN requires your terminal type be set correctly; the others
  are independent of terminal type.
 
SET TRANSFER LOCKING-SHIFT { OFF, ON, FORCED }
  Tell whether locking-shift protocol should be used during file transfer
  to achieve 8-bit transparency on a 7-bit connection.  ON means to request
  its use if PARITY is not NONE and to use it if the other Kermit agrees,
  OFF means not to use it, FORCED means to use it even if the other Kermit
  does not agree.
 
SET TRANSFER MODE { AUTOMATIC, MANUAL }
  Automatic (the default) means Kermit should automatically go into binary
  file-transfer mode and use literal filenames if the other Kermit says it
  has a compatible file system, e.g. UNIX-to-UNIX, but not UNIX-to-DOS.
  Also, when sending files, Kermit should switch between binary and text
  mode automatically per file based on the SET FILE BINARY-PATTERNS and SET
  FILE TEXT-PATTERNS.
 
SET TRANSFER PIPES { ON, OFF }
  Enables/Disables automatic sending from / reception to command pipes when
  the incoming filename starts with '!'.  Also see CSEND, CRECEIVE.
 
SET TRANSFER PROTOCOL { KERMIT, XMODEM, ... }
  Synonym for SET PROTOCOL (q.v.).
 
SET TRANSFER REPORT { ON, OFF }
  Enables/Disables the automatic post-transfer message telling what files
  went where from C-Kermit when it is in remote mode.  ON by default.
 
SET TRANSFER SLOW-START { OFF, ON }
  ON (the default) tells Kermit, when sending files, to gradually build up
  the packet length to the maximum negotiated length.  OFF means start
  sending the maximum length right away.
 
Synonym: SET XFER.  Use SHOW TRANSFER (XFER) to see SET TRANSFER values.
```

Compile-time default, from `SHOW TRANSFER`:

```
 Transfer Bell: on
 Transfer Interruption: on
 Transfer Cancellation: on
 Transfer Translation:  on
 Transfer Character-set: Transparent
 Transfer CRC-calculation: off
 Transfer Display: fullscreen
 Transfer Message: (none)
 Transfer Locking-shift: enabled, not used
 Transfer Mode: manual
 Transfer Pipes: off
 Transfer Protocol: Kermit
 Transfer Report: on
 Transfer Slow-start: on
```

### SET XFER

Synonym for [SET TRANSFER](#set-transfer).

### SET TRANSMIT

Synonym: XMIT

```
Syntax: SET TRANSMIT parameter value
 
Controls the behavior of the TRANSMIT command (see HELP TRANSMIT):
 
SET TRANSMIT ECHO { ON, OFF }
  Whether to echo text to your screen as it is being transmitted.
 
SET TRANSMIT EOF text
  Text to send after end of file is reached, e.g. \4 for Ctrl-D
 
SET TRANSMIT FILL number
  ASCII value of a character to insert into blank lines, 0 for none.
  Applies only to text mode.  0 by default.
 
SET TRANSMIT LINEFEED { ON, OFF }
  Transmit Linefeed as well as Carriage Return (CR) at the end of each line.
  Normally, only CR  is sent.
 
SET TRANSMIT LOCKING-SHIFT { ON, OFF }
  Whether to use SO/SI for transmitting 8-bit data when PARITY is not NONE.
 
SET TRANSMIT PAUSE number
  How many milliseconds to pause after transmitting each line (text mode),
  or each character (binary mode).
 
SET TRANSMIT PROMPT number
  ASCII value of character to look for from host before sending next line
  when TRANSMITting in text mode; normally 10 (Linefeed).  0 means none;
  don't wait for a prompt.
 
SET TRANSMIT TIMEOUT number
  Number of seconds to wait for each character to echo when TRANSMIT ECHO
  is ON or TRANSMIT PROMPT is not 0.  If 0 is specified, this means wait
  indefinitely for each echo.
 
Synonym: SET XMIT.  SHOW TRANSMIT displays current settings.
```

Compile-time default, from `SHOW TRANSMIT`:

```
 File type:                       binary
 File character-set:              ascii
 Terminal character-set (remote): ascii
 Terminal character-set (local):  ascii
 Terminal bytesize:               8
 Terminal echo:                   remote
 Transmit EOF:                    (none)
 Transmit Fill:                   (none)
 Transmit Linefeed:               off
 Transmit Prompt:                 10 (LF)
 Transmit Echo:                   on
 Transmit Locking-Shift:          off
 Transmit Pause:                  0 (milliseconds)
 Transmit Timeout:                1 (second)
```

### SET XMIT

Synonym for [SET TRANSMIT](#set-transmit).

### SET UNKNOWN-CHAR-SET

```
Syntax: SET UNKNOWN-CHAR-SET action
  DISCARD (default) means reject any arriving files encoded in unknown
  character sets.  KEEP means to accept them anyway.
```

### SET VARIABLE-EVALUATION

```
Syntax: SET VARIABLE-EVALUATION { RECURSIVE, SIMPLE }
  Tells Kermit weather to evaluate \%x and \&x[] variables recursively
  In C-Kermit 10.0 the default is SIMPLE, meaning variables return their
  values like in any other programming language, making life much easier
  when those values happen to be Windows or DOS pathnames, which contain
  backslashes.
```

### SET WILDCARD-EXPANSION

```
Syntax: SET WILDCARD-EXPANSION { KERMIT [ switch ], SHELL, ON, OFF }
  KERMIT (the default) means C-Kermit expands filename wildcards in SEND and
  similar commands itself, and in incoming GET commands.  Optional switches
  are /NO-MATCH-DOT-FILES ("*" and "?" should not match an initial
  period in a filename; this is the default) and /MATCH-DOT-FILES if you
  want files whose names begin with "." included.  SET WILDCARD SHELL
  means that Kermit asks your preferred shell to expand wildcards (this
  should not be necessary in C-Kermit 7.0 and later).  HELP WILDCARD for
  further information.
 
  The ON and OFF choices allow you to disable and renable wildcard
  processing independent of the KERMIT / SHELL choice.  Disabling wildcards
  allows you to process an array or list of filenames without having to
  consider whether the names might contain literal wildcard characters.
  WARNING: SET WILD OFF also disables internal filename pattern-matching,
  used (for example) in creating backup files.
```

### SET WINDOW-SIZE

Synonyms: W, WI, WIN

```
Syntax: SET WINDOW-SIZE number
  Specifies number of slots for sliding windows, i.e. the number of packets
  that can be transmitted before waiting for acknowledgement.  The default
  is one, the maximum is 32.  Increased window size might result in reduced
  maximum packet length.  Use sliding windows for improved efficiency on
  connections with long delays.  A full duplex connection is required, as
  well as a cooperating Kermit on the other end.
```

### SET W

Synonym for [SET WINDOW-SIZE](#set-window-size).

### SET WI

Synonym for [SET WINDOW-SIZE](#set-window-size).

### SET WIN

Synonym for [SET WINDOW-SIZE](#set-window-size).

## REMOTE Subcommands

### REMOTE ASSIGN

Synonyms: AS, ASG

```
Syntax: REMOTE ASSIGN variable-name [ value ]
  Assigns the given value to the named global variable on the server.
  Synonyms: RASG, RASSIGN.
```

### REMOTE AS

Synonym for [REMOTE ASSIGN](#remote-assign).

### REMOTE ASG

Synonym for [REMOTE ASSIGN](#remote-assign).

### REMOTE CD

Synonym: CWD

```
Syntax: REMOTE CD [ name ]
  Asks the Kermit or FTP server to change its working directory or device.
  If the device or directory name is omitted, restore the default.
  Synonym: RCD.
```

### REMOTE CWD

Synonym for [REMOTE CD](#remote-cd).

### REMOTE CDUP

```
Syntax: REMOTE CDUP
  Asks the Kermit or FTP server to change its working directory to
  the directory above it.  Synonym: RCDUP.
```

### REMOTE COPY

```
Syntax: REMOTE COPY source destination
  Asks the Kermit server to copy the source file to destination.
  Synonym: RCOPY.
```

### REMOTE DELETE

Synonym: ERASE

```
Syntax: REMOTE DELETE filespec
  Asks the Kermit or FTP server to delete the named file(s).
  Synonym: RDEL.
```

### REMOTE ERASE

Synonym for [REMOTE DELETE](#remote-delete).

### REMOTE DIRECTORY

```
Syntax: REMOTE DIRECTORY [ filespec ]
  Asks the Kermit or FTP server to provide a directory listing of the named
  file(s) or if no file specification is given, of all files in its current
  directory.  Synonym: RDIR.
```

### REMOTE EXIT

Synonym: E

```
Syntax: REMOTE EXIT
   Asks the Kermit server to exit (without disconnecting), or closes an FTP
   connection.  Synonym: REXIT, and (for FTP only) BYE, FTP BYE.
```

### REMOTE E

Synonym for [REMOTE EXIT](#remote-exit).

### REMOTE HELP

```
Syntax: REMOTE HELP
  Asks the Kermit or FTP server to list the services it provides.
  Synonym: RHELP.
```

### REMOTE HOST

```
Syntax: REMOTE HOST command
  Sends a command to the other computer in its own command language
  through the Kermit server that is running on that host.  Synonym: RHOST.
```

### REMOTE KERMIT

```
Syntax: REMOTE KERMIT command
  Sends a command to the remote Kermit server in its own command language.
  Synonym: RKERMIT.
```

### REMOTE LOGIN

Synonyms: L, LO, LOG

```
Syntax: REMOTE LOGIN user password [ account ]
  Logs in to a remote Kermit server that requires you login.  Note: RLOGIN
  is NOT a synonym for REMOTE LOGIN.
```

### REMOTE L

Synonym for [REMOTE LOGIN](#remote-login).

### REMOTE LO

Synonym for [REMOTE LOGIN](#remote-login).

### REMOTE LOG

Synonym for [REMOTE LOGIN](#remote-login).

### REMOTE LOGOUT

```
Syntax: REMOTE LOGOUT
  Logs out from a remote Kermit server to which you have previously logged in.
```

### REMOTE MESSAGE

```
Syntax: REMOTE MESSAGE text
  Sends a short text message to the remote Kermit server.
```

### REMOTE MKDIR

```
Syntax: REMOTE MKDIR directory-name
  Asks the Kermit or FTP server to create the named directory.
  Synonym: RMKDIR.
```

### REMOTE PRINT

```
Syntax: REMOTE PRINT filespec [ options ]
  Sends the specified file(s) to the remote Kermit and ask it to have the
  file printed on the remote system's printer, using any specified options.
  Synonym: RPRINT.
```

### REMOTE PWD

```
Syntax: REMOTE PWD
  Asks the Kermit server to display its current working directory.
  Synonym: RPWD.
```

### REMOTE QUERY

```
Syntax: [ REMOTE ] QUERY { KERMIT, SYSTEM, USER } variable-name
  Asks the Kermit server to send the value of the named variable of the
  given type, and make it available in the \v(query) variable.  When the
  type is KERMIT functions may also be specified as if they were variables.
```

### REMOTE RENAME

```
Syntax: REMOTE RENAME filespec newname
  Asks the Kermit or FTP server to rename the file.  Synonym: RRENAME.
```

### REMOTE RMDIR

```
Syntax: REMOTE RMDIR directory-name
  Asks the Kermit or FTP server to remove the named directory.
  Synonym: RRMDIR.
```

### REMOTE SET

```
Syntax:  REMOTE SET parameter value
Example: REMOTE SET FILE TYPE BINARY
  Asks the Kermit server to set the named parameter to the given value.
  Equivalent to typing the corresponding SET command directly to the other
  Kermit if it were in interactive mode.
```

### REMOTE SPACE

```
Syntax: REMOTE SPACE [ name ]
  Asks the Kermit server to tell you about its disk space on the current
  disk or directory, or in the one that you name.  Synonym: RSPACE.
```

### REMOTE STATUS

```
Syntax: REMOTE STATUS
  Asks the remote Kermit server for information about itself.  Typically
  this would include the name and version of Kermit program,the underlying
  hardware/architecture, operating system, current directory, and the
  details of the most recent file transfer (if any).
```

### REMOTE TYPE

```
Syntax: REMOTE TYPE file
  Asks the Kermit or FTP server to send the named file to your screen.
  Synonym: RTYPE.
```

### REMOTE WHO

```
Syntax: REMOTE WHO [ name ]
  Asks the Kermit server to list who's logged in, or to give information
  about the named user.  Synonym: RWHO.
```

## FILE Subcommands

### FILE CLOSE

```
Syntax: FILE CLOSE <channel>
  Closes the file on the given channel if it was open.
  Also see HELP FILE OPEN.  Synonym: FCLOSE.
```

### FILE COUNT

```
Syntax: FILE COUNT [ { /BYTES, /LINES, /LIST, /NOLIST } ] <channel>
  If the channel is open, this command prints the nubmer of bytes (default)
  or lines in the file if at top level or if /LIST is included; if /NOLIST
  is given, the result is not printed.  In all cases the result is assigned
  to \v(f_count).  Synonym: FCOUNT
```

### FILE FLUSH

```
Syntax: FILE FLUSH <channel>
  Flushes output buffers on the given channel if it was open, forcing
  all material previously written to be committed to disk.  Synonym: FFLUSH.
  Also available as \F_flush().
```

### FILE LIST

```
Syntax: FILE LIST
  Lists the channel number, name, modes, and position of each file opened
  with FILE OPEN.  Synonym: FLIST.
```

### FILE OPEN

```
Syntax: FILE OPEN [ switches ] <variable> <filename>
  Opens the file indicated by <filename> in the mode indicated by the
  switches, if any, or if no switches are included, in read-only mode, and
  assigns a channel number for the file to the given variable.
  Synonym: FOPEN.  Switches:
 
/READ
  Open the file for reading.
 
/STDIN
  Tells Kermit to read from Standard Input.  In this case you don't specify
  a filename.
 
/STDOUT
  Tells Kermit to write to Standard Output.  In this case you don't specify
  a filename.
 
/STDERR
  Tells Kermit to write to Standard Error.  In this case you don't specify
  a filename.
 
/WRITE
  Open the file for writing.  If /READ was not also specified, this creates
  a new file.  If /READ was specified, the existing file is preserved, but
  writing is allowed.  In both cases, the read/write pointer is initially
  at the beginning of the file.
 
/APPEND
  If the file does not exist, create a new file and open it for writing.
  If the file exists, open it for writing, but with the write pointer
  positioned at the end.
 
/BINARY
  This option is ignored in UNIX.
 
Switches can be combined in an way that makes sense and is supported by the
underlying operating system.
```

### FILE READ

```
Syntax: FILE READ [ switches ] <channel> [ <variable> ]
  Reads data from the file on the given channel number into the <variable>,
  if one was given; if no variable was given, the result is printed on
  the screen.  The variable should be a macro name rather than a \%x
  variable or array element if you want backslash characters in the file to
  be taken literally.  Synonym: FREAD.  Switches:
 
/LINE
  Specifies that a line of text is to be read.  A line is defined according
  to the underlying operating system's text-file format.  For example, in
  UNIX a line is a sequence of characters up to and including a linefeed.
  The line terminator (if any) is removed before assigning the text to the
  variable.  If no switches are included with the FILE READ command, /LINE
  is assumed.
 
/SIZE:number
  Specifies that the given number of bytes (characters) is to be read.
  This gives a semblance of "record i/o" for files that do not necessarily
  contain lines.  The resulting block of characters is assigned to the
  variable without any editing.
 
/CHARACTER
  Equivalent to /SIZE:1.  If FILE READ /CHAR succeeds but the <variable> is
  empty, this indicates a NUL byte was read.
 
/TRIM
  Trims trailing whitespace from the right when used with /LINE.  Ignored
  if used with /CHAR or /SIZE.
 
/UNTABIFY
  Tells Kermit to convert tabs to spaces (assuming tabs set every 8 spaces)
  when used with /LINE.  Ignored if used with /CHAR or /SIZE.
 
Synonym: FREAD.
Also available as \F_getchar(), \F_getline(), \F_getblock().
```

### FILE REWIND

```
Syntax: FILE REWIND <channel>
  If the channel is open, moves the read/write pointer to the beginning of
  the file.  Equivalent to FILE SEEK <channel> 0.  Synonym: FREWIND.
  Also available as \F_rewind().
```

### FILE SEEK

```
Syntax: FILE SEEK [ switches ] <channel> { [{+,-}]<number>, EOF }
  Switches are /BYTE, /LINE, /RELATIVE, /ABSOLUTE, and /FIND:pattern.
  Moves the file pointer for this file to the given position in the
  file.  Subsequent FILE READs or WRITEs will take place at that position.
  If neither the /RELATIVE nor /ABSOLUTE switch is given, an unsigned
  <number> is absolute; a signed number is relative.  EOF means to move to
  the end of the file.  If a /FIND: switch is included, Kermit seeks to the
  specified spot (e.g. 0 for the beginning) and then begins searching line
  by line for the first line that matches the given pattern.  To start
  searching from the current file position specify a line number of +0.
  To start searching from the line after the current one, use +1 (etc).
  Synonym: FSEEK.
```

### FILE STATUS

```
Syntax: FILE STATUS <channel>
  If the channel is open, this command shows the name of the file, the
  switches it was opened with, and the current read/write position.
  Synonym: FSTATUS
```

### FILE WRITE

```
FILE WRITE [ switches ] <channel> <text>
  Writes the given text to the file on the given channel number.  The <text>
  can be literal text or a variable, or any combination.  If the text might
  contain leading or trailing spaces, it must be enclosed in braces if you
  want to preserve them.  Synonym: FWRITE.  Switches:
 
/LINE
  Specifies that an appropriate line terminator is to be added to the
  end of the <text>.  If no switches are included, /LINE is assumed.
 
/SIZE:number
  Specifies that the given number of bytes (characters) is to be written.
  If the given <text> is longer than the requested size, it is truncated;
  if is shorter, it is padded according /LPAD and /RPAD switches.  Synonym:
  /BLOCK.
 
/LPAD[:value]
  If /SIZE was given, but the <text> is shorter than the requested size,
  the text is padded on the left with sufficient copies of the character
  whose ASCII value is given to write the given length.  If no value is
  specified, 32 (the code for Space) is used.  The value can also be 0 to
  write the indicated number of NUL bytes.  If /SIZE was not given, this
  switch is ignored.
 
/RPAD[:value]
  Like LPAD, but pads on the right.
 
/STRING
  Specifies that the <text> is to be written as-is, with no terminator added.
 
/CHARACTER
  Specifies that one character should be written.  If the <text> is empty or
  not given, a NUL character is written; otherwise the first character of
  <text> is given.
 
Synonym FWRITE.
Also available as \F_putchar(), \F_putline(), \F_putblock().
```

## Functions

### FUNCTION _EOF

```
\f_eof(n1)
  n1 = channel number.
Returns number:
  1 if channel n1 at end of file, 0 otherwise.
```

### FUNCTION _ERRMSG

```
\f_errmsg([n1])
  n1 = numeric error code, \v(f_error) by default.
  Returns the associated error message string.
```

### FUNCTION _GETBLOCK

```
\f_getblock(n1,n2)
  n1 = channel number, n2 = size
  Reads a block of n2 characters from channel n1 and returns it.
```

### FUNCTION _GETCHAR

```
\f_getchar(n1)
  n1 = channel number.
  Reads a character from channel n1 and returns it.
```

### FUNCTION _GETLINE

```
\f_getline(n1)
  n1 = channel number.
  Reads a line from channel n1 and returns it.
```

### FUNCTION _HANDLE

```
\f_handle(n1)
  n1 = channel number.
Returns number:
  File descriptor of open file on channel n1.
```

### FUNCTION _LINE

```
\f_line(n1)
  n1 = channel number.
Returns number:
  Read/write pointer of channel n1 as line number.
```

### FUNCTION _POS

```
\f_pos(n1)
  n1 = channel number.
Returns number:
  Read/write pointer of channel n1 as byte number.
```

### FUNCTION _PUTBLOCK

```
\f_putblock(n1,s1)
  n1 = channel number, s1 = string
  Writes the string s1 to channel n1.
  Returns number:
  How many characters written if successful;
  Otherwise a negative error code.
```

### FUNCTION _PUTCHAR

```
\f_putchar(n1,c)
  n1 = channel number, c = character
  Writes a character to channel n1.
Returns number:
  1 if successful, otherwise a negative error code.
```

### FUNCTION _PUTLINE

```
\f_putline(n1,s1)
  n1 = channel number, s1 = string
  Writes the string s1 to channel n1 and adds a line terminator.
Returns number:
  How many characters written if successful;
  Otherwise a negative error code.
```

### FUNCTION _STATUS

```
\f_status(n1)
  n1 = channel number.
Returns number:
  Sum of open modes of channel n1: 1 = read; 2 = write; 4 = append, or:
  0 if not open.
```

### FUNCTION AACONVERT

```
\faaconvert(name,&a[,&b])
  name = name of associative array, &a and &b = names of regular arrays.
  Converts the given associative array into two regular arrays, &a and &b,
  containing the indices and values, respectively:
Returns number:
  How many elements were converted.
```

### FUNCTION ABSOLUTE

```
\fabsolute(n1)
  n1 = integer.
Returns integer:
  The absolute (unsigned) value of n1.
```

### FUNCTION ADDR2NAME

Synonym: ADDRTONAME

```
\faddr2name(s)
  s = numeric IP address.
Returns:
  Corresponding IP hostname if found, otherwise null.
```

### FUNCTION ADDRTONAME

Synonym for [FUNCTION ADDR2NAME](#function-addr2name).

### FUNCTION ARRAYLOOK

```
\farraylook(pattern,&a) - Lookup pattern in array.
  pattern = String or pattern
  &a = array designator, can include range specifier.
Returns number:
  The index of the first matching array element or -1 if none.
More info:
  HELP PATTERN for pattern syntax.
  HELP ARRAY for arrays.
```

### FUNCTION B64DECODE

```
\b64decode(s)
  s = string in Base-64 notation
  Returns the decoded string or an error code if s not valid.
```

### FUNCTION B64ENCODE

```
\b64encode(s)
  s = string containing no NUL bytes
  Returns Base-64 encoding of string.
```

### FUNCTION BASENAME

```
\fbasename(f1)
  f1 = filename, possibly wild.
Returns string:
  Filename f1 stripped of all device and directory information.
```

### FUNCTION BREAK

```
\fbreak(s1,s2,n1)
  s1 = string to look in.
  s2 = string of characters to look for.
  n1 = 1-based integer starting position, default = 1.
Returns string:
  s1 up to the first occurrence of any character also in s2,
  scanning from the left starting at position n1.
```

### FUNCTION CAPITALIZE

Synonyms: CA, CAP, CAPS

```
\fcapitalize(s1)
  s1 = string.
Returns string:
  s1 with its first letter converted to uppercase and the remaining
  letters to lowercase.
Synonym: \fcaps(s1)
```

### FUNCTION CA

Synonym for [FUNCTION CAPITALIZE](#function-capitalize).

### FUNCTION CAP

Synonym for [FUNCTION CAPITALIZE](#function-capitalize).

### FUNCTION CAPS

Synonym for [FUNCTION CAPITALIZE](#function-capitalize).

### FUNCTION CHARACTER

```
\fcharacter(n1)
  n1 = integer.
Returns character:
  The character whose numeric code is n1.
```

### FUNCTION CHECKSUM

```
\fchecksum(s1)
  s1 = string.
Returns integer:
  16-bit checksum of string s1.
```

### FUNCTION CMDSTACK

```
\fcmdstack(n1,n2)
  n1 = Command-stack level, 0 to \v(cmdlevel), default \v(cmdlevel).
  n2 = Function code, 0 or 1.
Returns:
  n2 = 0: name of object at stack level n1
  n2 = 1: type of object at stack level n1:
     0 = interactive prompt
     1 = command file
     2 = macro
```

### FUNCTION CMPDATES

```
\fcmpdates(d1,d2)
  d1 = free-format date and/or time (default = NOW).
  d2 = ditto.
Returns:
  0 if d1 is equal to d2;
  1 if d1 is later than d2;
 -1 if d1 is earlier than d2.
```

### FUNCTION CODE

```
\fcode(s1)
  c1 = character.
Returns integer:
  The numeric code of the first character in string s1, or 0 if s1 empty.
```

### FUNCTION COMMAND

```
\fcommand(s1)
  s1 = string
Returns string:
  Output of system command s1, if any, with final line terminator stripped.
```

### FUNCTION CONTENTS

```
\fcontents(v1)
  v1 = variable name such as \%a.
Returns string:
  Literal definition of variable v1, evaluated one level only.
```

### FUNCTION COUNT

```
\fcount(s1,s2,n1)
  s1 = string or character to look for.
  s2 = string to look in.
  n1 = optional 1-based starting position, default = 1.
Returns integer:
  Number of occurrences of s1 in s2, 0 or more.
```

### FUNCTION CRC16

```
\fcrc16(s1)
  s1 = string.
Returns integer:
  16-bit cyclic redundancy check of string s1.
```

### FUNCTION CVTCSET

```
\fcvtcset(s,cset1,cset2)
  s = string
    Returns string converted from character set cset1 to cset2, where cset1
    and cset2 are names of File Character-Sets ('set file char ?' for a list).
```

### FUNCTION CVTDATE

```
\fcvtdate([date-time][,n1]) - Date/time conversion.
  Converts date and/or time to standard format.
  If no date/time given, returns current date/time.
  [date-time], if given, is free-format date and/or time.
  HELP DATE for info about date-time formats.
Returns string:
  Standard-format date and time: yyyymmdd hh:mm:ss (numeric)
  If n1 is given:
  n1 = 1: yyyy-mmm-dd hh:mm:ss (mmm = English 3-letter month abbreviation)
  n1 = 2: dd-mmm-yyyy hh:mm:ss (ditto)
  n1 = 3: yyyymmddhhmmss (all numeric)
  n1 = 4: Day Mon dd hh:mm:ss yyyy (asctime)
  n1 = 5: yyyy:mm:dd:hh:mm:ss (all numeric with all fields delimited)
  n1 = 6: dd month-spelled-out yyyy hh:mm:ss
  Other:  yyyymmdd hh:mm:dd
  If n1 is negative (-1 to -6), the result is date only.
```

### FUNCTION DATE

```
\fdate(f1)
  f1 = filename.
Returns string:
  Modification date of file f1, format: yyyymmdd hh:mm:ss.
```

### FUNCTION DAY

```
\fday([[date][ time]]) - Day of Week.
Returns day of week of given date as Mon, Tue, etc.
HELP DATE for info about date-time formats.
Also see HELP FUNCTION DAYNAME.
```

### FUNCTION DAYNAME

```
\fdayname(s1,n)
  s1 = free-format date OR day-of-week number 1-7 OR leave blank.
  n  = function code: 0 to return full name; nonzero to return abbreviation.
  Returns a string: the name of the weekday for the given date or weekday
    number or, if s1 was omitted, of the current date, in the language and
    character-set specified by the locale.  If n is nonzero, the result
    is abbreviated in the locale-appropriate way.  If given inappropriate
    arguments, the result is empty and an error message is printed.
```

### FUNCTION DAYOFYEAR

Synonyms: DOY, JDATE

```
\fdoy([date-time]) - Day of Year.
  Converts date and/or time to day-of-year (DOY) format.
  If no date/time given, returns current date.
  [date-time], if given, is free-format date and/or time.
  HELP DATE for info about date-time formats.
Returns numeric string:
  DOY: yyyyddd, where ddd is 1-based day number in year.
```

### FUNCTION DOY

Synonym for [FUNCTION DAYOFYEAR](#function-dayofyear).

### FUNCTION JDATE

Synonym for [FUNCTION DAYOFYEAR](#function-dayofyear).

### FUNCTION DECODEHEX

```
\fdecodehex(s1[,s2])
  s1, s2 = strings
    Decodes a string s1 that contains prefixed hex bytes.  s2 is the prefix;
    the default is %%.  You can specify any other prefix one or two bytes
    long.  If the prefix contains letters (such as 0x), case is ingored.
    Returns string s1 with hex escapes replaced by the bytes they represent.
```

### FUNCTION DEFINITION

```
\fdefinition(m1)
  m1 = macro name.
Returns string:
  Literal definition of macro m1.
```

### FUNCTION DELTA2SECS

Synonym: DELTATOSECS

```
\fdelta2secs(dt)
  dt = Delta time, e.g. +3d14:27:52.
Returns:
  The corresponding number of seconds.
```

### FUNCTION DELTATOSECS

Synonym for [FUNCTION DELTA2SECS](#function-delta2secs).

### FUNCTION DIALCONVERT

```
\fdialconvert(phone-number) - Convert phone number.
  Converts the given phone number for dialing according
  to the prevailing dialing rules -- country code, area code, etc.
Returns string:
  The dial string that would be used if the same phone number had been
  given to the DIAL command.
```

### FUNCTION DIFFDATES

```
\fdiffdates(d1,d2)
  d1 = free-format date and/or time (default = NOW).
  d2 = ditto.
Returns:
  Difference expressed as delta time:
  Negative if d2 is later than d1, otherwise positive.
```

### FUNCTION DIMENSION

```
Sorry, help not available for "help function dimension"
```

### FUNCTION DIRECTORIES

Synonyms: DIR, DIRE, DIREC, DIRECT, DIRECTO, DIRECTOR, DIRECTORY

```
\fdirectories(f1,&a) - Directory list.
  f1 = directory specification, possibly containing wildcards.
  &a = optional name of array to assign directory list to.
Returns integer:
  The number of directories that match f1; use with \fnextfile().
```

### FUNCTION DIR

Synonym for [FUNCTION DIRECTORIES](#function-directories).

### FUNCTION DIRE

Synonym for [FUNCTION DIRECTORIES](#function-directories).

### FUNCTION DIREC

Synonym for [FUNCTION DIRECTORIES](#function-directories).

### FUNCTION DIRECT

Synonym for [FUNCTION DIRECTORIES](#function-directories).

### FUNCTION DIRECTO

Synonym for [FUNCTION DIRECTORIES](#function-directories).

### FUNCTION DIRECTOR

Synonym for [FUNCTION DIRECTORIES](#function-directories).

### FUNCTION DIRECTORY

Synonym for [FUNCTION DIRECTORIES](#function-directories).

### FUNCTION DIRNAME

```
\fdirname(f) - Directory part of a filename.
  f = a file specification.
Returns directory name:
  The full name of the directory that the file is in, or if the file is a
  directory, its full name.
```

### FUNCTION DOSTOUNIXPATH

Synonym: DOS2UNIXPATH

```
\fdos2unixpath(p)
  p = string, DOS pathname.
Returns:
  The argument converted to a Unix pathname.
```

### FUNCTION DOS2UNIXPATH

Synonym for [FUNCTION DOSTOUNIXPATH](#function-dostounixpath).

### FUNCTION DOY2DATE

Synonym: DOYTODATE

```
\fdoy2date([doy[ time]]) - Day of Year to Date.
  Converts yyyymmm to yyyymmdd
  If time included, it is converted to 24-hour format.Returns standard date or date-time string yyyymmdd hh:mm:ss
```

### FUNCTION DOYTODATE

Synonym for [FUNCTION DOY2DATE](#function-doy2date).

### FUNCTION EMAILADDRESS

```
\femailaddress(s)
  s = From: or Sender: header from an RFC2822-format email message
    Extracts and returns the email address.
```

### FUNCTION ERRSTRING

```
\ferrstring(n)
  n = platform-dependent numeric error code.
Returns:
  The corresponding error string.
```

### FUNCTION EVALUATE

```
\fevaluate(e)
  e = arithmetic expression in ordinary algebraic notation.
Returns integer:
  The result of evaluating the expression.
```

### FUNCTION EXECUTE

```
\fexecute(m1,a1,a2,a3,...)
  m1 = macro name.
  a1 = argument 1.
  a2 = argument 2, etc
Returns string:
  The return value of the macro (HELP RETURN for further info).
```

### FUNCTION FILECOMPARE

```
\ffilecompare(s1,s2)
  s1 = name of first file
  s1 = name of second file
  Returns a number:
     0: The two files have identical contents and lengths;
     1: The two files have different content or lengths;
    -1: Error opening or reading either file.
```

### FUNCTION FILEINFO

```
\ffileinfo(s1,&a)
  s1 = file specification string
  &a = array designator for results (required)
  Returns a number:
     0: File not found or not accessible or bad arguments;
    >0: The number of attributes returned in the array, normally 7, 8, or 9
 1. The file's name
 2. The full path of the directory where the file resides
 3. The file's modification date-time yyyymmdd hh:mm:ss
 4. Platform-specific permissions string, e.g. drwxrwxr-x or RWED,RWE,RE,E
 5. Platform-specific permissions code, e.g. an octal number like 40775
 6. The file's size in bytes
 7. Type: regular file, executable, directory, link, or unknown
 8. If link, the name of the file linked to
 9. Transfer mode for file: text or binary.
```

### FUNCTION FILES

```
\ffiles(f1[,&a]) - File list.
  f1 = file specification, possibly containing wildcards.
  &a = optional name of array to assign file list to.
Returns integer:
  The number of regular files that match f1.  Use with \fnextfile().
```

### FUNCTION FPABSOLUTE

```
\ffpabsolute(f1,d)
  f1 = floating-point number or integer.
   d = integer.
Returns floating-point number:
  The absolute (unsigned) value of f1 to d decimal places.
```

### FUNCTION FPADD

```
\ffpadd(f1,f2,d)
  f1,f2 = floating-point numbers or integers.
      d = integer.
Returns floating-point number:
  The sum of f1 and f2 to d decimal places.
```

### FUNCTION FPCOSINE

```
\ffpcosine(f1,d)
  f1 = floating-point number or integer.
   d = integer.
Returns floating-point number:
  The cosine of angle f1 (in radians) to d decimal places.
```

### FUNCTION FPDIVIDE

```
\ffpdivide(f1,f2,d)
  f1,f2 = floating-point numbers or integers.
      d = integer.
Returns floating-point number:
  f1 divided by f2 to d decimal places.
```

### FUNCTION FPEXP

```
\ffpexp(f1,d)
  f1 = floating-point number or integer.
   d = integer.
Returns floating-point number:
  e (the base of natural logarithms) raised to the f1 power,
  to d decimal places.
```

### FUNCTION FPINT

```
\ffpint(f1)
  f1 = floating-point number or integer.
Returns integer:
  The integer part of f1.
```

### FUNCTION FPLOG10

```
\ffplog10(f1,d)
  f1 = floating-point number or integer.
   d = integer.
Returns floating-point number:
  The logarithm, base 10, of f1 to d decimal places.
```

### FUNCTION FPLOGN

```
\ffplogn(f1,d)
  f1 = floating-point number or integer.
   d = integer.
Returns floating-point number:
  The natural logarithm of f1 to d decimal places.
```

### FUNCTION FPMAXIMUM

```
\ffpmaximum(f1,f2,d)
  f1,f2 = floating-point numbers or integers.
      d = integer.
Returns floating-point number:
  The maximum of f1 and f2 to d decimal places.
```

### FUNCTION FPMINIMUM

```
\ffpminimum(f1,f2,d)
  f1,f2 = floating-point numbers or integers.
      d = integer.
Returns floating-point number:
  The minimum of f1 and f2 to d decimal places.
```

### FUNCTION FPMODULUS

```
\ffpmodulus(f1,f2,d)
  f1,f2 = floating-point numbers or integers.
      d = integer.
Returns floating-point number:
  The modulus of f1 and f2 to d decimal places.
```

### FUNCTION FPMULTIPLY

```
\ffpmultiply(f1,f2,d)
  f1,f2 = floating-point numbers or integers.
      d = integer.
Returns floating-point number:
  The product of f1 and f2 to d decimal places.
```

### FUNCTION FPRAISE

```
\ffpraise(f1,f2,d)
  f1,f2 = floating-point numbers or integers.
      d = integer.
Returns floating-point number:
  f1 raised to the power f2, to d decimal places.
```

### FUNCTION FPROUND

```
\ffpround(f1,d)
  f1 = floating-point number or integer.
   d = integer.
Returns floating-point number:
  f1 rounded to d decimal places.
```

### FUNCTION FPSINE

```
\ffpsine(f1,d)
  f1 = floating-point number or integer.
   d = integer.
Returns floating-point number:
  The sine of angle f1 (in radians) to d decimal places.
```

### FUNCTION FPSQRT

```
\ffpsqrt(f1,d)
  f1 = floating-point number or integer.
   d = integer.
Returns floating-point number:
  The square root of f1 to d decimal places.
```

### FUNCTION FPSUBTRACT

```
\ffpsubtract(f1,f2,d)
  f1,f2 = floating-point numbers or integers.
      d = integer.
Returns floating-point number:
  f1 minus f2 to d decimal places.
```

### FUNCTION FPTANGENT

```
\ffptangent(f1,d)
  f1 = floating-point number or integer.
   d = integer.
Returns floating-point number:
  The tangent of angle f1 (in radians) to d decimal places.
```

### FUNCTION FUNCTION

```
\ffunction(s1)
 s1 = name of function.
Returns integer:
  1 if s1 is the name of an available built-in function;
  0 otherwise.
```

### FUNCTION PIDINFO

Synonym: GETPIDINFO

```
\fgetpidinfo(n1)
 n1 = Numeric process ID
Returns integer:
 -1 on failure to get information;
  1 if n1 is the ID of an active process;
  0 if the process does not exist.
```

### FUNCTION GETPIDINFO

Synonym for [FUNCTION PIDINFO](#function-pidinfo).

### FUNCTION HEX2IP

Synonym: HEXTOIP

```
\fhex2ip(s)
  s = 8-digit hexadecimal number
  Returns the equivalent decimal dotted IP address.
```

### FUNCTION HEXTOIP

Synonym for [FUNCTION HEX2IP](#function-hex2ip).

### FUNCTION HEX2N

```
\fhex2n(s)
  s = hexadecimal number
  Returns decimal equivalent.
```

### FUNCTION HEXIFY

```
\fhexify(s1)
  s1 = string.
Returns string:
  The hexadecimal representation of s1.  Also see \fn2hex().
```

### FUNCTION INDEX

```
\findex(s1,s2,n1,n2)
  s1 = string to look for.
  s2 = string to look in.
  n1 = optional 1-based starting position, default = 1.
  n2 = optional desired occurrence number, default = 1.
Returns integer:
  1-based position of leftmost occurrence of s1 in s2, ignoring the leftmost
  (n1-1) characters in s2; returns 0 if s1 not found in s2.
```

### FUNCTION IP2HEX

Synonym: IPTOHEX

```
\fip2hex(s)
  s = decimal dotted IP address
  Returns the equivalent 8-digit hexadecimal number.
```

### FUNCTION IPTOHEX

Synonym for [FUNCTION IP2HEX](#function-ip2hex).

### FUNCTION IPADDRESS

```
\fipaddress(s1,n1)
  s1 = string.
  n1 = 1-based integer starting position, default = 1.
Returns string:
  First IP address in s1, scanning from left starting at position n1.
```

### FUNCTION JOIN

```
\fjoin(&a[,s[,n1[,n2]]])
  &a = array designator, can include range specifier.
  s  = optional separator.
  n1 = nonzero to put grouping around elements that contain spaces;
       see \fword() grouping mask for values of n.
  n2 = 0 or omitted to put spaces between elements; nonzero to omit them.
  Returns the (selected) elements of the array joined to together,
  separated by the separator.

  If s is CSV (literally), that means the array is to be transformed into a
  comma-separated list.  No other arguments are needed.  If s is TSV, then
  a tab-separated list is created.
```

### FUNCTION KEYWORDVALUE

Synonym: KWVALUE

```
\fkeywordvalue(s1[,s2])
  s1 = string of the form "name=value"
  s2 = one more separator characters (default separator is "=")
    Assigns the value, if any, to the named macro and sets
    the \v(lastkeywordvalue) to the macro name.
    If no value is given, the macro is undefined.
Returns:
 -1 on error
  0 if no keyword or value were found
  1 if a keyword was found but no value
  2 if a keyword and a value were found
Synonym: \kwvalue(s1[,s2])
```

### FUNCTION KWVALUE

Synonym for [FUNCTION KEYWORDVALUE](#function-keywordvalue).

### FUNCTION LEFT

```
\fleft(s1,n1)
  s1 = string.
  n1 = integer, default = length(s1).
Returns string:
  The leftmost n1 characters of string s1.
```

### FUNCTION LENGTH

```
\flength(s1)
  s1 = string.
Returns integer:
  Length of string s1.
```

### FUNCTION LITERAL

```
\fliteral(s1)
  s1 = string.
Returns string:
  s1 literally without evaluation.
```

### FUNCTION LONGPATHNAME

```
\fpathname(f1)
  f1 = filename, possibly wild.
Returns string:
  Full pathname of f1.
```

### FUNCTION PATHNAME

Synonyms: LONGPATHNAME, SHORTPATHNAME

```
\fpathname(f1)
  f1 = filename, possibly wild.
Returns string:
  Full pathname of f1.
```

### FUNCTION LONGPATHNAME

Synonym for [FUNCTION PATHNAME](#function-pathname).

### FUNCTION SHORTPATHNAME

Synonym for [FUNCTION PATHNAME](#function-pathname).

### FUNCTION LOP

```
\flop(s1[,c1[,n1]])
  s1 = string to look in.
  c1 = character to look for, default = ".".
  n1 = occurrence of c1, default = 1.
Returns string:
  The part of s1 after the n1th leftmost occurrence of character c1.
```

### FUNCTION LOPX

```
\flopx(s1,c1)
  s1 = string to look in.
  c1 = character to look for, default = ".".
  n1 = occurrence of c1, default = 1.
Returns string:
  The part of s1 after the n1th rightmost occurrence of character c1.
```

### FUNCTION LOWER

```
\flower(s1)
  s1 = string.
Returns string:
  s1 with uppercase letters converted to lowercase.
```

### FUNCTION LPAD

```
\flpad(s1,n1,c1)
  s1 = string.
  n1 = integer.
  c1 = character, default = space.
Returns string:
  s1 left-padded with character c1 to length n1.
```

### FUNCTION LTRIM

```
\fltrim(s1,s2)
  s1 = string to look in.
  s2 = string of characters to look for, default = blanks and tabs.
Returns string:
  s1 with all characters that are also in s2 trimmed from the left.
.
```

### FUNCTION MAXIMUM

```
\fmaximum(n1,n2)
  n1 = integer.
  n2 = integer.
Returns integer:
  The greater of n1 and n2.
```

### FUNCTION MINIMUM

```
\fminimum(n1,n2)
  n1 = integer.
  n2 = integer.
Returns integer:
  The lesser of n1 and n2.
```

### FUNCTION MJD

```
\fmjd([[date][ time]]) - Modified Julian Date (MJD).
  Converts date and/or time to MJD, the number of days since 17 Nov 1858.
  HELP DATE for info about date-time formats.
Returns: integer.
```

### FUNCTION MJDTODATE

Synonym: MJD2DATE

```
\fmjd2date(mjd) - Modified Julian Date (MJD) to Date.
  Converts MJD to standard-format date.
Returns: yyyymmdd.
```

### FUNCTION MJD2DATE

Synonym for [FUNCTION MJDTODATE](#function-mjdtodate).

### FUNCTION MODULUS

```
\fmodulus(n1,n2)
  n1 = integer.
  n2 = integer.
Returns integer:
  The remainder after dividing n1 by n2.
```

### FUNCTION MONTHNAME

```
\fmonthname(s1,n)
  s1 = free-format date OR month-of-year number 1-12 OR leave blank.
  n  = function code: 0 to return full name; nonzero to return abbreviation.
  Returns a string: the name of the month for the given date or month
    number or, if s1 was omitted, of the current date, in the language and
    character-set specified by the locale.  If n is nonzero, the result
    is abbreviated in the locale-appropriate way.  If given inappropriate
    arguments, the result is empty and an error message is printed.
```

### FUNCTION N2HEX

Synonym: NTOHEX

```
\fn2hex(n1) - Number to hex
  n1 = integer.
Returns string:
  The hexadecimal representation of n1.
```

### FUNCTION NTOHEX

Synonym for [FUNCTION N2HEX](#function-n2hex).

### FUNCTION N2OCTAL

Synonym: NTOOCTAL

```
\fn2octal(n1) - Number to octal
  n1 = integer.
Returns string:
  The octal representation of n1.
```

### FUNCTION NTOOCTAL

Synonym for [FUNCTION N2OCTAL](#function-n2octal).

### FUNCTION N2TIME

Synonym: NTOTIME

```
\fn2time(seconds) - Numeric Time to Time.
Returns the given number of seconds in hh:mm:ss format.
```

### FUNCTION NTOTIME

Synonym for [FUNCTION N2TIME](#function-n2time).

### FUNCTION NAME2ADDR

```
\fname2addr(s)
  s = IP host name.
Returns:
  Corresponding numeric IP address if found, else null.
```

### FUNCTION NDAY

```
\fnday([[date][ time]]) - Numeric Day of Week.
Returns numeric day of week of given date, 0=Sun, 1=Mon, ..., 6=Sat.
HELP DATE for info about date-time formats.
```

### FUNCTION NEXTFILE

```
\fnextfile()
Returns string:
  Name of next file from list created by most recent \f[r]files() or
  \f[r]dir()invocation, or an empty string if there are no more files in
  the list.
```

### FUNCTION NTIME

Synonyms: TOD2SECS, TODTOSECS

```
\fntime([[date][ time]]) - Numeric Time.
Returns time portion of given date and/or time as seconds since midnight.
If no argument given, returns current time.
HELP DATE for info about date-time formats.
```

### FUNCTION TOD2SECS

Synonym for [FUNCTION NTIME](#function-ntime).

### FUNCTION TODTOSECS

Synonym for [FUNCTION NTIME](#function-ntime).

### FUNCTION OCT2N

Synonym: OCTTON

```
\foct2n(s)
  s = octal number
  Returns decimal equivalent.
```

### FUNCTION OCTTON

Synonym for [FUNCTION OCT2N](#function-oct2n).

### FUNCTION PATTERN

```
\fpattern(s)
  s = string
  Returns string: s with any variables, etc, evaluated in the normal manner.
  For use with INPUT, MINPUT, and REINPUT to declare that a search target is
  a pattern rather than a literal string.
```

### FUNCTION PERMISSIONS

```
\fpermissions(file) - Permissions of File.
Returns permissions of given file as they would be shown by "ls -l".
```

### FUNCTION PICTUREINFO

```
\fpictureinfo(s[,&a])
  s  = File specification of an image file in JPG or GIF format.
  &a = Optional array name.

Returns integer:
  0 if file not found or not recognized;
  1 if orientation is landscape;
  2 if orientation is portrait;
  3 if the image is square.

If an array name is included, and if the function's return value is
greater than 0, element 1 of the array is filled in with the image
width in pixels, element 2 the image height, and element 3 is the image's
'date taken' (if present) in 'yyyy:mm:dd hh:mm:ss' format; for example
2013:05:17 21:14:12.
```

### FUNCTION RADIX

```
\fradix(s,n1,n2)
  s = number in radix n1
  Returns the number's representation in radix n2.
```

### FUNCTION RANDOM

```
\frandom(n) - Random number.
  n = a positive integer.
Returns integer:
  A random number between 0 and n-1.
```

### FUNCTION RAWCOMMAND

```
\frawcommand(s1)
  s1 = string
Returns string:
  Output of system command s1, if any.
```

### FUNCTION RDIRECTORIES

```
\frdirectories(f1) - Recursive directory list.
  f1 = directory specification, possibly containing wildcards.
  &a = optional name of array to assign directory list to.
Returns integer:
  The number of directories that match f1 in the current or given directory
  tree.  Use with \fnextfile().
```

### FUNCTION RECURSE

```
\frecurse(s1)
 s1 = name of \&x or \&x[] type variable
Returns the result of evaluating the variable recursively.
```

### FUNCTION RFILES

```
\frfiles(f1[,&a]) - Recursive file list.
  f1 = file specification, possibly containing wildcards.
  &a = optional name of array to assign file list to.
Returns integer:
  The number of files whose names match f1 in the current or given
  directory tree; use with \fnextfile().
```

### FUNCTION REPEAT

Synonym: REP

```
\frepeat(s1,n1)
  s1 = string.
  n1 = integer.
Returns string:
  s1 repeated n1 times.
```

### FUNCTION REP

Synonym for [FUNCTION REPEAT](#function-repeat).

### FUNCTION REPLACE

```
\freplace(s1,s2,[s3[,n1[,n2]]])
  s1 = original string.
  s2 = match string.
  s3 = replacement string (may be empty).
  n1 = occurrence (if omitted or 0 does all occurrences).
  n2 = word mode (0 = ignore context; 1 = only if target is delimited).
Returns string:
  s1 with occurrence number n1 of s2 replaced by s3.
  If n1 = 0 or omitted, all occurrences are replaced.
  If n1 < 0, occurrences are counted from the right.
```

### FUNCTION REVERSE

```
\freverse(s1)
  s1 = string.
Returns string:
  s1 with its characters in reverse order.
```

### FUNCTION RIGHT

```
\fright(s1,n1)
  s1 = string.
  n1 = integer, default = length(s1).
Returns string:
  The rightmost n1 characters of string s1.
```

### FUNCTION RINDEX

```
\frindex(s1,s2,n1,n2)
  s1 = string to look for.
  s2 = string to look in.
  n1 = optional 1-based starting position, default = 1.
  n2 = optional desired occurrence number, default = 1.
Returns integer:
  1-based position of rightmost occurrence of s1 in s2, ignoring the rightmost
  (n1-1) characters in s2; returns 0 if s1 not found in s2.
```

### FUNCTION RPAD

```
\frpad(s1,n1,c1)
  s1 = string.
  n1 = integer.
  c1 = character, default = space.
Returns string:
  s1 right-padded with character c1 to length n1.
```

### FUNCTION RSEARCH

```
\frsearch(s1,s2,n1,n2)
  s1 = pattern to look for.
  s2 = string to look in.
  n1 = optional 1-based offset, default = 1.
  n2 = optional desired occurrence of match, default = 1.
Returns integer:
  1-based position of rightmost match for s1 in s2, ignoring the rightmost
  (n1-1) characters in s2; returns 0 if no match.
  s1 is a "floating pattern"; see HELP PATTERNS for details.
```

### FUNCTION SEARCH

```
\fsearch(s1,s2,n1,n2)
  s1 = pattern to look for.
  s2 = string to look in.
  n1 = optional 1-based offset, default = 1.
  n2 = optional desired occurrence of match, default = 1.
Returns integer:
  1-based position of leftmost match for s1 in s2, ignoring the leftmost
  (n1-1) characters in s2; returns 0 if no match.
  s1 is a "floating pattern"; see HELP PATTERNS for details.
```

### FUNCTION SEXPRESSION

```
\fsexpression(s1)
  s1 = S-Expression.
  Returns: The result of evaluating s1.
```

### FUNCTION SHORTPATHNAME

```
\fpathname(f1)
  f1 = filename, possibly wild.
Returns string:
  Full pathname of f1.
```

### FUNCTION SIZE

```
\fsize(f1)
  f1 = filename.
Returns integer:
  Size of file f1.
```

### FUNCTION SPAN

```
\fspan(s1,s2,n1)
  s1 = string to look in.
  s2 = string of characters to look for.
  n1 = 1-based integer starting position, default = 1.
Returns string:
  s1 up to the first occurrence of any character not also in s2,
  scanning from the left starting at position n1.
```

### FUNCTION SPLIT

```
Function \fsplit(s1,&a,s2,s3,n2,n3) - Assigns string words to an array.
  s1 = source string.
  &a = array designator.
  s2 = optional break set.
  s3 = optional include set (or ALL, CSV, or TSV).
  n2 = optional grouping mask.
  n3 = optional separator flag:
   0 = collapse adjacent separators;
   1 = don't collapse adjacent separators.
 
  \fsplit() breaks the string s1 into "words" as indicated by the other
  parameters, assigning them to given array, if any.  If the specified
  already exists, it is recycled; if no array is specified, the count is
  returned but no array is created.  All arguments are optional
  (\fsplit() with no arguments returns 0).
 
  The BREAK SET is the set of all characters that separate words. The
  default break set is all characters except ASCII letters and digits.
  ASCII (C0) control characters are treated as break characters by default,
  as are spacing and punctuation characters, brackets, and so on, and
  all 8-bit characters.
 
  The INCLUDE SET is the set of characters that are to be treated as 
  parts of words even though they normally would be separators.  The
  default include set is empty.  Three special symbolic include sets are
  also allowed:
 
    ALL (meaning include all bytes that are not in the break set)
    CSV (special treatment for Comma-Separated-Value records)
    TSV (special treatment for Tab-Separated-Value records)
 
  For operating on 8-bit character sets, the include set should be ALL.
 
  If the grouping mask is given and is nonzero, words can be grouped by
  quotes or brackets selected by the sum of the following:
 
     1 = doublequotes:    "a b c"
     2 = braces:          {a b c}
     4 = apostrophes:     'a b c'
     8 = parentheses:     (a b c)
    16 = square brackets: [a b c]
    32 = angle brackets:  <a b c>
 
  Nesting is possible with {}()[]<> but not with quotes or apostrophes.
 
Returns integer:
  Number of words in source string.
 
Also see:
  HELP FUNCTION WORD
```

### FUNCTION SQUEEZE

```
\fsqueeze(s)
  s = string
    Returns string with leading and trailing whitespace removed, Tabs
    converted to Spaces, and multiple spaces converted to single spaces.
```

### FUNCTION STRCMP

```
\fstrcmp(s1,s2[,case[,start[,length]]])
  s1, s2 = strings
  case, start, length = numbers or arithmetic expressions.
    case = 0 [default] means to do a case-independent comparison;
    nonzero case requests a case-sensitive comparison.
    The optional start and length arguments apply to both s1 and s2
    and allow specification of substrings if it is not desired to compare
    the whole strings.  Results for non-ASCII strings are implentation-
    and locale-dependent.
  Returns a number:
    -1: s1 is lexically less than s2;
     0: s1 and s2 are lexically equal;
     2: s1 is lexically greater than s2.
```

### FUNCTION STRINGTYPE

```
\fstringtype(s)
  s = string
    Returns a string representing the type of its string argument s1:
    7BIT, 8BIT, UTF8, TEXT, or BINARY.  TEXT means some kind of text
    other than 7BIT, 8BIT, or UTF8 (this probably will never appear).
```

### FUNCTION STRIPB

```
\fstripb(s1[,c1[,c2]])
  s1 = original string.
  c1 = optional first character
  c2 = optional final character.
Returns string:
  s1 with the indicated enclosing characters removed.  If c1 and c2 not
     specified, any matching brackets, braces, parentheses, or quotes are
     assumed.  If c1 is given but not c2, the appropriate c2 is assumed.
     if both c1 and c2 are given, they are used as-is.
Alternative format:
  Include a grouping mask number in place of c1 and omit c2 to specify more
  than one possibility at once; see \fword() for details.
```

### FUNCTION STRIPN

```
\fstripn(s1,n1)
  s1 = string to look in.
  n1 = integer, default = 0.
Returns string:
  s1 with n1 characters removed from the right.
```

### FUNCTION STRIPX

```
\fstripx(s1,c1)
  s1 = string to look in.
  c1 = character to look for, default = ".".
Returns string:
  s1 up to the rightmost occurrence of character c1.
```

### FUNCTION SUBSTRING

Synonyms: SU, SUB, SUBS, SUBST

```
\fsubstring(s1,n1,n2)
  s1 = string.
  n1 = integer, 1-based starting position, default = 1.
  n2 = integer, length, default = length(s1) - n1 + 1.
Returns string:
  Substring of s1 starting at n1, length n2.
```

### FUNCTION SU

Synonym for [FUNCTION SUBSTRING](#function-substring).

### FUNCTION SUB

Synonym for [FUNCTION SUBSTRING](#function-substring).

### FUNCTION SUBS

Synonym for [FUNCTION SUBSTRING](#function-substring).

### FUNCTION SUBST

Synonym for [FUNCTION SUBSTRING](#function-substring).

### FUNCTION SUBSTITUTE

```
\fsubstitute(s1,s2,s3)
  s1 = Source string.
  s2 = List of characters to be translated.
  s3 = List of characters to translate them to.
  Returns: s1, with each character that is in s2 replaced by the
  corresponding character in s3.  s2 and s3 can contain ASCII ranges,
  like [a-z].  Any characters in s2 that don't have corresponding
  characters in s3 (after range expansion) are removed from the result.
  This function works only with single-byte character-sets
```

### FUNCTION TABLELOOK

```
\ftablelook(keyword,&a,[c]) - Lookup keyword in keyword table.
  keyword = keyword to look up (can be abbreviated).
  &a      = array designator, can include range specifier.
            This array must be in alphabetical order.
  c       = Optional field delimiter, colon(:) by default.
Returns number:
  1 or greater, index of array element that uniquely matches given keyword;
or -2 if keyword was ambiguous, or -1 if keyword empty or not found.
Also see:
  HELP FUNC ARRAYLOOK for a similar function.
  HELP ARRAY for arrays.
```

### FUNCTION TIME

```
\ftime([[date][ time]]) - Time.
Returns time portion of given date and/or time in hh:mm:ss format.
If no argument given, returns current time.
HELP DATE for info about date-time formats.
```

### FUNCTION TRIM

```
\ftrim(s1,s2)
  s1 = string to look in.
  s2 = string of characters to look for, default = blanks and tabs.
Returns string:
  s1 with all characters that are also in s2 trimmed from the right.
.
```

### FUNCTION UNHEXIFY

```
\funhexify(h1)
  h1 = Hexadecimal string.
Returns string:
  The result of unhexifying s1, or nothing if s1 is not a hex string.
```

### FUNCTION UNIXTODOSPATH

Synonym: UNIX2DOSPATH

```
\funix2dospath(p)
  p = string, Unix pathname.
Returns:
  The argument converted to a DOS pathname.
```

### FUNCTION UNIX2DOSPATH

Synonym for [FUNCTION UNIXTODOSPATH](#function-unixtodospath).

### FUNCTION UNTABIFY

```
\funtabify(s1)
  s1 = string.
Returns string:
  The result of converting tabs in s1 to spaces assuming tab stops every
  8 spaces.
```

### FUNCTION UPPER

```
\fupper(s1)
  s1 = string.
Returns string:
  s1 with lowercase letters converted to uppercase.
```

### FUNCTION UTCDATE

```
\futcdate(d1)
  d1 = free-format date and/or time (default = NOW).
Returns:
  Date-time converted to UTC (GMT) yyyymmdd hh:mm:ss.
```

### FUNCTION VERIFY

```
\fverify(s1,s2,n1)
  s1 = string of characters to look for.
  s2 = string to look in.
  n1 = starting position in s2.
Returns integer:
  1-based position of first character in s2 that is not also in s1,
  or -1 if s1 is empty, or 0 if all characters in s2 are also in s1.
```

### FUNCTION WORD

```
Function \fword(s1,n1,s2,s3,n2,n3) - Extracts a word from a string.
    s1 = source string.
    n1 = word number (1-based) counting from left; if negative, from right.
    s2 = optional break set.
    s3 = optional include set (or ALL, CSV, or TSV).
    n2 = optional grouping mask.
    n3 = optional separator flag:
       0 = collapse adjacent separators;
       1 = don't collapse adjacent separators.
 
  \fword() returns the n1th "word" of the string s1, according to the
  criteria specified by the other parameters.
 
  The BREAK SET is the set of all characters that separate words. The
  default break set is all characters except ASCII letters and digits.
  ASCII (C0) control characters are treated as break characters by default,
  as are spacing and punctuation characters, brackets, and so on, and
  all 8-bit characters.
 
  The INCLUDE SET is the set of characters that are to be treated as 
  parts of words even though they normally would be separators.  The
  default include set is empty.  Three special symbolic include sets are
  also allowed:
   
    ALL (meaning include all bytes that are not in the break set)
    CSV (special treatment for Comma-Separated-Value records)
    TSV (special treatment for Tab-Separated-Value records)
 
  For operating on 8-bit character sets, the include set should be ALL.
 
  If the GROUPING MASK is given and is nonzero, words can be grouped by
  quotes or brackets selected by the sum of the following:
 
     1 = doublequotes:    "a b c"
     2 = braces:          {a b c}
     4 = apostrophes:     'a b c'
     8 = parentheses:     (a b c)
    16 = square brackets: [a b c]
    32 = angle brackets:  <a b c>
 
  Nesting is possible with {}()[]<> but not with quotes or apostrophes.
 
Returns string:
  Word number n1, if there is one, otherwise an empty string.
 
Also see:
  HELP FUNCTION SPLIT
```

