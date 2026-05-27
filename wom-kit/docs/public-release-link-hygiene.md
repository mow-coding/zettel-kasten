# Public Release Link Hygiene

Date: 2026-05-27
Status: public documentation guardrail

## Summary

Public repository documents and GitHub Release bodies render links from different places.

A repo-local Markdown link can be correct inside the repository and still become wrong when the same text is copied into a GitHub Release body. v0.2.49 adds a local checker so release notes avoid that mistake before the release body is prepared.

## Link Types

### Repo-Local Markdown Links

Use repo-local links inside normal repository Markdown documents when the link is meant to be read from that file's location.

Example:

```markdown
[Public Documentation Map](public-documentation-map.md)
```

These links are good for docs that stay in the repository.

### GitHub Release Body Links

Release note files under `wom-kit/docs/releases/` may be copied into GitHub Release bodies.

For repository files linked from those release notes, use absolute GitHub `blob` URLs:

```markdown
[Public Release Link Hygiene](https://github.com/mow-coding/zettel-kasten/blob/main/wom-kit/docs/public-release-link-hygiene.md)
```

Do not use `../some-file.md` in release notes when that link points to a repository file. It may render correctly in the repo but incorrectly from a GitHub Release page.

For repository directories linked from release notes, use absolute GitHub `tree` URLs:

```markdown
[Release Notes](https://github.com/mow-coding/zettel-kasten/tree/main/wom-kit/docs/releases)
```

Do not use relative directory links such as `../examples/some-folder/` inside release notes. They may also render from the wrong GitHub Release page context.

### External URLs

Normal external `https://` links are not checked in v0.2.49.

Network checking can be flaky and should be a separate explicit batch if it is added later.

### Case-Sensitive Paths

GitHub file paths are case-sensitive. A link that works on a case-insensitive local machine can still break publicly if the case does not match the tracked file path.

## Local Checker

Run:

```powershell
python wom-kit\tools\check_public_links.py
```

The checker:

- inspects repository Markdown files through `git ls-files`,
- verifies repo-local Markdown file links with case-sensitive paths,
- accepts repo-local directory links in normal docs when the directory exists,
- requires release notes to use absolute GitHub `blob` URLs for repository file links and absolute GitHub `tree` URLs for repository directory links,
- rejects suspicious GitHub file links that use `/tree/` instead of `/blob/`,
- does not fetch external URLs.

## Non-Goals

v0.2.49 does not add product behavior, CLI/MCP archive commands, provider calls, GitHub Release editing, release publishing, ZET transport, feed ranking, trust/import/attestation/signature writes, projection writes, or receipts.
