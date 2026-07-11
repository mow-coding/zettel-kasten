# zet Catalog Pass Artifact Lifecycle

Status: implemented in v0.3.217

## Plain-Language Purpose

`zet-catalog-pass` creates a complete private JSONL so a terminal AI can walk a
large local zet catalog without rescanning frontmatter in a new process for
every page. The file still needs a safe consumer and a safe ending.

v0.3.217 gives that temporary file a closed lifecycle:

```text
create -> pin SHA-256 -> validate -> read one page -> repeat -> preview cleanup -> approve cleanup
```

The JSONL remains private scratch. It does not become a zet, receipt, map,
index, backup, or external database record.

## 1. Create And Pin

Run the existing complete pass and retain `output.sha256` from its small stdout
summary:

```powershell
archive zet-catalog-pass <archive-root> `
  --status canonical `
  --projection reading `
  --output .wom-scratch/diagnostics/catalog-pass.jsonl `
  --dry-run `
  --progress `
  --format json
```

The SHA-256 covers the exact header, page, and footer bytes published by that
run. It is an artifact identity, not a signature or outside attestation.

## 2. Validate Without Returning Private Items

The first read can validate the whole artifact and return only counts and
proof metadata:

```powershell
archive zet-catalog-pass-read <archive-root> `
  --input .wom-scratch/diagnostics/catalog-pass.jsonl `
  --expected-sha256 <sha256-from-pass-summary> `
  --dry-run `
  --progress
```

Validation streams the file and checks:

- supported header, page, and footer schemas;
- contiguous page indexes and cursors from zero;
- one stable snapshot id and total count;
- strict continuation and final archive-wide coverage proof;
- full first response followed by compact continuation responses;
- final multi-page local revalidation proof;
- declared catalog projection and allowed item/result fields;
- explicit body-exclusion guards;
- the expected SHA-256 when supplied.

A malformed or changed artifact returns no catalog page.

## 3. Read One Bounded Page

Private page output requires the SHA-256 pin:

```powershell
archive zet-catalog-pass-read <archive-root> `
  --input .wom-scratch/diagnostics/catalog-pass.jsonl `
  --page-index 0 `
  --expected-sha256 <sha256-from-pass-summary> `
  --dry-run `
  --progress
```

The command validates the complete artifact before returning the selected
`catalog_page`. It never returns more than one page. Continue with
`selection.next_page_index` and the same SHA-256 until it becomes `null`.

This bounds model input, not filesystem work. Each independent read streams
and validates the complete JSONL again so it does not trust stale hidden state.

## 4. Preview And Approve Cleanup

Preview deletion after the final page is consumed:

```powershell
archive zet-catalog-pass-cleanup <archive-root> `
  --input .wom-scratch/diagnostics/catalog-pass.jsonl `
  --expected-sha256 <sha256-from-pass-summary> `
  --dry-run
```

Then approve only that validated artifact:

```powershell
archive zet-catalog-pass-cleanup <archive-root> `
  --input .wom-scratch/diagnostics/catalog-pass.jsonl `
  --expected-sha256 <sha256-from-pass-summary> `
  --approve `
  --reviewed-by human:local-operator
```

Cleanup revalidates structure and SHA-256, then checks the file identity and
hash once more immediately before deletion. It deletes no partial, directory,
zet, objet, manifest, or receipt. The reviewer value is not echoed and cleanup
itself writes no receipt because the target is explicitly disposable private
scratch rather than archive knowledge.

## Honest Boundaries

- The JSONL can contain private zet ids, titles, abstracts, facets, ties, and
  edges. Never commit it or paste the whole file into one model response.
- It contains no zet body text when generated and validated by this contract.
- `zet-catalog-pass-read` writes nothing and calls no provider or model.
- Cleanup is never automatic. It requires the exact artifact hash and explicit
  human approval.
- Hidden `.partial` files from forced termination are not accepted as complete
  artifacts and are not deleted by the cleanup command.
- SHA-256 detects identity changes; it is not proof that a model understood the
  page or that every zet has a usable abstract.
