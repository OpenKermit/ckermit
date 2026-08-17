$!
$! CKVBUILDLOG.COM - Record C-Kermit build info for OpenVMS
$!
$! P1: Output file spec.  Default: ckvblog.txt
$!
$! Usage:
$!
$!    $ set default build_dev:[build_dir]
$!    $ @ source_dev:[source_dir]ckvbuildlog.com [ output_file_spec ]
$!
$!
$ on error then goto clean_up
$ say = "write sys$output"
$!
$! Script info.
$!
$ ckvbl_date = "2024-08-19"
$ ckvbl_vers = "0.1"
$!
$! Determine the output file name.
$!
$ build_log_file_name = "ckvker.blog"
$ out_file_name = "ckvblog.txt"
$ shofeat_file_name = "shofeat.txt"
$ wermit_exe = "sys$disk:[]wermit.exe"
$!
$ procedure = f$environment("PROCEDURE")
$ procname = f$element(0,";",procedure)
$ procname = f$parse( procname, , , "NAME", "SYNTAX_ONLY")+ -
             f$parse( procname, , , "TYPE", "SYNTAX_ONLY")
$!
$ sts = 1
$!
$ if (P1 .nes. "")
$ then
$    out_file_name = P1
$ endif
$!
$ if (f$search( wermit_exe) .eqs. "")
$ then
$   say "wermit executable (''wermit_exe') not found in this directory."
$   say "This script (''procname') must be run in a C-Kermit build directory."
$   say "Please see instructions in ""ckvker.com""."
$   sts = %X00018292 ! RMS-E-FNF, file not found
$   goto clean_up
$ endif
$!
$! Open the output file.
$!
$ create /fdl = sys$input 'out_file_name'
RECORD
        FORMAT stream_lf
$!
$ open /append out_file 'out_file_name'
$!
$! Write the report.
$!
$! Prefix.
$!
$ write out_file "<tr>"
$!
$! OS, version.
$!
$ write out_file "<td>OpenVMS "+ f$getsyi( "version")
$!
$! Host architecture (from build log file).
$!
$ in_file_name = build_log_file_name
$ search_string = "ARCH="
$ gosub scanfile
$ arch = f$extract( f$length( search_string), 2047, match)
$ write out_file "<td>''arch'"
$!
$! Source location.
$!
$ in_file_name = build_log_file_name
$ search_string = "CK_SOURCE="
$ gosub scanfile
$ ck_source = f$extract( f$length( search_string), 2047, match)
$!
$! Build command.
$!
$ in_file_name = build_log_file_name
$ search_string = "P1="
$ gosub scanfile
$ bp1 = f$extract( f$length( search_string), 2047, match)
$!
$ search_string = "P2="
$ gosub scanfile
$ bp2 = f$extract( f$length( search_string), 2047, match)
$!
$ search_string = "P3="
$ gosub scanfile
$ bp3 = f$extract( f$length( search_string), 2047, match)
$!
$ search_string = "P4="
$ gosub scanfile
$ bp4 = f$extract( f$length( search_string), 2047, match)
$!
$ search_string = "P5="
$ gosub scanfile
$ bp5 = f$extract( f$length( search_string), 2047, match)
$!
$ search_string = "P6="
$ gosub scanfile
$ bp6 = f$extract( f$length( search_string), 2047, match)
$!
$ rp1 = ""
$ rp2 = ""
$ rp3 = ""
$ rp4 = ""
$ rp5 = ""
$ rp6 = ""
$!
$ if ((bp1 .nes. "") .or. (bp2 .nes. "") .or. (bp3 .nes. "") .or. -
      (bp4 .nes. "") .or. (bp5 .nes. "") .or. (bp6 .nes. ""))
