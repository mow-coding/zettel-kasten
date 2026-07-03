Both load-bearing claims are confirmed empirically:

1. **Scanners miss the R2/AWS secret.** `DRAFT_SECRET_VALUE_RE` (line 1480) only fires on high-entropy values when preceded by a `secret=/token=/?? label, plus fixed shapes `AKIA[0-9A-Z]{16}` (the non-secret ID), `ghp_??, and PEM headers. `GITHUB_SECRET_LIKE_RE` (1634) only catches `ghp_/github_pat_/sk-?? and the literal words token/secret/etc. A bare 64-hex R2 secret or 40-char AWS secret in an unlabeled JSON field is invisible to both. The red-team is correct.

2. **Idempotency predicate is digest-blind.** `object_storage_upload_evidence_location_exists` (41192??1208) matches only `provider=="object_storage"` AND `provider_kind` AND `store_ref` ??it never inspects the object's digest. Confirmed.

3. **Anchor drift confirmed.** Real HEAD is `a5425b62`, not v0.3.162. I'll re-pin.

4. **Reliability red-team is a stub** (`{"verdict":"test",??"a"]??"b"]}`) ??no actionable content; I'll record that explicitly rather than fabricate findings.

I have enough verified grounding to lock the doc. Writing the final design now.

---

# WOM #11 ??Live Object-Storage Upload Adapter: Staged Design + Threat Model (LOCKED)

**Status:** DESIGN-LOCKED. READ-ONLY design phase ??no implementation in this batch.
**Anchor commit (re-pinned):** `a5425b62` ("Add honest mint-receipt reconcile with content-change gating"). *Implementers diff against this tree, NOT the earlier-cited v0.3.162 tag. All line anchors below are into `wom-kit/src/wom_kit/` at `a5425b62` and are approximate ??resolve by symbol name, not by line number.*
**Decision:** Kim Seong Kyun, 2026-07-03 ??BUILD #11 as an approval-gated WOM-kit CLI command, NOT a provider MCP the AI drives.
**Review provenance:** Folds in the security red-team (4 BLOCKERs, 3 SHOULDs, 1 NIT, 5 residual risks), each resolved below with a decision + rationale. The reliability red-team returned a non-substantive stub (`verdict:"test"`, `["a"]`, `["b"]`) ??it produced **no actionable finding**; recorded in 짠9 so the gap is visible and a real reliability pass can be re-run before Stage 2 code lands.

---

## 0. First principles (why the normal rule is insufficient here)

This is the FIRST WOM surface that simultaneously (a) holds a real credential, (b) makes a live network call, and (c) mutates remote state. The house rule "temp-dir tests pass ??auto-release" is **necessary but not sufficient** for the wire step: the actual S3-compatible `PUT` cannot be proven in a temp dir. The build is split so everything provable stays auto-releasable, and only the unprovable wire step is Kim-gated and tiny-first.

- **Stage 1 (auto-releasable):** credential-ref resolution *shape*, upload plan, digest-aware idempotency/skip-already-uploaded, local RAW-byte verification (`sha256` of local bytes == `object_id`), dry-run preview, receipts, and ??critically ??the **direct-value secret-containment control** (짠2.3) that is the load-bearing safety claim of the whole batch. Fully temp-dir testable.
- **Stage 2 (Kim-gated):** the live `PUT` behind `--approve`, provider `HEAD` before/after, checksum comparison, resume ledger, provider-confirmed manifest update, execution receipt. Tested against an **injected fake transport** (no server, no new dependency). Shipped with an explicit `unproven_against_live_provider: true` caveat and validated **tiny-first** (one object before ~19k objects / 158 GB).

The existing `object_storage_adapter_execution_contract` (`archive_services.py:45650`, doc `docs/object-storage-adapter-execution-contract.md`) is the load-bearing spec this adapter must satisfy; this design does not relax it, it implements it ??and it **tightens** two of its assumptions (secret detection and idempotency) that the red-team proved insufficient.

---

## 0.1 Red-team resolutions (decision log ??every required_change)

| ID | Red-team item | Severity | Decision | Rationale |
|---|---|---|---|---|
| **RC1** | Named scanners do NOT catch R2/AWS *secret* keys; only the non-secret `AKIA` ID. 짠2.3 secret-free proof does not hold. | BLOCKER | **ADOPT.** Replace the regex-primary control with a **direct constant-time containment check** of the two resolved key values against the fully-serialized output, on every write path. Regexes demoted to backstop. (짠2.3, 짠7-T1) | Verified empirically at `a5425b62`: `DRAFT_SECRET_VALUE_RE` (1480) needs a `secret=/token=` label to fire on a bare hex/base64 value; `GITHUB_SECRET_LIKE_RE` (1634) only matches `ghp_/sk-/github_pat_` + literal keywords. A 64-hex R2 secret or 40-char AWS secret in an unlabeled field passes both clean. The only sound control is comparing against the actual in-memory secret. |
| **RC2** | 짠2.3 unit test injects `AKIA??sk-??ghp_?? ??exactly the shapes the scanners DO catch ??proving nothing about the real secret. | BLOCKER | **ADOPT.** Stage-1 secret-free test injects the TRUE shapes (64-hex R2 secret, 40-char AWS secret, B2 appKey) and asserts absence across receipt+ledger+manifest-delta+return payload+**every** `failed_*` branch. Test MUST fail if only the regex backstop is present. (짠2.3, 짠6) | A green test on the wrong shapes manufactures false confidence in the auto-releasable half. The test must exercise the direct-value control, not the backstop. |
| **RC3** | `object_storage_upload_evidence_location_exists` (41192) is DIGEST-BLIND ??matches only `(provider_kind, store_ref)`, never the object's digest. New `wom_uploaded` variant + `--only` + `--plan-from` make a same-store/different-digest false-positive skip reachable. | BLOCKER | **ADOPT.** Stage-2 idempotency matches on the content-addressed `key_hint` digest == planned object's `object_id` digest, not just `(provider_kind, store_ref)`. Add an audit assertion: every `object_storage` location's `key_hint` digest == the enclosing record's `object_id`. (짠3.1, 짠3.3, 짠7-T11) | Confirmed at 41198??1208: no digest comparison. Reusing it verbatim for `--skip-uploaded` would silently skip an un-uploaded object or advance a manifest location whose key does not match the record. |
| **RC4** | The cited pre-write gate (`37892`) runs only `contains_forbidden_location_reference or DRAFT_SECRET_VALUE_RE` ??it does not even include `GITHUB_SECRET_LIKE_RE`, and misses the secret per RC1. | BLOCKER | **ADOPT.** Do NOT cite 37892 as the template. Specify a NEW `assert_no_secret_or_location_leak(...)` that (a) does constant-time containment of BOTH resolved key values, (b) runs all three heuristic scanners as backstop, (c) is invoked on EVERY exit path incl. all `failed_*` branches and the dry-run preview. (짠2.3) | The existing pattern is both incomplete (one scanner) and unsound (wrong scanner). The new gate is the single enforcement point for T1/T2. |
| **RC5** | SigV4 / provider-error leakage: R2 `SignatureDoesNotMatch` bodies echo `StringToSign/CanonicalRequest`; if captured into `retry_summary`/ledger/receipt, secret-adjacent material leaks and no scanner catches it. | SHOULD | **ADOPT.** Explicitly forbid recording request headers, `Authorization`, `StringToSign`, `CanonicalRequest`, or any provider error body in `retry_summary`/ledger/receipt. Ledger + receipt are built from a fixed scalar **allowlist**, never from caught exception args. (짠4, 짠5, 짠7-T9) | A `SignatureDoesNotMatch?쪺tringToSign?? body passes both regexes clean. Allowlist construction is the only durable guarantee that no error body reaches disk. |
| **RC6** | `--max-objects` REFUSE precedent cited (14780) but not pinned to the SERVICE layer, so a direct service/MCP call could bypass it. | SHOULD | **ADOPT.** `--max-objects` REFUSE is enforced in the **service** plan-builder, before any credential read, mirroring the CLI+service double-gate. (짠1.1, 짠5, 짠7-T5) | Same double-layer logic T6 uses for the approval gate; CLI-only enforcement is bypassable via direct service/MCP call. |
| **RC7** | Env-only-first-live is doc-only; the Tiro resolver blocks `secret:/wallet:` but not `keyring:/credential-manager:`. | SHOULD | **ADOPT.** Implement env-only-first-live as an explicit **service-layer blocker** appended in the approve path BEFORE `resolve_credential_value` is called for either key. (짠2.2, 짠7-T8) | `safe_credential_ref` accepts `keyring:/credential-manager:`; without an explicit blocker they would resolve at B6. Fail closed until the env path is proven live. |
| **RC8** | Anchor drift: doc HEAD v0.3.162 ??real HEAD; `resolve_credential_value` does not yet exist (it is the proposed generalization). | NIT | **ADOPT.** Re-pinned to `a5425b62` (verified). All anchors resolved by symbol name. `resolve_credential_value` is explicitly labelled NEW (generalization of `tiro_read_credential_value` at 25456). | Implementers must diff against the right tree. |

---

## 1. COMMAND SURFACE (staged)

Naming stays inside the existing `object-storage-*` family (`archive_cli.py:42-86`) with the established Korean-typo aliases (`objet-*`). Every mutating handler copies the three-way gate from `command_remint_reconcile` (`archive_cli.py:8470`) and `command_objet_capture` (`archive_cli.py:9000`): reject both modes, reject neither, reject `--approve` without a safe `--reviewed-by`. The service layer re-enforces the same invariants (per `objet_capture_enable` at `archive_services.py:62964`) so the gate cannot be bypassed via a direct service call or MCP.

### 1.1 Stage 1 ??up to the wire (no network, auto-releasable)

**(S1-a) `object-storage-upload-plan`** *(aliases: `object-storage-upload-plan-preview`, `objet-storage-upload-plan`)*
Read-only, `--dry-run` **required**, writes **nothing**.
```
archive object-storage-upload-plan \
  --provider-kind cloudflare-r2 \
  --store-ref storage:account:<label> \
  --access-key-id-ref env:WOM_R2_ACCESS_KEY_ID \
  --secret-access-key-ref env:WOM_R2_SECRET_ACCESS_KEY \
  [--only sha256:<hex> | --plan-from <matched-set>] \
  [--max-objects 1] [--skip-uploaded] \
  --dry-run
