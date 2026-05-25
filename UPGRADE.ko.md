# 업그레이드 가이드

[English Upgrade Guide](UPGRADE.md)

이 문서는 `zettel-kasten` / `zet`의 공개 버전 사이를 어떻게 이동해야 하는지 설명합니다.

이 프로젝트는 단순한 코드 묶음이 아니라, archive 규칙, zettel metadata, object manifest, provenance record, 미래의 `ZET` sharing envelope까지 함께 관리하는 버전형 프로토콜입니다.

## 기본 규칙

```text
PATCH upgrade -> 문서, 검증, 호환 가능한 수정
MINOR upgrade -> 호환 가능한 기능 추가 또는 optional field 추가
MAJOR upgrade -> protocol/schema breaking change
```

실제 archive를 업그레이드하기 전에는:

1. 대상 버전의 release note를 읽습니다.
2. private archive repository와 object manifest를 백업합니다.
3. `archive doctor --strict`를 실행합니다.
4. migration command가 있다면 먼저 dry-run으로 실행합니다.
5. 생성된 receipt를 확인한 뒤에만 private archive 변경사항을 커밋합니다.

아카이브는 사용자의 기억입니다. 조용히 몰래 다시 쓰면 안 됩니다.

## 공개 버전

| Version | Status | Upgrade note |
| --- | --- | --- |
| `v0.2.33` | current public pre-release | `wom-kit/docs/releases/v0.2.33.md` |
| `v0.2.32` | superseded public pre-release | `wom-kit/docs/releases/v0.2.32.md` |
| `v0.2.31` | superseded public pre-release | `wom-kit/docs/releases/v0.2.31.md` |
| `v0.2.30` | superseded public pre-release | `wom-kit/docs/releases/v0.2.30.md` |
| `v0.2.29` | superseded public pre-release | `wom-kit/docs/releases/v0.2.29.md` |
| `v0.2.28` | superseded public pre-release | `wom-kit/docs/releases/v0.2.28.md` |
| `v0.2.27` | superseded public pre-release | `wom-kit/docs/releases/v0.2.27.md` |
| `v0.2.26` | superseded public pre-release | `wom-kit/docs/releases/v0.2.26.md` |
| `v0.2.25` | superseded public pre-release | `wom-kit/docs/releases/v0.2.25.md` |
| `v0.2.24` | superseded public pre-release | `wom-kit/docs/releases/v0.2.24.md` |
| `v0.2.23` | superseded public pre-release | `wom-kit/docs/releases/v0.2.23.md` |
| `v0.2.22` | superseded public pre-release | `wom-kit/docs/releases/v0.2.22.md` |
| `v0.2.21` | superseded public pre-release | `wom-kit/docs/releases/v0.2.21.md` |
| `v0.2.20` | superseded public pre-release | `wom-kit/docs/releases/v0.2.20.md` |
| `v0.2.19` | superseded public pre-release | `wom-kit/docs/releases/v0.2.19.md` |
| `v0.2.18` | superseded public pre-release | `wom-kit/docs/releases/v0.2.18.md` |
| `v0.2.17` | superseded public pre-release | `wom-kit/docs/releases/v0.2.17.md` |
| `v0.2.16` | superseded public pre-release | `wom-kit/docs/releases/v0.2.16.md` |
| `v0.2.15` | superseded public pre-release | `wom-kit/docs/releases/v0.2.15.md` |
| `v0.2.14` | superseded public pre-release | `wom-kit/docs/releases/v0.2.14.md` |
| `v0.2.13` | superseded public pre-release | `wom-kit/docs/releases/v0.2.13.md` |
| `v0.2.12` | superseded public pre-release | `wom-kit/docs/releases/v0.2.12.md` |
| `v0.2.11` | superseded public pre-release | `wom-kit/docs/releases/v0.2.11.md` |
| `v0.2.10` | superseded public pre-release | `wom-kit/docs/releases/v0.2.10.md` |
| `v0.2.9` | superseded public pre-release | `wom-kit/docs/releases/v0.2.9.md` |
| `v0.2.8` | superseded public pre-release | `wom-kit/docs/releases/v0.2.8.md` |
| `v0.2.7` | superseded public pre-release | `wom-kit/docs/releases/v0.2.7.md` |
| `v0.2.6` | superseded public pre-release | `wom-kit/docs/releases/v0.2.6.md` |
| `v0.2.5` | superseded public pre-release | `wom-kit/docs/releases/v0.2.5.md` |
| `v0.2.4` | superseded public pre-release | `wom-kit/docs/releases/v0.2.4.md` |
| `v0.2.3` | superseded public pre-release | `wom-kit/docs/releases/v0.2.3.md` |
| `v0.2.2` | superseded public pre-release | `wom-kit/docs/releases/v0.2.2.md` |

