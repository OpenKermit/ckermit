# Making a C-Kermit Release

This document describes the steps required to prepare and publish a release of
C-Kermit.

## 1. Update the Changelog

Make sure `doc/changelod.md` is up-to-date with details for the release.

## 2. Update Source Code Version and Build Information

Edit the version and date definitions in the codebase. Reference commit
`37dcbf4439cf959125b1439999616cdafe0eb727` for an example of these updates.

### `ckcmai.c`

Update the following macros and variable definitions:

- `EDITDATE`
- `EDITNDATE`
- `ck_s_edit`
- `ck_s_xver`
- `ck_l_ver`

### `makefile`

Update the following variables:

- `BUILDID`
- `CKVER`

### Commit all outstanding changes

Verify everything is committed.  PR/push it all.

## 3. Create and Push the Tag

Create the version tag and push both the commit and tag to origin:

```bash
git tag v11.0.503
git push origin main
git push origin v11.0.503
```

## 4. Prepare GitHub Release Description

Use `tools/unwrap_markdown.py` to format `doc/changelog.md` into single-line
paragraphs suitable for pasting into the GitHub release description:

```bash
python3 tools/unwrap_markdown.py doc/changelog.md
```

Copy the command output and paste it into the GitHub release text box.