```
- Chains the shipped gate pipeline: `object_storage_adapter_readiness_plan` (`45210`) ??`object_storage_operation_request_plan` (`45360`, `--operation upload_object`) ??`object_storage_adapter_execution_contract` (`45650`). Keeps `live_execution_allowed_now=False`.
- Resolves each candidate `object_id` to local bytes via `resolve_objet_ref` (`55139`).
- Emits a per-object plan: `object_id`, `size_bytes`, computed content-addressed remote key shape `sha256/<first2>/<sha256>` (`OBJECT_STORAGE_UPLOAD_KEY_STRATEGY`, `1729`), and a **digest-aware idempotency verdict** `would_upload | already_uploaded` (짠3.1, digest-matched ??NOT the raw digest-blind predicate).
- Validates the two credential refs *for shape only* via `safe_credential_ref` (`39872`); reports only their store class via `credential_ref_store` (`39864`). No secret read; `credential_value_read=False`.
- **`--max-objects N` REFUSES** (does not truncate) if the plan exceeds N. **Per RC6: this REFUSE is enforced in the service plan-builder, before any credential read**, mirroring `mint-batch` (`archive_cli.py:14780`) at the service layer ??so an AI calling the service directly cannot pass `max_objects=1` while planning 19k. "Exactly one" is provable, not "at most one processed".

**(S1-b) `object-storage-upload-verify`** *(aliases: `object-storage-local-byte-verify`, `objet-storage-upload-verify`)*
Read-only, `--dry-run` **required**, writes **nothing**.
- The Stage-1 *proof* step: for each planned `object_id`, streams the local file through `sha256_path` (`58848`) and asserts the RAW-byte digest equals the `sha256:<hex>` in `object_id`. **Hash RAW bytes** ??do NOT use `bytes_normalized_for_content_compare` (`58856`, BOM/CRLF normalization); upload verification must be byte-exact.
- Emits `local_byte_verification: {object_id, verified: true|false, size_bytes}`. This earns the semantic value `byte_verification_by_wom_kit` (still not written to the manifest until Stage 2 confirmation).

> Split rationale: the plan is cheap and secret-class-only; the verify pass reads local bytes. Separation lets an operator preview a 19k-object plan without hashing 158 GB, then verify a bounded `--only`/`--max-objects` slice.

### 1.2 Stage 2 ??the live PUT (Kim-gated, tiny-first)

**(S2) `object-storage-upload`** *(aliases: `object-storage-upload-execute`, `objet-storage-upload`)*
Mutating. Requires **exactly one** of `--dry-run` / `--approve`; `--approve` additionally requires `--reviewed-by <safe-actor-id>` and `--store-ref`.
```
archive object-storage-upload \
  --provider-kind cloudflare-r2 \
  --store-ref storage:account:<label> \
  --access-key-id-ref env:WOM_R2_ACCESS_KEY_ID \
  --secret-access-key-ref env:WOM_R2_SECRET_ACCESS_KEY \
  --only sha256:<hex> \            # tiny-first: name the single object
  --max-objects 1 \               # service-layer REFUSE if plan > 1
  --skip-uploaded \               # digest-aware manifest + remote-HEAD idempotency
  --reviewed-by kim \
  --approve