$ then
$   rp1 = " """+ bp1+ """"
$ endif
$!
$ if ((bp2 .nes. "") .or. (bp3 .nes. "") .or. -
      (bp4 .nes. "") .or. (bp5 .nes. "") .or. (bp6 .nes. ""))
$ then
$   rp2 = " """+ bp2+ """"
$ endif
$!
$ if ((bp3 .nes. "") .or. -
      (bp4 .nes. "") .or. (bp5 .nes. "") .or. (bp6 .nes. ""))
$ then
$   rp3 = " """+ bp3+ """"
$ endif
$!
$ if ((bp4 .nes. "") .or. (bp5 .nes. "") .or. (bp6 .nes. ""))
$ then
$   rp4 = " """+ bp4+ """"
$ endif
$!
$ if ((bp5 .nes. "") .or. (bp6 .nes. ""))
$ then
$   rp5 = " """+ bp5+ """"
$ endif
$!
$ if ((bp6 .nes. ""))
$ then
$   rp6 = " """+ bp6+ """"
$ endif
$!
$ write out_file "<td>@ckvker.com"+  rp1+ rp2+ rp3+ rp4+ rp5+ rp6
$!
$! Source kit date.
$!
$ editndate = ""
$ in_file_name = ck_source+ "ckcmai.c"
$ search_string = "EDITNDATE"
$ gosub scanfile
$ sts = $status
$ if (match .nes. "")
$ then
$   editndate = f$element( 2, " ", match)- """"- """" ! yyyymmdd
$   editndate = f$extract( 0, 4, editndate)+ "-"+ -
                f$extract( 4, 2, editndate)+ "-"+ -
                f$extract( 6, 2, editndate)
$ endif
$ write out_file "<td>''editndate'"
$!
$! Executable (wermit.exe) size (bytes).
$!
$ if (f$parse( wermit_exe) .nes. "")
$ then
$   siz = f$file_attributes( wermit_exe, "EOF")* 512
$ else
$   siz = "???"
$ endif
$ write out_file "<td>''siz'"
$!
$! C compiler version.
$!
$ in_file_name = build_log_file_name
$ search_string = "CC_VERSION="
$ gosub scanfile
$ ccv = f$extract( f$length( search_string), 2047, match)
$ write out_file "<td>''ccv'"
$!
$! OpenSSL version.
$!
$ in_file_name = build_log_file_name
$ search_string = "SSL_VERSION="
$ gosub scanfile
$ osslv = f$extract( f$length( search_string), 2047, match)
$ write out_file "<td>''osslv'"
$!
$! "show features" report.
$!
$ ck_sts = 0
$ banner = ""
$ ck_dir = ""
$ if (siz .nes. "???")
$ then
$!
$! Note: With MCR anyplace, command-line case is not preserved.
$! Upper-case (case-significant) command-line material must be quoted.
$!
$   define /user_mode sys$output 'shofeat_file_name'
$   mcr 'wermit_exe' "-C" "{ show features, exit }"
$   ck_sts = $status
$!
$   if ((ck_sts .and. %x7) .eq. 1)
$   then
$!
$! Extract Kermit banner from "show features" report.
$!
$     in_file_name = shofeat_file_name
$     search_string = "C-Kermit"
$     gosub scanfile
$     banner = match
$!
$! Extract Kermit "dir kermit.exe" report.
$!
$     temp_file_name = "ck_dir.tmp"
$     define /user_mode sys$output 'temp_file_name'
$     mcr 'wermit_exe' "-H" "-C" "dir wermit.exe , quit"
$!
$     in_file_name = temp_file_name
$     search_string = "("
$     gosub scanfile
$     ck_dir = match
$     delete /nolog 'temp_file_name';*
$!
$   endif
$!
$ endif
$!
$!
$! Build Status.
$!
$ if ((ck_sts .and. %x7) .eq. 1)
$ then
$   sts_str = "OK"
$ else
$   sts_str = "FAILED"
$ endif
$ write out_file "<td>''sts_str'"
$!
$! Close the output file, if open.
$!
$ if (f$trnlnm( "out_file") .nes. "")
$ then
$   close out_file
$ endif
$!
$! Display info.
$!
$ say "''procname' ''ckvbl_vers' ''ckvbl_date'"
$ say "This directory: "+ f$environment( "default")
$ if (banner .nes. "")
$ then
$   say "wermit: "+ banner
$   say "Executable: "
$   say ck_dir
$   say ""
$   say "''procname' done, result (also in ''out_file_name';"
$   say "please email it to fdc@columbia.edu):"
$   type 'out_file_name'
$ else
$   say "wermit.exe not found"
$   say "''procname' must be run in a C-Kermit build directory."
$   say "Please see instructions in ""ckvker.com""."
$ endif
$!
$ clean_up:
$!
$ on error then exit
$!
$! Close the output file, if open.
$!
$ if (f$trnlnm( "out_file") .nes. "")
$ then
$   close out_file
$ endif
$!
$! End of main-line code.
$!
$! Exit.
$!
$ exit 'sts'
$!
$!----------------------------------------------------------------------
$!
$! Subroutines.
$!
$! SCANFILE - Scan file 'in_file_name' for string 'search_string'.
$             Return first matching line in symbol "match".
$!
$ scanfile:
$!
$! in_file_name: input file
$! search_string: search string
$! match: DCL symbol for output line
$!
$ open /read in_file 'in_file_name'
$ sts = $status
$ if ((sts .and. %x7) .eq. 1)
$ then
$   match = ""
$   read_loop_top:
$   read in_file line -
     /end_of_file = read_loop_end /error = read_loop_end
$!
$   line_len = f$length( line)
$   if (f$locate( search_string, line) .lt. line_len)
$   then
$     match = line
$   else
$     goto read_loop_top
$   endif
$   read_loop_end:
$   close in_file
$ endif
$ return sts
$!
