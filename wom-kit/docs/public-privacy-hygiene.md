# Public Privacy Hygiene

Status: local release-safety checker
Version: v0.2.52

v0.2.52 adds a small public privacy hygiene checker for WOM-kit repository work.

The checker turns the manual release privacy pass into a repeatable local command:

```powershell
python wom-kit\tools\check_public_privacy.py
```

It is a lightweight project guardrail. It is not a general-purpose secret scanner and does not replace human review before a public release.

## What It Checks

The checker reads Git-known public text files and flags obvious accidental leaks such as:

- local user-home paths with non-placeholder user segments,
- token-like strings for common provider and API key shapes,
- private key block headers,
- seed-phrase-like labels when the value is not clearly a placeholder,
- local or private-network provider endpoint examples,
- URLs that contain credential-looking userinfo before the host.

Placeholder examples are allowed when they are obviously fake, such as:

```text
C:\Users\example\dev\zettel-kasten
<repo-root>
<archive-root>
https://example.invalid/provider
http://localhost:<port>/api
```

## What It Does Not Do

The checker:

- does not rewrite files,
- does not fetch external URLs,
- does not inspect private archives,
- does not scan the whole disk,
- does not call provider APIs,
- does not edit GitHub Releases,
- does not add product CLI or MCP behavior.

It uses local Git file listing plus local text reads only.

## Cloud And Provider Endpoint Boundary

The checker catches obvious local/private endpoints and credential-bearing URLs, but it is intentionally not a general-purpose cloud secret scanner.

It may not catch every real cloud provider endpoint, token format, signed URL, JWT, webhook URL, or service-specific credential pattern unless a future batch adds those patterns explicitly.

## Relationship To Other Checkers

This checker complements:

- `wom-kit/tools/check_public_links.py`, which catches release-note link hygiene issues,
- `wom-kit/tools/check_korean_product_language.py`, which catches Korean product-language drift in public Markdown.

Together, these checks make the pre-release review loop more repeatable without changing WOM archive behavior.