```
Modes:
- `--dry-run`: identical output to `object-storage-upload-plan` plus the execution-receipt *preview* shape. `provider_api_called=False`, reads no bytes, reads no secret. **The dry-run preview is also passed through `assert_no_secret_or_location_leak` (짠2.3) ??RC4.**
- `--approve`: the ONLY mode that reads the secret, reads local bytes, and calls the provider. Behavior in 짠3?벬?.

**Writes on `--approve` success:**
1. Resume ledger (append-only JSONL, no secrets, **allowlist-built** per RC5) at `receipts/providers/object-storage-executions/<case-id>.resume-ledger.jsonl` ??durable via `_atomic_write_json`-style write (`9346`).
2. Non-secret execution receipt at `receipts/providers/object-storage-executions/<case-id>.object-storage-upload.json` (짠4), written **receipt-first** then manifest, per the crash-safety ordering rule (`objet_capture_enable` comment, `63084`).
3. Manifest location transition in `objects/manifests/files.jsonl` ??only after provider confirmation (짠3, 짠4), via an extended `update_manifest_with_object_storage_upload_evidence` (`41234`).

**Tiny-first is enforced structurally**: `--max-objects` refuses at the service layer when the plan exceeds the cap; the receipt records the *actual* uploaded `object_count` as a fact (mirroring `notion` recording `request_count`, `22335`), giving a verifiable "one object" proof for the first live release.

---

## 2. CREDENTIAL MODEL

### 2.1 The two-secret gap

An S3-compatible R2 `PUT` needs four things: **Access Key ID**, **Secret Access Key** (both secret in effect ??the ID is publicly loggable but still treated as a resolved-value to contain), **endpoint**, **bucket** (both non-secret metadata). The shipped binding builder `build_object_storage_provider_binding` (`47865`) models auth as a *single* token (`token_env` / `account_ref`, `47891`) ??it does **not** model the S3 key pair. The design closes this by modelling **two independent refs**, each reusing the existing resolver unchanged:

- `access_key_id_ref` and `secret_access_key_ref`, each validated by `safe_credential_ref` (`39872`) ??each must carry a `CREDENTIAL_REF_PREFIXES` prefix (`env:` / `keyring:` / `credential-manager:` / `secret:` / `wallet:`, `1806`) and is shape-checked against `OBJECT_STORAGE_REF_RE` (`1717`) to contain no URL/path/query/secret characters (`@ :// / \ # ? & =`).
- endpoint stays a **ref**, never a URL: `default_object_storage_endpoint_ref` ??`provider:endpoint:<kind>` (`47796`), guarded by `safe_object_storage_ref` (`47846`).
- bucket stays non-secret metadata under `OBJECT_STORAGE_BUCKET_RE`.

Binding schema extension: add `auth.access_key_id_ref` and `auth.secret_access_key_ref` alongside the existing single-token fields (kept for backward compat with setup-managed bindings). Both new fields pass `safe_credential_ref`, so they are safe to record in `provider-bindings.yml` and in receipts ??only the *resolved values* are secret.

### 2.2 Resolution (reuse Tiro, do not fork)

The only working ref?뭭alue resolver today is `tiro_read_credential_value` (`25456`). **Generalize it into a shared `resolve_credential_value(ref, store)` (NEW ??RC8)** rather than forking, and call it for each of the two refs. Resolution dispatch is inherited verbatim:
- `env:` ??`os.environ.get(safe_environment_ref_name(...))`, env NAME matching `^[A-Z][A-Z0-9_]{2,80}$` (`39786`).
- `keyring:` / `credential-manager:` ??`tiro_windows_credential_manager_read_secret` via `ctypes` `CredReadW`/`CredEnumerateW` (`25354`).
- `secret:` / `wallet:` ??shape-valid but **no resolver** ("not supported for approved live fetch", `25486`) ??blocks.

**First-live-call env-only restriction ??now a HARD service-layer blocker (RC7).** The one shipped live adapter (Notion) restricts the FIRST live call to `env:` refs only (`22229`, `22258`). Stage 2 mirrors this, but **as an explicit blocker appended in the approve path BEFORE `resolve_credential_value` is called for either key** ??not doc-only. Both refs must be `env:` at B6; `keyring:`/`credential-manager:` refs (which `safe_credential_ref` accepts) **fail closed** at the first live release even though the resolver could handle them. Expand to `keyring:` only after the env path is proven live. This is a service-layer gate, not a schema change.

### 2.3 Hard no-secret guarantee ??DIRECT-VALUE CONTAINMENT (rewritten per RC1/RC2/RC4)

> **This section is the load-bearing safety claim of the whole batch and the original draft got it wrong.** The named regex scanners do NOT detect an R2/AWS *secret* key. Verified at `a5425b62`: `DRAFT_SECRET_VALUE_RE` (1480) only fires on a bare high-entropy value when preceded by a literal `secret=/token=/password=/aws_secret_access_key=` label; a raw 64-hex R2 secret or 40-char AWS secret in an unlabeled JSON field is invisible. `GITHUB_SECRET_LIKE_RE` (1634) only matches `ghp_/github_pat_/sk-?? + literal keywords. The ONLY R2/S3 shape they catch is the non-secret `AKIA?? access-key *ID*. **The primary control is therefore direct comparison against the actual resolved secret, not a regex.**

The two resolved key values follow the Tiro token discipline exactly:
- read **only** inside `if approve and not blockers` (`25696`);
- held in local vars, **hard-cleared in `finally: key = None`** (`25880`);
- **never** placed in blockers, warnings, receipts, manifest, resume ledger, return payload, or any log line.

**Primary control ??`assert_no_secret_or_location_leak(serialized, key_values, ...)` (NEW, RC4).** Before ANY write, and on EVERY exit path (success, every `failed_*` branch in 짠5, and the dry-run preview), the fully-serialized output ??receipt + resume-ledger delta + manifest delta + return payload ??is checked by:
1. **Direct constant-time containment** of BOTH resolved key values (Access Key ID and Secret Access Key) as substrings of the serialized text. Use a constant-time comparison over sliding windows / a single `value in serialized` guarded so timing does not leak the key; **any containment ??hard abort before write, key cleared, `result_status: failed_secret_guard`** (which itself carries no secret). This is the sound guarantee ??it catches the 64-hex/40-char secret the regexes miss, and also catches `StringToSign`/error-body echoes that happen to embed the key.
2. **Backstop scanners (defense in depth, not primary):** `DRAFT_SECRET_VALUE_RE` (1479) + `GITHUB_SECRET_LIKE_RE` (1633) + `contains_forbidden_location_reference` (`paths.py:142`) all as negative gates. These catch labelled secrets, `AKIA` IDs, PEM blocks, and provider URLs / absolute paths ??a genuinely useful second layer, but explicitly NOT relied on for the raw secret.
3. **`privacy_guards` block** of `*_echoed:false` booleans (execution-contract template, `45858`): `secret_values_echoed`, `exact_credential_refs_echoed`, `bucket_names_echoed`, `provider_urls_echoed`, `local_absolute_paths_echoed`, `generated_urls_echoed` ??all `false`.

