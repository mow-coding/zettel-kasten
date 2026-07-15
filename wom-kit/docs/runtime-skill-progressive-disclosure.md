# WOM Archive Agent Skill And Progressive Disclosure

Status: v0.3.244 packaged skill and approval-gated host lifecycle

## Purpose

An AI operator should not have to read one giant manual before answering a
small archive question. It also must not skip the safety rules merely because
the manual is long.

WOM therefore ships a standards-compatible `wom-archive` Agent Skill package.
The package applies the same useful pattern seen in the
[Agent Skills specification](https://openagentskills.dev/docs/specification) and
low-friction AI tooling such as
[Graphify](https://github.com/Graphify-Labs/graphify): make the entry point easy
to discover, keep the first read small, and reveal deeper instructions only
when the current goal needs them.

WOM adopts that interaction pattern. It does not adopt a generated graph as
the source of truth.

## Package Shape

```text
templates/ai-runtime/wom-archive/
  SKILL.md
  references/
    startup-and-update.md
    reading-memory-and-revision.md
    capture-draft-and-publication.md
    foreign-sharing-and-trust.md
    safety-results-and-human-language.md
    operator-contract.md
```

`SKILL.md` contains the required YAML `name` and `description`, the bounded
first action, a goal-to-reference routing table, universal safety rules, and
the human-facing completion contract. At v0.3.243 it is 97 lines and 555 words.

The five focused references cover ordinary task families. The preserved
`operator-contract.md` contains the complete previous runtime contract so an
exact advanced command, historical boundary, or narrow trust-stage rule is not
lost during the split.

Since v0.3.244, a separate CLI lifecycle can preview, install, inspect, update,
and uninstall this package in one explicitly selected AI-host skill directory.
It does not run as a side effect of installing the Python wheel.

## AI Reading Contract

1. Read `SKILL.md` once when archive work begins.
2. Run the quick read-only `archive ai-start-here` surface.
3. Choose the one focused reference matching the human's actual goal.
4. Search `operator-contract.md` by exact command name only when the focused
   reference says more detail is required.
5. Read full zet bodies selected by the human goal and archive relations; a
   short instruction file or abstract is a routing aid, not a substitute for
   the relevant evidence.

Preloading every reference defeats the design. Reading no reference and
improvising from model memory also defeats it.

## Release Gate

Run:

```powershell
python wom-kit/tools/check_runtime_skill.py
```

The checker verifies:

- valid YAML frontmatter with a safe name matching the directory;
- a bounded root line and word count;
- at least two focused references and direct root discovery of every reference;
- no symlink in the skill package;
- no broken local Markdown link or link escaping the skill directory;
- a separate line budget for each focused reference;
- preservation of critical untrusted-input, dry-run, approval, mint, revision,
  foreign-trust, secret, and naming language across the package.

The checker is part of `check_release_readiness.py`. Existing documentation
tests read the entire skill package rather than assuming every rule must remain
inside the first file.

## Installed-Wheel Parity

The skill directory is one of WOM-kit's deterministic package resources.
`sync_package_resources.py` mirrors every file into the installable package and
binds source path, packaged path, byte count, and SHA-256 in the resource
manifest. Clean-wheel verification checks those members after building and
after a fresh virtual-environment install.

This means progressive instructions are available from both a source checkout
and the exact tagged wheel. A stale or incomplete generated package mirror
blocks release readiness.

## Authority Boundary

The skill is operational guidance, not archive memory authority.

- Reviewed local zet, objet, relation, and receipt records remain canonical.
- Abstracts, ties, edges, indexes, and skill references choose reading order;
  they do not replace the relevant zet bodies.
- GitHub remains metadata/version-history backup, object storage remains objet
  byte backup, and an external database remains a regenerable map backup or
  replica.
- Installing the Python tool does not discover, read, create, or modify a user
  archive, and it does not silently write an AI host's configuration.
- The v0.3.244 host lifecycle is a separate local CLI action. Status and
  `--dry-run` are read-only; a write requires the exact preview SHA-256 and a
  safe reviewer identifier. A path-free ownership manifest binds every managed
  file, and a conflicting, symlinked, invalid, or human-edited directory fails
  closed rather than being adopted, overwritten, or removed.
- The default Codex user target is `$HOME/.agents/skills/wom-archive`.
  Repository scope requires an explicit repository and uses
  `<repo>/.agents/skills/wom-archive`; other hosts use an explicit custom skill
  root. Local paths remain redacted by default.
- Host activation changes only AI instruction discovery. It does not authorize
  an archive write, read source bodies, call a provider, or make a generated
  graph or index canonical.

## Deliberately Not Claimed

This checkpoint does not claim:

- PyPI publication or availability of `pip install wom-kit`;
- silent or automatic host skill installation or updates;
- generated graph authority;
- automatic semantic truth checking;
- permission for an MCP inspection tool to perform a CLI write;
- a web dashboard or custom UI.