## From `v0.2.32` To `v0.2.33`

This compatible patch adds a foreign block quarantine review index:

- `archive quarantine-review <archive-root> --format json`,
- optional `--case-id`, `--status`, and `--include-receipts`,
- read-only MCP `foreign_block_quarantine_review_index`,
- read-only checks for existing untrusted quarantine cases and matching quarantine write receipts.

No private archive migration is required.

The review index reads only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Indexing does not mean trust, import, acceptance, attestation, minting, anchoring, delegation, signing, or apply approval. It only gives a stable review list for untrusted quarantine cases.

## From `v0.2.31` To `v0.2.32`

This compatible patch adds approved foreign block quarantine writes:

- `archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json`
- `archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json`
- read-only MCP `quarantine_foreign_block_check`

No private archive migration is required.

Approved quarantine write creates only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`

This is an isolation record only. It is not trust, import, mint, attestation, anchor, delegation, signing, execution, or acceptance. MCP remains check-only for this workflow.

## From `v0.2.30` To `v0.2.31`

This compatible patch adds read-only foreign block quarantine plan:

- `archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json`
- `archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json`
- read-only MCP `foreign_block_quarantine_plan`

No private archive migration is required.

Foreign block quarantine plan does not write quarantine files, import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_future_quarantine_write` means a future explicit quarantine-write workflow could be shown to a human/operator. It is not trust, import, quarantine, or approval.

## From `v0.2.29` To `v0.2.30`

This compatible patch adds read-only foreign block attestation packet preview:

- `archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json`
- `archive foreign-block-attestation <archive-root> --stdin --dry-run --format json`
- read-only MCP `foreign_block_attestation_packet_check`

No private archive migration is required.