**Stage-1 secret-free unit test (rewritten, RC2).** Inject the TRUE credential shapes as fake env values ??a **64-char lowercase-hex R2 secret** (e.g. `3f786850e387550fdab836ed7e6dc881de23001b??), a **40-char AWS-style secret** (e.g. `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`), and a **B2 appKey** ??run the full serialize-then-gate over receipt + ledger + manifest-delta + return payload + **every** `failed_*` branch, and assert the raw value is absent from all of them. **The test MUST FAIL if only the regex backstop is present** (i.e. it must exercise the direct-value containment control), forcing control #1. This is the temp-dir-testable, Stage-1 (B3) secret-free proof ??and it is what makes the auto-releasable half actually safe.

---

## 3. IDEMPOTENCY & VERIFICATION

### 3.1 "Already uploaded" ??two layers, both DIGEST-AWARE (rewritten per RC3)

**Layer A (manifest, both stages) ??digest-matched, NOT the raw predicate.** The shipped predicate `object_storage_upload_evidence_location_exists` (`41192`) is **digest-blind** ??verified at 41198??1208 it matches only `provider=="object_storage"` AND `provider_kind` AND `store_ref`, never the object's digest. Reusing it verbatim for `--skip-uploaded` would false-positive on a same-store location carrying a *different* digest (after a partial run or a hand-edited manifest), silently skipping an un-uploaded object. **Therefore `--skip-uploaded` uses a digest-aware wrapper:** an object is `already_uploaded` only if a matching `object_storage` location exists with `(provider_kind, store_ref)` AND the location's `key_hint` digest equals the planned object's `object_id` digest. The manifest appender (`41234`) already appends only when `not already_present`, so re-running remains safe by construction ??but the "already present" test is now digest-correct.

**Layer B (remote HEAD, Stage 2 only).** Before the `PUT`, issue a provider `HEAD` on the content-addressed key. Per the execution contract, `provider_head_before_upload_for_idempotency=True`. Verdicts:
- `remote_absent` ??proceed to `PUT`.
- `remote_present_same` (size + checksum match, 짠3.2) ??skip the `PUT`, treat as already-uploaded, still allowed to advance the manifest to provider-confirmed (bytes proven to match).
- `remote_present_different` ??**fail closed** for that object (짠5), do NOT overwrite.

Layer A is cheap and offline; Layer B is the authoritative network check. `--skip-uploaded` short-circuits on (digest-aware) Layer A; without it, Layer B still runs and still refuses to overwrite differing bytes.

### 3.2 Byte verification ??before and after

- **Before (local):** `sha256_path` (`58848`) over RAW local bytes must equal the `sha256:<hex>` in `object_id`. Mismatch ??blocker, no upload. Flips the *earned* value of `byte_verification_by_wom_kit` to true ??written to the manifest only after provider confirmation.
- **After (remote):** `provider_head_after_upload_required=True`. Compare **non-secret** `size` + `checksum` only. Checksum policy per the integrity contract (`45753`+):
  - Prefer the provider's SHA-256 checksum when supported (`x-amz-checksum-sha256` on AWS S3 / R2 S3 API).
  - **ETag is NOT treated as sha256** unless provider policy is verified; multipart uploads produce composite ETags, so a multipart/large-object checksum policy is required and the adapter must not assume ETag == md5 == content hash.
  - `content_sha256_must_match_object_id`. The remote HEAD comparison is on size + provider checksum, never on a secret or URL.

Only after the after-HEAD confirms does `provider_confirmation_by_wom_kit` become eligible to be true.

### 3.3 The location-variant problem + digest audit (must-fix, not bypass)

The current `object_storage` location is pinned: `availability="declared_uploaded"`, `byte_verification_by_wom_kit=False`, `provider_confirmation_by_wom_kit=False` (`41211`). The audit `object_storage_upload_evidence_audit_location_errors` (`41550`) **rejects any location claiming either flag true**. The live adapter must NOT reuse `declared_uploaded`; it introduces a new WOM-verified variant and **extends the audit** (never bypasses it):

| Field | External-evidence (today) | WOM live upload (Stage 2) |
|---|---|---|
| `availability` | `declared_uploaded` | `wom_uploaded` (provider-confirmed) |
| `byte_verification_by_wom_kit` | `false` | `true` (local sha proven) |
| `provider_confirmation_by_wom_kit` | `false` | `true` (after-HEAD proven) |
| `content_addressed` | `true` | `true` |
| `key_strategy` | `sha256_content_addressed` | `sha256_content_addressed` |
| `execution_receipt_ref` | ??| `<execution receipt path>` |

Audit extension (two branches):
- For `availability == "wom_uploaded"`: both `by_wom_kit` flags MUST be true and `execution_receipt_ref` MUST resolve to an on-disk execution receipt.
- For `availability == "declared_uploaded"`: existing invariants (both flags false) stand unchanged.
- **NEW digest invariant (RC3), applied to BOTH branches:** every `object_storage` location's `key_hint` digest MUST equal the enclosing manifest record's `object_id` digest. A location whose key digest does not match its record is an audit **error** ??this closes the digest-blind false-skip / mismatched-advance hole at the audit layer, so even a hand-edited manifest is caught.

---

## 4. RECEIPTS

Two receipts already exist in shape; Stage 2 adds the **execution receipt writer** (distinct from the shipped evidence-receipt writer `41283`).

**Execution receipt** at `receipts/providers/object-storage-executions/<case-id>.object-storage-upload.json`, written via the durable `_atomic_write_json` primitive (`9346`: temp `.part-<token_hex(8)>` + flush + `os.fsync` + `os.replace`) and immutable-by-monotonic-suffix per the reconcile precedent (`9436`) so each execution EVENT is never overwritten.

**RECEIPT + LEDGER ARE ALLOWLIST-BUILT (RC5).** Both the execution receipt and the resume-ledger rows are assembled from a **fixed allowlist of scalar fields only** ??never from caught exception args, provider response bodies, or request headers. Explicitly forbidden anywhere in receipt/ledger/`retry_summary`: request headers, `Authorization`, `StringToSign`, `CanonicalRequest`, provider error body, raw adapter output. `retry_summary` records only scalar counters (`attempts`, `last_status_class`, `backoff_ms_total`) ??never the provider's response text.

**RECORDS (required fields, from `receipt_contract`):**
- `operation` (`upload_object` only ??`EXECUTION_CONTRACT_OPERATIONS`, `1726`), `object_id`, `provider_kind`, `store_ref`, `key_strategy`, `key_hint` (`sha256/<first2>/<sha256>` ??the *shape*, not a URL).
- `result_status` (`uploaded | skipped_already_present | skipped_remote_same | remote_conflict_different_bytes | failed_auth | failed_rate_limited | failed_upload | failed_secret_guard`), `bytes_uploaded`, `checksum_algorithm`, `retry_summary` (scalar-only), `object_count` (the tiny-first proof), `reviewed_by` (the safe actor id ??the ONLY identity recorded).
- `availability_transition`: `{from: "<none|declared_uploaded>", to: "wom_uploaded"}` and the two flag transitions `false?뭪rue`.
- `manifest_update_preview` (dry-run) / `manifest_update_applied` (approve), `execution_receipt_ref` self-reference.
- `closed_actions` booleans (`provider_api_called`, `credential_value_read`, `object_file_bytes_read`, `local_sha256_computed`, `remote_head_checked`, `object_uploaded`, `manifest_updated`, ?? recording what actually ran ??the `45842` template, now with true values where the adapter acted.
- `privacy_guards` block (짠2.3).

**NEVER RECORDS (from `must_not_include`, verified `45805`):** `secret_values`, `exact_credential_refs`, `bucket_names`, `provider_urls`, `local_absolute_paths`, `raw_adapter_output`. `key_hint` is content-addressed and filename-free (`object_key_must_not_include_original_filename=True`); bucket/prefix/endpoint are never echoed, only referenced by store ref. **Every field written passes `assert_no_secret_or_location_leak` (짠2.3) first.**

**Manifest location transition** (`objects/manifests/files.jsonl`, `update_allowed_only_after_provider_confirmation=True`, verified `45815`): `declared_uploaded ??wom_uploaded`, appending `execution_receipt_ref`, `uploaded_at`, flipping both `by_wom_kit` flags to `true`. `provider_url_must_not_be_recorded_publicly=True` ??no URL ever lands in the manifest.

**Doctor hook.** Register `_check_object_storage_execution_receipts` mirroring `_check_reconcile_receipts` (`archive_cli.py:1902`): validate against a new `object-storage-upload-receipt.schema.json`, require `dry_run:false` + non-empty `reviewed_by` on applied receipts, self-referentially check `receipt_path == display_path` (`1927`) to catch a copied/moved receipt, AND assert the digest invariant (짠3.3) on the recorded `key_hint` vs `object_id`.

---

## 5. FAILURE MODEL

House rule: **fail closed, always leave a receipt, evaluate all blockers before the first byte, roll back partial writes.** Live adapters wrap multi-file writes in try/except that unlinks every created path and cleans empty dirs on error (Notion, `22314`). **Every failure exit passes `assert_no_secret_or_location_leak` (짠2.3, RC4) and builds its receipt from the scalar allowlist (RC5).**

| Failure | Desired behavior |
|---|---|
| **Partial upload** (PUT starts, dies mid-object) | Single-part PUT is atomic at the provider (no partial object). For multipart, `partial_upload_cleanup_policy_required`: abort the multipart upload (cleanup) or record the upload-id in the resume ledger for resume. Manifest NOT advanced (no after-HEAD confirmation). Receipt: `result_status: failed_upload`, `object_uploaded:false`. |
| **Network drop mid-batch** | Resume ledger records each object's terminal state as it completes (scalar allowlist only). On re-run with `--skip-uploaded`, completed objects are `already_uploaded` (digest-aware Layer A) and skipped; the interrupted object is retried. `retry_policy=bounded_exponential_backoff_with_resume`, `default_concurrency=low`, `large_media_safe_mode`. No half-state in the manifest ??written per-object only after that object's after-HEAD. |
| **Auth failure** (bad/expired key) | Fail closed for the whole run before any object if the provider rejects credentials; receipt: `result_status: failed_auth` with **no** secret, no ref value, **no provider error body echoed** (raw provider error caught but never surfaced, per `22780`/`25532`; RC5 allowlist enforces this structurally). Key vars cleared in `finally`. |
| **Remote exists but different bytes** (짠3.1 Layer B) | **NEVER overwrite.** Skip that object, `result_status: remote_conflict_different_bytes`, mark for human review. Content-addressed keys mean same-key/different-bytes is a genuine anomaly, not a benign re-upload. |
| **Rate-limit (429 / throttle)** | Bounded exponential backoff with jitter, capped retry count; on exhaustion fail closed for that object (`result_status: failed_rate_limited`), resumable next run. `retry_summary` records only scalar counters. Low default concurrency to avoid inducing throttling on the 19k-object corpus. |
| **Cost blowout** (accidental mass upload) | Structural guards: `--max-objects` **REFUSES at the service layer** (RC6) if the plan exceeds the cap (a 19k plan cannot run behind a `--max-objects 1` intent, even via direct service/MCP call); tiny-first mandates one object for the first live release; `--skip-uploaded` prevents re-billing already-present objects. Receipt records `bytes_uploaded` + `object_count` for after-the-fact audit. No auto-retry loop that could silently multiply PUTs. |
| **Secret would appear in output** (new, RC1/RC4) | `assert_no_secret_or_location_leak` direct-value containment fires ??**hard abort before any write**, key cleared, `result_status: failed_secret_guard` (carries no secret). This is the last-line structural guarantee that no output path can exfiltrate the resolved key. |

---

## 6. TEST STRATEGY

**Temp-dir testable ??Stage 1 (fully) and Stage 2 (behavior minus the real wire):**
- The whole pre-wire pipeline (readiness ??operation-request ??execution-contract ??plan ??local-byte-verify) runs entirely on a temp archive with fixture manifests. Assert plan verdicts, `would_upload/already_uploaded` counts (including the **digest-aware** case: a same-store location with a DIFFERENT digest must verdict `would_upload`, not `already_uploaded` ??RC3), `--max-objects` REFUSE behavior **at the service layer** (RC6), and `local_byte_verification.verified` on both matching and deliberately-corrupted local bytes.
- **Secret-free proof (RC1/RC2) ??the load-bearing Stage-1 test.** Inject the TRUE credential shapes (64-hex R2 secret, 40-char AWS secret, B2 appKey) via `patch.dict(archive_services.os.environ, {...})` (`test_cli.py:4578`); run the full serialize-then-gate over receipt + ledger + manifest-delta + return payload + **every** `failed_*` branch; assert the raw value is absent everywhere AND that the test fails if control #1 (direct-value containment) is removed and only the regex backstop remains.
- **Stage 2 wire via injected fake transport (no server, no new dependency).** Factor the single urllib `PUT` behind a module-level `object_storage_put_object(...)` and a per-object executor `object_storage_execute_one_upload(...)` mirroring `notion_execute_one_ancestor_fetch_request` (`22266`). Tests `patch.object(archive_services, 'object_storage_put_object', side_effect=fake)` (`test_cli.py:1499`): the fake receives the same kwargs (including the resolved key), **asserts the credential was threaded correctly**, records `key/bytes/headers`, returns a canned `200` with ETag + `x-amz-checksum-sha256`. A companion fake `object_storage_head_object` returns `absent`/`present_same`/`present_different` to exercise all 짠3.1 branches; error-injecting fakes exercise every 짠5 row (auth, rate-limit, network drop, conflict, and a fake that returns a `SignatureDoesNotMatch?쪺tringToSign?? body ??RC5 ??asserting that body reaches NO durable field). Assert receipt facts, resume-ledger contents (scalar-only), manifest transition `declared_uploaded ??wom_uploaded`, and rollback on injected `OSError`.

