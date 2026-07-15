# Install The WOM Archive Agent Skill

Status: v0.3.244 preview-first, approval-gated local host lifecycle

## What This Does

WOM-kit already contains the `wom-archive` Agent Skill. These commands copy
that packaged skill into one AI host skill directory so the host can discover
it without a manual file-copy ritual.

Installing the Python wheel and installing the host skill are separate acts:

- `uv tool install` or a dedicated `pip` environment installs WOM-kit commands.
- `runtime-skill-install --approve` writes the reviewed skill package into one
  selected host skill directory.

The first act never implies approval for the second.

## Codex User Setup

Current Codex documentation discovers user skills under
`$HOME/.agents/skills` and repository skills under `.agents/skills` inside the
repository path. WOM-kit uses those locations for `--host codex`; it does not
target the older `.codex/skills` authoring layout.

First inspect current state:

```powershell
archive runtime-skill-status --format json
```

Preview the install:

```powershell
archive runtime-skill-install --dry-run --format json
```

Review `target`, `source_package`, `installation`, `would_write`, and
`operation_plan_sha256`. Then approve only that exact plan:

```powershell
archive runtime-skill-install `
  --approve `
  --reviewed-by person:local-owner `
  --expected-plan-sha256 <operation_plan_sha256> `
  --format json
```

Confirm the result:

```powershell
archive runtime-skill-status --format json
```

The desired state is `managed_current`. Codex detects skill changes
automatically in ordinary cases; restart only when the skill does not appear.

## Repository Scope

To make the skill available only while Codex works in one repository:

```powershell
archive runtime-skill-install `
  --host codex `
  --scope repo `
  --repo-root <repository-root> `
  --dry-run `
  --format json
```

Repeat the same target options for approval. WOM-kit resolves the target to
`<repository-root>/.agents/skills/wom-archive` and refuses a missing,
symlinked, or escaping repository root.

## Explicit Custom Host Root

WOM-kit does not guess another product's current user directory. A custom host
or test environment must provide its skills root explicitly:

```powershell
archive runtime-skill-install `
  --host custom `
  --scope custom `
  --skills-root <skills-root> `
  --dry-run `
  --format json
```

This copies a standard Agent Skill package. It does not claim that every host
will discover the supplied directory.

## State Meanings

| State | Meaning | Safe action |
| --- | --- | --- |
| `absent` | No target skill directory exists. | Preview an install. |
| `managed_current` | Every installed file matches the WOM manifest and current packaged source. | No action. |
| `managed_outdated` | Every installed file still matches its WOM manifest, but a newer packaged source is active. | Preview the same install command as an update. |
| `unmanaged_conflict` | A directory exists without WOM ownership evidence. | Do not overwrite or delete it. Review manually. |
| `managed_drift` | A WOM-installed file, directory, or symlink differs from the ownership manifest. | Preserve the human change and review manually. |
| `managed_invalid` | The ownership manifest is malformed or no longer matches the target contract. | Do not write or remove anything. |

An install command performs both first install and verified managed update. It
never adopts an unmanaged directory and never overwrites a human-edited
managed directory.

## Ownership Manifest

An approved install writes `.wom-kit-install.json` inside the skill directory.
It records:

- WOM-kit version, host, and scope;
- packaged skill digest;
- install time and safe reviewer id;
- archive-relative file names, byte counts, and SHA-256 values.

A payload SHA-256 also makes an accidental or manual edit to the ownership
manifest itself fail closed.

It records no absolute source/target path, archive data, prompt, conversation,
provider account, token, credential, or secret value.

Every update and uninstall rereads every managed file and compares it with this
manifest. The reviewed plan also binds the hashed target location, packaged
source, prior state, and manifest digest so stale approval fails closed.

## Safe Uninstall

Preview removal:

```powershell
archive runtime-skill-uninstall --dry-run --format json
```

Approve only the returned digest:

```powershell
archive runtime-skill-uninstall `
  --approve `
  --reviewed-by person:local-owner `
  --expected-plan-sha256 <operation_plan_sha256> `
  --format json
```

Uninstall works only for an unchanged WOM-kit-managed directory. It moves the
verified directory outside the active skills root before deletion, so a
cleanup failure cannot leave the skill active. An unmanaged or edited skill is
never removed.

## Safety Boundary

These commands:

- read only the packaged public skill and the selected target directory;
- redact local paths by default;
- make no network, provider, model, database, object-store, or credential call;
- read and write no WOM archive, zet, objet, relation, or receipt;
- create no generated graph or index;
- expose no MCP write tool;
- use an exclusive local operation lock and revalidate the plan under that
  lock before writing.

PyPI publication and plain `pip install wom-kit` remain separate future work.
Reusable workspace distribution as a Codex plugin also remains a later
distribution option; v0.3.244 provides a narrow local skill lifecycle.