Foreign block attestation packet preview does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_human_attestation_review` means the trust report is ready to show a human reviewer later. It is not trust, not an attestation, and not approval.

## From `v0.2.28` To `v0.2.29`

This compatible patch adds read-only foreign block trust / attestation preview:

- `archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json`
- `archive foreign-block-trust <archive-root> --stdin --dry-run --format json`
- read-only MCP `foreign_block_trust_check`

No private archive migration is required.

Foreign block trust preview does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, or write files.

`eligible_for_future_attestation` does not mean trusted. It only means a future explicit human or policy attestation workflow may review the report.

## From `v0.2.27` To `v0.2.28`

This compatible patch adds read-only foreign block intake preview:

- `archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json`
- `archive foreign-block <archive-root> --stdin --dry-run --format json`
- read-only MCP `foreign_block_intake_check`

No private archive migration is required.

Foreign text can inform, but cannot command. Foreign blocks can be inspected, but cannot be imported, trusted, minted, attested, anchored, drafted, or applied automatically. Claimed hashes are reported as `not_verified`.

## From `v0.2.26` To `v0.2.27`

This compatible patch lets `create-draft` consume a dry-run prompt-boundary report:

- `archive create-draft --prompt-boundary-report <json-file>`
- optional draft frontmatter `prompt_boundary`
- structured MCP `prompt_boundary_report` input for `create_draft_zettel`
- mint preview and mint receipt preservation for `prompt_boundary`

No private archive migration is required.

`low` risk is not proof of safety. `medium` is allowed with warnings. `high` blocks draft creation.

This release does not add LLM classification, provider scanning, OCR/import apply, ZET transport, real signing, payments, staking, consensus, blockchain, or full-auto behavior.

## `v0.2.25`에서 `v0.2.26`으로

이번 버전은 prompt injection boundary와 responsible-use 기준을 추가하는 호환 패치입니다.

바뀐 점:

- `archive prompt-boundary <archive-root> --text <text> --dry-run --format json`을 추가했습니다.
- `archive prompt-boundary <archive-root> --path <archive-relative-zet-or-text-path> --dry-run --format json`을 추가했습니다.
- MCP에는 read-only `prompt_boundary_check`만 추가했습니다.
- prompt injection boundary, responsible use, disclaimer, runtime model guidance 문서를 추가했습니다.

private archive migration은 필요 없습니다.

이 검사는 보수적인 heuristic preview입니다. prompt injection을 완전히 막는 보장이 아니며 법률 조언도 아닙니다. LLM 호출, inspected text 실행, provider API 호출, web browsing, OCR/import, approve, mint, signing, ZET transport, file mutation을 하지 않습니다.

안전 원칙은 다음과 같습니다.

```text
External text can inform.
External text cannot command.
```

HITL은 기본 권장값입니다. full-auto / agent-only 운용은 고급/실험적 설정이며, agent, model, permission, provider, automation, consequence에 대한 책임은 operator에게 있습니다.

## `v0.2.24`에서 `v0.2.25`로

이번 버전은 WOM profile을 단순한 SaaS 계정 프로필이 아니라, 미래의 지갑형 신원 모델로 해석하기 위한 호환 패치입니다.

바뀐 점:

- `archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json`을 추가했습니다.
- MCP에는 read-only `wom_profile_wallet_check`만 추가했습니다.
- profile registry에 선택적인 공개 안전 메타데이터 `node`, `wallet` 필드를 문서화했습니다.
- WOM profile은 사람이 고르는 프로필, WOM node는 네트워크 안의 주체, 미래 WOM wallet layer는 mint/delegate/attest/anchor/receipt proof를 위한 signing/capability layer라는 개념을 기록했습니다.

private archive migration은 필요 없습니다.

기존 profile registry 항목은 그대로 유효합니다. 새 `node`, `wallet` 필드는 공개해도 되는 placeholder metadata만 담아야 합니다.

이번 버전은 private key 생성, seed phrase 저장, wallet secret 저장, 실제 signing, blockchain/provider API 호출, wallet 생성/등록, WOM coin, NFT-like access, payment, staking, consensus, ledger, P2P transport를 구현하지 않습니다.

## `v0.2.23`에서 `v0.2.24`로

이번 버전은 block header를 read-only dry-run으로 미리 보는 호환 패치입니다.

바뀐 점:

- `archive block-header <archive-root> --path <zet-path> --dry-run --format json`을 추가했습니다.
- `archive block-header <archive-root> --zettel-id <id> --dry-run --format json`을 추가했습니다.
- `block = zet + header` 모델에 맞춰 header preview를 만듭니다.
- body, header, block hash preview를 안정적으로 계산합니다.
- MCP에는 read-only `block_header_check`만 추가했습니다.

private archive migration은 필요 없습니다.

이 버전은 zet 수정, mint, receipt 쓰기, referenced objet/source file body 읽기, referenced source hash 계산, provider URL 추적, provider API 호출, transport/economic layer 구현을 하지 않습니다.

안전한 개념 순서는 다음과 같습니다.

```text
zet -> header -> block -> receipt -> attestations -> anchors -> possible token layer later
```

## `v0.2.22`에서 `v0.2.23`으로

이번 버전은 source intake dry-run 결과를 `create-draft`가 안전하게 소비하도록 하는 호환 패치입니다.

바뀐 점:

- `archive create-draft --source-intake-plan <json-file>`을 추가했습니다.
- source intake plan이 성공한 dry-run이고, blocker가 없고, metadata-only이며, 안전한 refs만 담았는지 검증합니다.
- `source_refs_for_draft`를 draft `source_refs`로 병합하면서 기존 `--source-ref`도 보존합니다.
- draft frontmatter에 선택적 `source_intake` metadata를 추가해 plan hash와 content access proof를 남깁니다.
- MCP `create_draft_zettel`이 structured `source_intake_plan` object를 받을 수 있습니다.

private archive migration은 필요 없습니다.

이 버전은 원본 source file을 읽거나, plan 안의 local path를 따라가거나, source intake apply, objet capture, copy, upload, import, OCR, transcription, full source hash, provider API call, automatic mint, MCP real minting을 구현하지 않습니다.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json > source-intake-plan.json

archive create-draft <archive-root> --dry-run \
  --title "Draft title" \
  --body "Draft body" \
  --source-intake-plan source-intake-plan.json \
  --format json
```