**HONEST residual ??only a real endpoint proves these (ship with caveat):**
1. That hand-rolled **AWS SigV4** signing (if option A, 짠8) is byte-correct against a real R2/S3 authorizer ??a fake transport that echoes back cannot validate the signature.
2. That the real provider's `x-amz-checksum-sha256` / ETag / multipart behavior matches the assumed checksum policy (ETag-is-not-sha256, composite multipart ETags).
3. Real 429/throttle timing, TLS/endpoint quirks, and eventual-consistency of the after-HEAD.
4. Real cost accounting.

These four are exactly why Stage 2's live release is Kim-gated and validated tiny-first (one object, verified end-to-end, before the ~19k/158 GB run). The shipped doc and receipt carry `unproven_against_live_provider: true` until Kim confirms the first live object.

---

## 7. THREAT MODEL

| # | Threat | Vector | Mitigation |
|---|---|---|---|
| **T1** | **Secret leaks into a public record** | Resolved key ID/secret lands in receipt, manifest, resume ledger, blocker/warning, return payload, or a log line | **PRIMARY (RC1/RC4): direct constant-time containment** of both resolved key values against the fully-serialized output on EVERY exit path, hard-abort `failed_secret_guard` on any hit ??this catches the 64-hex R2 / 40-char AWS secret the regexes miss. Keys read only under `if approve and not blockers`, held in locals, `finally: key=None` (`25880`). Backstop: `DRAFT_SECRET_VALUE_RE` + `GITHUB_SECRET_LIKE_RE` + `contains_forbidden_location_reference` (all three, negative). `privacy_guards.*_echoed:false`. `receipt_contract.must_not_include` (verified `45805`). Stage-1 test injects the TRUE secret shapes and asserts absence (RC2). |
| **T2** | **Bucket URL / local path leaks** (deanonymizes the archive) | Provider URL or `C:\??/UNC path echoed in receipt or manifest | `contains_forbidden_location_reference` (`paths.py:142`, `PROVIDER_URL_RE` `s3\|b2\|r2\|gs://`, `LOCAL_ABSOLUTE_REFERENCE_RE`) as a hard negative gate inside `assert_no_secret_or_location_leak`; endpoint stays a `provider:endpoint:<kind>` ref (`47796`); `key_hint` content-addressed and filename-free; `provider_url_must_not_be_recorded_publicly=True` (`45827`). |
| **T3** | **Remote data corruption / overwrite** | Same content-addressed key already holds *different* bytes; adapter overwrites | HEAD-before-upload; `remote_present_different` ??**fail closed, never PUT** (짠5); content-addressing makes same-key-different-bytes a genuine anomaly flagged for human review. |
| **T4** | **Wrong bytes uploaded** (local file drifted from object_id) | Local bytes no longer hash to `object_id` | `local_object_sha256_must_match_object_id_before_upload=True` ??`sha256_path` over RAW bytes must equal `object_id` or block; after-HEAD confirms remote size+checksum; `byte_verification_by_wom_kit` set true only after the local proof. |
| **T5** | **Cost blowout** | AI or operator accidentally triggers a 19k/158 GB mass upload | **`--max-objects` REFUSES at the SERVICE layer (RC6)** ??un-bypassable via direct service/MCP call; tiny-first mandates one object for first live release; `--skip-uploaded` (digest-aware) prevents re-billing; bounded retry (no runaway loop); receipt records `object_count`+`bytes_uploaded`. |
| **T6** | **AI agent uploads without genuine human intent** ??the core #11 concern | Agent calls the mutating command with `--approve`, or drives a raw provider MCP | (a) **Not an MCP the AI drives** ??WOM-kit CLI with explicit human `--approve` gate (Kim's decision). (b) Three-way gate at BOTH CLI and service layers (`8470`, `62964`). (c) `--approve` requires `--reviewed-by` as a safe actor id, recorded as the only identity. (d) `live_execution_allowed_now` stays false through all planners; only `object-storage-upload --approve` crosses the wire. (e) First live release Kim-gated, not auto-released. (f) `default_concurrency=low` + tiny-first bound blast radius. |
| **T7** | **Forged receipt / tamper** | Local actor with write access recomputes a sha and rewrites both bytes and receipt | HONEST LIMIT (confirmed): **no cryptographic signature** anywhere in WOM ??every `signature_created` is hardcoded `False`, no hmac/gpg/ed25519. Tamper-**EVIDENT** (sha content-addressing, prior?뭤ew chaining, append-only monotonic-suffixed immutable receipts, doctor self-referential `receipt_path` check `1927`), NOT tamper-**PROOF** against a motivated local editor. Stated residual (짠9-R3), not a mitigated threat. |
| **T8** | **Credential-store confusion / unsupported store silently no-ops** | `secret:`/`wallet:` ref passes shape check but has no resolver; or `keyring:` used at first live | `resolve_credential_value` blocks on unsupported stores (`25486`); **first live release additionally restricted to `env:` only via an explicit service-layer blocker BEFORE resolution (RC7)**, failing closed rather than proceeding with an unresolved or not-yet-proven key path. |
| **T9** | **Provider error / SigV4 material leaks** | Raw HTTPError/URLError body, or a `SignatureDoesNotMatch` body echoing `StringToSign`/`CanonicalRequest`, surfaced in receipt/ledger/stderr | **RC5: receipt + ledger built from a fixed scalar allowlist, never from caught exception args**; provider errors caught and never echoed (`22780`/`25532`); receipt records only a `result_status` class; explicitly forbidden: request headers, `Authorization`, `StringToSign`, `CanonicalRequest`, provider error body, `raw_adapter_output`. Verified that a `SignatureDoesNotMatch?쪺tringToSign?? body passes both regexes clean, so the allowlist (not the scanner) is the guarantee. |
| **T10** | **ETag mistaken for content hash** ??false "confirmed" on differing bytes | Multipart/composite ETag treated as sha256, passing a bogus match | ETag NOT treated as sha256 unless provider policy verified; prefer `x-amz-checksum-sha256`; explicit multipart/large-object checksum policy; this correctness point is on the "only a real endpoint proves" residual (짠6.2), reinforcing the Kim-gate. |
| **T11** | **Digest-blind false skip** (new, RC3) | A same-store `object_storage` location with a *different* digest causes `--skip-uploaded` to skip an un-uploaded object, or to advance a manifest location whose key_hint ??record's object_id | **Idempotency matches on `key_hint` digest == planned `object_id` digest (짠3.1), not just `(provider_kind, store_ref)`; audit asserts every location's key digest == its record's object_id (짠3.3); doctor re-checks the invariant (짠4).** Closes the false-skip / mismatched-advance hole at plan, audit, and doctor layers. |

---

## 8. STAGE / BATCH LADDER

Each commit is one atomic batch touching paired EN/KO docs + README/CHANGELOG/UPGRADE per the house workflow. "Auto" = tests-pass auto-release; "Kim-gate" = explicit go required.

| Batch | Ships | Wire? | Release |
|---|---|---|---|
| **B1 ??schema + credential model** | Extend `build_object_storage_provider_binding` (`47865`) with `access_key_id_ref` + `secret_access_key_ref` (both via `safe_credential_ref`); generalize `tiro_read_credential_value` ??shared `resolve_credential_value` (`25456`); no new command yet. Docs: binding schema, credential model. | No | **Auto** |
| **B2 ??`object-storage-upload-plan`** | Read-only planner composing readiness?뭨equest?뭖ontract + **digest-aware** idempotency verdict + credential store-class check + **service-layer `--max-objects` REFUSE**. Writes nothing. | No | **Auto** |
| **B3 ??`object-storage-upload-verify` + the secret-free control** | Read-only local-byte verification (`sha256_path` RAW bytes == object_id); **`assert_no_secret_or_location_leak` with direct-value containment (RC1/RC4) and the secret-free-output test injecting the TRUE R2/AWS secret shapes (RC2)**. Writes nothing. **This batch ships the load-bearing safety control; it is auto-releasable ONLY because that control is now sound and directly tested.** | No | **Auto** |
| **B4 ??execution-receipt writer + resume ledger + `wom_uploaded` variant + audit/doctor extension** | Execution receipt writer (**allowlist-built, RC5**), `<case-id>.resume-ledger.jsonl` (allowlist-built), new `wom_uploaded` availability + extended `object_storage_upload_evidence_audit_location_errors` (`41550`) including the **digest invariant (RC3)**, new schema + `_check_object_storage_execution_receipts`. Exercised **against injected fake transport** ??no real wire. | No (fake) | **Auto** |
| **B5 ??`object-storage-upload` dry-run + Stage-2 wire behind `--approve`, transport stubbed off by default** | The command with full three-way gate; `object_storage_put_object` / `head_object` module seams + per-object executor; SigV4 signing; **env-only-first-live service-layer blocker (RC7)**; the live PUT path fully implemented but only reachable via `--approve`. All 짠5 failure branches (incl. `SignatureDoesNotMatch` body, `failed_secret_guard`) tested via fakes. Ships with `unproven_against_live_provider: true`. | Yes (code present) | **Auto for the code**; `--approve` live use is **Kim-gate** |
| **B6 ??FIRST LIVE OBJECT (tiny-first validation)** | No code ??an operational milestone. Kim runs `object-storage-upload --only sha256:<one> --max-objects 1 --reviewed-by kim --approve` against the real R2 endpoint, verifies the execution receipt + manifest transition + remote after-HEAD by hand. On success, flip the doc caveat to `proven_against_live_provider: cloudflare-r2, one object`. | Yes (real) | **Kim-gate (explicit go)** |
| **B7 ??bounded batch enablement** | Only after B6: raise `--max-objects` beyond 1, keep `--skip-uploaded` (digest-aware) + resume ledger, run the ~19k/158 GB corpus in bounded, resumable slices. | Yes (real) | **Kim-gate per slice** |

**Transport-signing choice (B5), reported not decided.** WOM is strictly dependency-light (PyYAML only; live HTTP hand-rolled `urllib.request`; **no boto3**). Three house-consistent options for SigV4:
- **(A) stdlib-only SigV4-by-hand** ??`hashlib.sha256` + `hmac` (stdlib) to build the `Authorization` header, then the same `urllib.request` PUT pattern as Notion/Tiro. Zero new deps; residual 짠6.1 (signing correctness) sits on the Kim-gate. **Note: with option A the RC5 error-body allowlist is load-bearing ??a signing bug makes the provider reflect `StringToSign` in the error body.**
- **(B) lazy-optional boto3** behind an `importlib.util.find_spec` probe ??core stays dep-free, boto3 only required when the user opts in.
- **(C) pluggable transport** ??user supplies the upload callable/command (their existing `aws`/`rclone`/boto3 script); WOM only orchestrates approval/receipt/verification. Closest to the stated rationale ("WOM users already hand-roll boto3 upload scripts").
Kim's call at B5; the design is transport-agnostic (everything routes through the `object_storage_put_object` seam), so the choice does not change the surface, receipts, or threat model.

---

## 9. Known residual risks (accepted / carried forward)

Nothing hidden. These are stated plainly; none is silently mitigated.

- **R1 ??Secret-free guarantee is only as good as the direct-value control.** With RC1/RC2/RC4 adopted, the guarantee is now sound (direct constant-time containment of the actual resolved key, tested against the TRUE secret shapes). The residual is that this control MUST land and be tested in B3 exactly as specified; if an implementer reverts to a regex-only check, the hole re-opens silently. **Mitigation baked in:** the B3 test must FAIL if only the regex backstop is present. Status: **mitigated in design, contingent on faithful B3 implementation.**
- **R2 ??SigV4 signing correctness is temp-dir-unprovable (짠6.1).** A signing bug can make the provider reflect signing material in an error body. **Mitigated** by the RC5 allowlist (error bodies never reach disk) + Kim-gated tiny-first live validation. Residual: correctness itself is only proven at B6.
- **R3 ??Tamper-EVIDENT, not tamper-PROOF (T7).** No hmac/gpg/ed25519 anywhere; every `signature_created` is hardcoded `False`. A local actor with write access can forge a matching sha + receipt, so `reviewed_by: kim` and `proven_against_live_provider` are advisory, not cryptographically bound. **Accepted** for the solo-author trust model. **Carried-forward trigger:** if #11 ever gains multi-operator or shared-credential use, one operator could forge another's approval ??re-open this before widening the trust boundary.
- **R4 ??Digest-blind idempotency at batch scale (RC3).** The false-skip risk (believing a backup exists when the object was never PUT) is a data-availability risk distinct from T3 corruption. Tiny-first does NOT catch it (the first object is uploaded fresh); the hole would open at B7 batch scale. **Mitigated in design** by digest-aware Layer A + the 짠3.3 audit digest invariant + the doctor re-check. Residual: relies on those three landing in B2/B4 as specified.
- **R5 ??Cost-blowout depends on the service-layer REFUSE (RC6).** If an implementer places the REFUSE at the CLI only, a direct service/MCP call could plan 19k behind a `--max-objects 1` intent; financial blast radius (R2 Class-A operation billing on 19k PUTs) is real even though content-addressing prevents corruption. **Mitigated in design** (service-layer enforcement, tested in B2). Residual: implementation-fidelity.
- **R6 ??Reliability review gap.** The reliability red-team returned a non-substantive stub (`verdict:"test"`, findings `["a"]`, risks `["b"]`) ??it produced no analysis of concurrency, resume-ledger correctness under interleaved failures, `os.replace` durability on Windows, partial-multipart cleanup semantics, or clock/`case-id` collision. **NOT mitigated ??it was never actually reviewed.** Accepted for the design lock (Stage-1 has no wire and no concurrency), but a real reliability pass MUST run before B4/B5 code lands, specifically on: resume-ledger idempotency under interleaved partial failures, monotonic-suffix collision under concurrent runs, and multipart abort/cleanup correctness.

---

**Key reused primitives (resolve by symbol at `a5425b62`):** `object_storage_adapter_execution_contract` `archive_services.py:45650` (the spec); `object_storage_upload_evidence_location_exists` `:41192` (digest-blind ??wrap, do not reuse verbatim, RC3); `update_manifest_with_object_storage_upload_evidence` `:41234`; `object_storage_upload_evidence_location` `:41211`; `object_storage_upload_evidence_audit_location_errors` `:41550` (audit to extend, + digest invariant); `resolve_objet_ref` `:55139`; `object_storage_context` `:55080`; `sha256_path` `:58848` (RAW-byte verify); `tiro_read_credential_value` `:25456` ??shared `resolve_credential_value` (NEW); `safe_credential_ref` `:39872` / `credential_ref_store` `:39864` / `CREDENTIAL_REF_PREFIXES` `:1806`; `tiro_lossless_recovery_fetch_run` `:25616` (approval-gate template); `_atomic_write_json` `:9346` (durable write); `DRAFT_SECRET_VALUE_RE` `:1479` / `GITHUB_SECRET_LIKE_RE` `:1633` / `contains_forbidden_location_reference` `paths.py:142` (leak scanners ??BACKSTOP ONLY, do NOT catch the R2/AWS secret); `notion_execute_one_ancestor_fetch_request` `:22266` (per-object executor pattern); `command_remint_reconcile` `archive_cli.py:8470` / `command_objet_capture` `:9000` (three-way gate); `doctor._check_reconcile_receipts` `archive_cli.py:1902` (doctor hook pattern). Test seams: `patch.object(archive_services,'object_storage_put_object',...)` + `patch.dict(os.environ,...)` per `tests/test_cli.py:1499,4578`. NEW symbols: `resolve_credential_value`, `object_storage_put_object`, `object_storage_head_object`, `object_storage_execute_one_upload`, `assert_no_secret_or_location_leak`, `_check_object_storage_execution_receipts`.

**Empirical verifications performed against `a5425b62` before locking:** (1) `DRAFT_SECRET_VALUE_RE` (1480) and `GITHUB_SECRET_LIKE_RE` (1634) confirmed to miss a bare 64-hex R2 / 40-char AWS secret and catch only labelled secrets + `AKIA`/`ghp_`/`sk-`/PEM ??the security red-team's central claim is CORRECT (RC1). (2) `object_storage_upload_evidence_location_exists` (41198??1208) confirmed digest-blind (RC3). (3) Repo HEAD confirmed `a5425b62`, not v0.3.162 (RC8).

**Design residuals stated plainly:** (1) the secret-free guarantee is now sound but contingent on the direct-value control landing faithfully in B3 (R1); (2) SigV4 signing correctness, real checksum/ETag/multipart behavior, real throttle timing, and cost are unprovable in temp dirs and are exactly what B6's tiny-first Kim-gate exists to prove (R2); (3) tamper-evident, not tamper-proof (R3); (4) reliability was never actually reviewed ??a real pass is required before B4/B5 (R6).

---

## 10. Reliability / cost red-team — 2nd pass (folded in 2026-07-03)

The 1st-pass reliability red-team returned a stub; §9 flagged this and required a real pass
before Stage-2 code. That pass ran and is folded in here. (Its "design is truncated / §§5-9
missing" meta-finding was an artifact of a botched doc extraction, now fixed — §§5-9 are present.
The code-grounded findings below stand regardless and were verified against HEAD a5425b62.)

### Real gaps to close in the Stage-1/Stage-2 implementation (blocker-class)

- **R4 — manifest write is non-atomic and unlocked (highest reliability gap).**
  `update_manifest_with_object_storage_upload_evidence` (archive_services.py:41234) ends in a bare
  `manifest_path.write_text(...)` (:41274) — no temp+fsync+os.replace, and it does NOT acquire
  `_ObjetCaptureManifestLock` (:61406) that the objet-capture append path uses on the same
  `objects/manifests/files.jsonl`. A crash mid-write or a concurrent capture corrupts ALL ~19k
  records, not just the object being uploaded. FIX: the adapter's manifest transition MUST (a) acquire
  `_ObjetCaptureManifestLock` and (b) write via temp+fsync+os.replace. Applies to Stage 1 as soon as
  the adapter touches the manifest.
- **R1 — `--skip-uploaded` must honor ONLY provider-confirmed `wom_uploaded` locations.** It must NOT
  skip on `declared_uploaded` (external evidence = a claim, not a WOM proof) nor on a manifest-only hit
  without a Layer-B remote HEAD. This client has 19k `declared_uploaded` external-evidence records, so a
  manifest-only/declared skip = silently never uploading objects that were never actually WOM-uploaded
  (or skipping ones deleted out-of-band from R2). Layer A gates COST; only a Layer-B `remote_present_same`
  HEAD may gate CORRECTNESS.
- **R3 — no crash-safe append primitive exists in the codebase.** Every `.jsonl` writer is whole-file
  replace; there is no fsync'd append. The "append-only resume ledger" has no primitive to lean on.
  FIX: either specify append(full line)+flush+os.fsync(fileno)+tolerate-a-trailing-torn-line-on-read,
  OR make each object's completion its own atomic-written file. The ledger MUST be READ on every re-run
  and is authoritative for "PUT already succeeded," independent of the manifest (which is written last).
- **R6 — multipart after-check needs a concrete algorithm.** ETag ≠ sha256 for multipart; any object
  >5 GB must be multipart. FIX: define the multipart threshold + require full-object SHA-256 checksum
  mode (or per-part verification / re-download-and-hash); if the provider cannot return a whole-object
  sha256, the object FAILS — never pass on size alone.

### Tiny-first must become a tiered gate (R9)

One small object exercises none of the risks that matter for 19k/158 GB. The Stage-2 live acceptance
gate is tiered, each tier Kim-visible: (1) one small object; (2) one object above the multipart
threshold; (3) ~10-object batch with a deliberate mid-batch abort to prove the manifest lock + resume;
(4) a `--skip-uploaded` re-run against the real manifest to prove no `declared_uploaded` false-skip;
only then (5) the full set.

### Accepted residual risks (explicit — carried by `unproven_against_live_provider: true`)

1. Provider durability after 200/HEAD-OK is trusted, not proven (after-HEAD proves visibility only).
2. Fake-transport cannot prove real R2 behavior (multipart checksums, SigV4 error bodies, throttling,
   partitions, read-after-write consistency) — these are only ever OBSERVED via the tiered live rollout,
   never unit-tested pre-release.
3. Out-of-band remote mutation (delete/overwrite in R2 outside WOM) leaves WOM's manifest stale; only a
   full Layer-B HEAD sweep (not `--skip-uploaded`) detects it.
4. Aborted-multipart parts accrue R2 storage cost until aborted — the contract's
   `partial_upload_cleanup_policy_required` must be given a concrete abort/cleanup step.
5. Tamper-evident, not tamper-proof: no hmac/gpg/ed25519; a local actor with archive write access can
   forge a matching sha + receipt. `reviewed_by`/`proven_against_live_provider` are advisory, not
   cryptographically bound.

### Genuinely mitigated by the design as written (confirmed)

RC3 digest-blindness (§3.3 + audit invariant); before-hash on RAW bytes (§3.2); scalar-only allowlist
`retry_summary`/ledger (§4/RC5); service-layer `--max-objects` REFUSE and env-only-first-live
(RC6/RC7, precedents real at 22229). §5 retry policy and §7 threat matrix exist and were NOT re-attacked
in this pass beyond the items above — a focused re-read of §5's retry ceiling against R7 is a Stage-2
pre-code checklist item.
