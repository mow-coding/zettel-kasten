# Work Log: GitHub Publication Setup

Date: 2026-05-23

## 1. Purpose

Prepare GitHub repositories for the `zettel-kasten` and `zet` project:

- one public showcase/open-source repository,
- one private actual-use repository.

## 2. Account Check

GitHub CLI showed the active account:

```text
mow-coding
```

Local Git author configuration:

```text
user.name:  mow-coding
user.email: mow.coding@gmail.com
```

The GitHub authenticated email API could not be queried because the current token does not include the `user` scope. The token scope was not broadened automatically.

## 3. Public Repository

Created and pushed:

```text
https://github.com/mow-coding/zettel-kasten
```

Visibility:

```text
public
```

Initial commit:

```text
f6a135f Initial open-source zettel-kasten showcase
```

## 4. Private Repository

Created:

```text
https://github.com/mow-coding/zettel-kasten-private
```

Visibility:

```text
private
```

This repository is reserved for the user's actual personal working archive.

## 5. Files Added For Public Release

Added:

```text
README.md
LICENSE
NOTICE.md
CONTRIBUTING.md
SECURITY.md
.gitignore
```

These files define:

- MIT License,
- copyright attribution,
- public/private boundary,
- contribution rules,
- security reporting,
- contact at `mow.coding@gmail.com`,
- request for GitHub stars and collaboration/investment contact.

## 6. Publication Safety

The root `.gitignore` excludes:

- hidden provider login files,
- local agent instructions,
- detailed private meeting minutes,
- root decision logs,
- private strategy drafts,
- real archive folders,
- provider secrets,
- build/cache artifacts.

The staged files were scanned for obvious token/secret patterns before publishing.

## 7. Verification

Tests:

```text
python -m unittest discover -s tests
```

Result:

```text
125 tests OK, 8 skipped
```

Doctor:

```text
python cli\archive.py doctor examples\fake-life-archive --strict
```

Result:

```text
0 errors, 0 warnings
```

## 8. Next Work

The private repo exists, but real archive initialization should be done later through the planned onboarding flow:

```text
one-command setup
-> source registration
-> dry-run scan
-> draft zet
-> human-approved mint
```