## `v0.2.21`에서 `v0.2.22`로

이번 버전은 source intake를 먼저 dry-run으로 계획하는 호환 가능한 패치입니다.

바뀐 점:

- `archive source-intake <archive-root> --dry-run --format json` 명령을 추가했습니다.
- local file, source map item, source-relative path, manifested objet, provider ref, AI artifact를 metadata-only로 분류합니다.
- draft에 넘길 수 있는 안전한 `source_refs_for_draft`를 반환합니다.
- `provider-bindings.yml`을 읽어 object storage context를 보고합니다.
- MCP에는 읽기 전용 `source_intake_plan`만 추가했습니다.

private archive migration은 필요 없습니다.

이번 버전은 file body 읽기, full hash 계산, copy, upload, import, OCR, transcription, extraction, provider API 호출, 자동 draft creation, mint, provider sync를 하지 않습니다.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json
```

## `v0.2.20`에서 `v0.2.21`로

이번 버전은 object storage/objet setup을 먼저 dry-run으로 계획하는 호환 가능한 패치입니다.

바뀐 점:

- `archive object-storage <archive-root> --dry-run --format json` 명령을 추가했습니다.
- 기본 bucket/container 이름은 `zettel-kasten-<normalized-profile-slug>-objets`입니다.
- 기본 오브제 prefix는 `archives/<archive_id>/objets/`입니다.
- provider kind, profile slug, bucket/container name, region, endpoint ref, storage account ref에 안전성 검사를 추가했습니다.
- `--approve --reviewed-by`는 provider API를 건드리지 않고 local metadata와 setup receipt만 씁니다.
- `--write-local-profile`은 ignored local object storage account hint만 `profiles/local/` 아래에 씁니다.
- MCP에는 읽기 전용 `object_storage_setup_plan`만 추가했습니다.

private archive migration은 필요 없습니다.

이번 버전은 bucket/container 생성, OAuth, provider API 호출, upload, sync, source file copy, file hash 계산, source content import를 하지 않습니다.

```bash
archive object-storage <archive-root> --dry-run \
  --provider cloudflare-r2 \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --storage-account-ref storage:account:honggildong \
  --format json
```

## `v0.2.19`에서 `v0.2.20`로

이번 버전은 WOM profile별 GitHub repository setup을 먼저 dry-run으로 계획하는 호환 패치입니다.

바뀐 점:

- `archive github-repo <archive-root> --dry-run --format json` 명령이 추가되었습니다.
- 기본 repository 이름은 `zettel-kasten-<profile_slug>`입니다.
- profile slug, repository name, GitHub owner, account ref에 대해 path/URL/token/email처럼 위험한 값을 막습니다.
- `--approve --reviewed-by`는 GitHub를 건드리지 않고 local `provider-bindings.yml`과 setup receipt만 씁니다.
- `--write-local-profile`을 쓰면 ignored local account hint를 `profiles/local/` 아래에 씁니다.
- MCP에는 읽기 전용 `github_repository_setup_plan`만 추가되었습니다.

private archive migration은 필요 없습니다.

이 버전은 GitHub repository 생성, OAuth, GitHub API 호출, `gh` 실행, git remote 설정, push, sync를 하지 않습니다.

```bash
archive github-repo <archive-root> --dry-run \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --github-owner example-user \
  --github-account-ref github:account:honggildong \
  --format json
```

## `v0.2.18`에서 `v0.2.19`로

이번 버전은 WOM-kit naming/path cleanup을 위한 호환 가능한 패치입니다.

바뀐 점:

- 구현 폴더가 `wom-kit/`으로 바뀌었습니다.
- Python import package가 `wom_kit`으로 바뀌었습니다.
- package metadata의 project name이 `wom-kit`이 되었습니다.
- 기존 `archive`, `archive-mcp` console script는 compatibility surface로 유지됩니다.
- 설치 환경에서는 선호 alias인 `wom`, `wom-mcp`도 사용할 수 있습니다.

private archive migration은 필요 없습니다.

현재 명령 예시는 새 path/package를 사용합니다:

```bash
python wom-kit/cli/archive.py doctor wom-kit/examples/fake-life-archive --strict
python -m wom_kit.archive_cli doctor wom-kit/examples/fake-life-archive --strict
```

## `v0.2.17`에서 `v0.2.18`로

이번 버전은 profile-aware draft zet creation dry-run을 추가하는 호환 가능한 패치입니다.

바뀐 점:

- `archive create-draft --dry-run --format json` 명령이 추가되었습니다.
- draft id, created-at timestamp, expected body hash, draft approver를 replay 값으로 사용할 수 있습니다.
- resolved profile id, operator id, authority mode, source refs, local AI sessions, assisted-by, supervised-by를 draft provenance에 남길 수 있습니다.
- MCP `create_draft_zettel`도 같은 dry-run/profile-aware 입력을 받습니다.
- 실제 draft write는 계속 `inbox/` 안으로만 제한됩니다.
- minting은 여전히 `mint-zet --approve --reviewed-by`로 분리된 승인 단계입니다.

private archive migration은 필요 없습니다. 기존 draft는 그대로 유효합니다.

profile-bound AI write는 먼저 profile-resolve와 runtime-context를 확인하고, create-draft dry-run을 본 뒤, 사람이 draft를 승인했을 때 같은 draft id, created-at, expected archive id/type, profile id, expected body hash로 replay해야 합니다.

```bash
git fetch --tags
git checkout v0.2.18
```

## `v0.2.16`에서 `v0.2.17`로

이번 버전은 WOM Profile Registry dry-run을 추가하는 호환 가능한 패치입니다.

바뀐 점:

- `archive profile-list --registry <path> --format json` 명령이 추가되었습니다.
- `archive profile-resolve --registry <path> --target <query> --format json` 명령이 추가되었습니다.
- MCP에도 읽기 전용 `wom_profile_list`, `wom_profile_resolve` 도구가 추가되었습니다.
- AI runtime이 runtime-context나 draft 작업 전에 요청된 profile을 먼저 확인할 수 있습니다.
- 예시 registry는 `wom-kit/templates/profiles/wom-profiles.example.yml`에 추가되었습니다.

private archive migration은 필요 없습니다.

이번 버전은 profile 등록, token 저장, create-draft dry-run, provider API sync, UI, MCP를 통한 real minting, MCP write/register/apply tool을 추가하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.17
```

## `v0.2.15`에서 `v0.2.16`으로

이번 버전은 WOM AI Runtime Context Layer를 추가하는 호환 가능한 패치입니다.

바뀐 점:

- `archive runtime-context <archive-root> --format json` 명령이 추가되었습니다.
- `--expected-archive-id`, `--expected-type`, `--strict` 옵션으로 AI runtime이 draft를 만들거나 dry-run을 실행하거나 mint 승인을 요청하기 전에 올바른 archive에 붙어 있는지 확인할 수 있습니다.
- 기본 출력은 로컬 절대경로를 숨기고 archive-relative path만 보여줍니다. 신뢰할 수 있는 로컬 디버깅 때만 `--no-redact-local-paths`를 사용할 수 있습니다.
- MCP에도 읽기 전용 `archive_runtime_context` 도구가 추가되었습니다. 기존 MCP allowed roots 규칙을 그대로 따릅니다.

private archive migration은 필요 없습니다.

이번 버전은 create-draft dry-run, provider API sync, UI, MCP를 통한 real minting, MCP apply tool을 추가하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.16
```

## `v0.2.14`에서 `v0.2.15`로

WOM Safe HTML Profile dry-run validator 패치이며, 호환 가능한 변경입니다.

변경 사항:

- `archive check-safe-html --path <zet> --dry-run`이라는 읽기 전용 CLI 명령을 추가했습니다. v0.2 Markdown 호환 zet가 미래의 WOM Safe HTML Profile 마이그레이션과 호환 가능한지 미리 검사합니다.
- validator는 `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URL, 그리고 `onclick=` 같은 inline event handler attribute가 zet body 안에 있으면 차단합니다.
- validator는 `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, `source_reference_preview` 필드를 포함한 구조화된 JSON을 반환합니다.

실제 private archive migration은 필요 없습니다.

이번 릴리스는 Markdown-to-HTML 변환기, profile allowlist, UI, live sharing, P2P transport, external provider sync를 구현하지 않습니다. 기존 Markdown 호환 zets는 그대로 유효합니다.

```bash
git fetch --tags
git checkout v0.2.15
```

## `v0.2.13`에서 `v0.2.14`로

WOM Safe HTML Profile을 위한 호환 가능한 문서/스펙 기준선 패치입니다.

변경 사항:

- `WOM`, `zet`, `ZET`의 차이를 문서화했습니다.
- `zet`는 zettel-kasten 안에서 민팅되는 단위 문서라고 명확히 했습니다.
- `ZET`는 메신저, SNS/feed, 협업툴로 확장될 수 있는 미래 통신 계층이라고 명확히 했습니다.
- WOM Safe HTML Profile을 장기 canonical/interchange/rendering target으로 기록했습니다.
- Markdown은 v0.2 authoring/import compatibility format으로 유지했습니다.

실제 private archive migration은 필요 없습니다.

이번 릴리스는 Markdown-to-HTML converter, profile validator, UI, live sharing, P2P transport, external provider sync를 구현하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.14
```

## `v0.2.12`에서 `v0.2.13`으로

호환 가능한 WOM 명칭 기준선과 CLI alias 패치입니다.

변경 사항:

- `WOM`을 전체 umbrella name으로, `Widesider of Modernity`를 그 확장명으로 기록했습니다.
- zet를 민팅하는 선호 명령으로 `archive mint-zet`을 추가했습니다.
- 기존 `archive mint-zettel`은 compatibility alias로 유지했습니다.
- 범위가 정해진 portable unit을 만드는 선호 명령으로 `archive parcel`을 추가했습니다.
- 기존 `archive pack`은 compatibility alias로 유지했습니다.
- parcel/workpack을 들여오는 과정을 미리 검토하는 선호 명령으로 `archive admit --dry-run`을 추가했습니다.
- 기존 `archive import --dry-run`은 compatibility alias로 유지했습니다.

실제 private archive migration은 필요 없습니다.

기존 스크립트는 옛 이름을 계속 써도 됩니다. 다만 새 사용자-facing 문서는 `mint-zet`, `parcel`, `admit`을 우선 사용해야 합니다.

```bash
git fetch --tags
git checkout v0.2.13
```

## `v0.2.11`에서 `v0.2.12`로

호환 가능한 real delegate receipt write 패치입니다.

변경 사항:

- `archive delegate-zet --approve --reviewed-by <actor>` 추가,
- 실제 delegate 실행 시 `receipts/delegate/*.delegate.json` 생성,
- `archive doctor`가 applied delegate receipt 검증,
- real delegate capability receipt에 nonce 생성,
- claim/spent/revocation registry는 아직 구현하지 않음을 명시.

private archive migration은 필요하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.12
```

## `v0.2.10`에서 `v0.2.11`로

호환 가능한 delegate capability 계약 패치입니다.

변경 사항:

- `archive delegate-zet --dry-run`에 `--target-policy counterparty_bound|claimable_once` 추가,
- `claimable_once` delegate preview에서는 `--target-archive` 없이도 실행 가능,
- `delegation_capability`, `claim_binding`, `settlement_condition` preview field 추가,
- settlement는 아직 비금융 상태이며 `mode: "none"`으로만 기록,
- 실제 P2P, claim registry, spent registry, revocation, blockchain, payment는 아직 구현하지 않음.

private archive migration은 필요하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.11
```

## `v0.2.9`에서 `v0.2.10`으로

이 버전은 호환 가능한 dry-run lifecycle 기능 패치입니다.

변경 사항:

- `archive delegate-zet --dry-run` 추가,
- `archive attest-zet --dry-run` 추가,
- `archive anchor-zet --dry-run` 추가,
- delegate, attest, anchor를 위한 read-only MCP check 추가,
- delegate receipt, attestation receipt, anchor metadata schema 추가.

private archive migration은 필요하지 않습니다.

실제 P2P, feed, transport, 외부 전송, foreign zet import는 아직 구현하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.10
```

## `v0.2.8`에서 `v0.2.9`로

호환 가능한 용어 안정화 패치입니다.

변경 사항:

- 새 archive는 `human_minting`을 기본값으로 사용합니다.
- 기존 `human_promotion` archive도 계속 유효합니다.
- zettel rules에서 `minting_rules`를 사용할 수 있습니다.
- `promotion_rules`는 v0.2 legacy fallback으로 유지됩니다.
- 사용자-facing 문서는 minting 언어를 우선 사용합니다.

실제 private archive migration은 필요 없습니다.

```bash
git fetch --tags
git checkout v0.2.9
```

## `v0.2.7`에서 `v0.2.8`로

호환 가능한 민팅 라이프사이클 기능 패치입니다.

변경 사항:

- `archive mint-zettel --dry-run`을 추가했습니다.
- `archive mint-zettel --approve --reviewed-by <id>`를 추가했습니다.
- `receipts/mint/` 아래 mint receipt를 추가했습니다.
- `receipts/mint/drafts/` 아래 draft snapshot을 추가했습니다.
- canonical zettel의 `mint` frontmatter를 추가했습니다.
- doctor가 mint receipt와 SHA-256 파일 연결을 검증합니다.
- read-only MCP `mint_zettel_check`를 추가했습니다.

실제 private archive migration은 필요 없습니다.

새 zettel을 민팅했다면 canonical zettel, mint receipt, draft snapshot을 함께 보관하세요.

```bash
git fetch --tags
git checkout v0.2.8
```

## `v0.2.3`에서 `v0.2.4`로

문서 정돈 패치입니다.

변경 사항:

- `README.md`를 더 정돈된 영문 프로젝트 진입 문서로 다시 작성했습니다.
- `README.ko.md`를 한국어 공식 진입 문서로 추가했습니다.
- 업그레이드 문서를 영문/한국어로 분리했습니다.
- 공개 포지셔닝, 현재 상태, privacy boundary, storage model, text provenance 설명을 정리했습니다.

실제 private archive migration은 필요 없습니다.

권장 명령:

```bash
git fetch --tags
git checkout v0.2.4
```

## `v0.2.2`에서 `v0.2.3`으로

한영 문서 병기 패치입니다.

실제 private archive migration은 필요 없습니다.

```bash
git fetch --tags
git checkout v0.2.3
```

## `v0.2.1`에서 `v0.2.2`로

문서, provenance, 공개 히스토리 정리 패치입니다.

실제 private archive migration은 필요 없습니다.

중요 개념:

```text
original editable text != OCR/AI-derived text
```

둘 다 보관하지만, OCR/AI-derived text는 derivation metadata와 review status를 남겨야 합니다.

## 이전 버전에 남기

사용자는 오래된 버전에 남을 수 있습니다.

이것도 설계의 일부입니다.

```text
old version -> old rule set
new version -> updated rule set
```

미래의 sharing/collaboration 기능은 sender/receiver version을 명시해야 합니다.

## 앞으로의 릴리스 요구사항

앞으로 공개 릴리스는 반드시 다음을 포함해야 합니다.

- changelog entry,
- `wom-kit/docs/releases/` 아래 release note,
- compatibility statement,
- migration instructions,
- test/doctor verification status,
- privacy scan status,
- Git tag,
- GitHub Release.
