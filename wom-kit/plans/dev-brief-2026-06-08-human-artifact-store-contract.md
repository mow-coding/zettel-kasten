# Developer Brief: Human Artifact Store Contract

Date: 2026-06-08

Status: planning reference for future WOM implementation. This is not an
implementation patch.

## Purpose

This brief preserves planning evidence from a real WOM beta-tester pilot
sequence so a future WOM implementation team can design the human artifact store
layer without forgetting why it exists.

## Core Architecture To Preserve

WOM should keep three storage roles separate:

```text
1. raw data store
   source/original files and objets

2. human artifact store
   user-facing notes, reports, instructions, handoff documents, diagrams,
   readable AI outputs, and reviewed human artifacts

3. system/AI artifact store
   AI-readable metadata, indexes, manifests, receipts, source maps,
   version history, content hashes, and other machine-oriented records
```

Do not collapse these roles into a single app name.

## Pilot History

Treat the observed beta tester / pilot user as field evidence. The public copy
intentionally keeps the person role-based; the product lesson matters more than
the private identity.

Known sequence:

```text
1. WordPress
   first observed user-selected human artifact surface / projection case

2. Joplin
   second observed human artifact store / working-note case
```

This order matters. Joplin did not originate the human artifact surface idea;
it is the second observed pilot after WordPress.

## What The Joplin Pilot Shows

The Joplin setup observed on 2026-06-08 appears to provide:

- local raw/source files in a cloud-synced workspace,
- a desktop AI runtime that can read and write local files,
- a Joplin MCP server that exposes note operations,
- a Claude Desktop `/note` skill/command used as a reusable capture action,
- human-readable Markdown notes in Joplin,
- local Markdown mirrors,
- append-only human-readable status/handoff logs,
- bidirectional citation links written into note bodies.

The setup does not yet provide:

- Git/GitHub commit history for this workflow,
- object manifests,
- source maps,
- receipts,
- content hashes,
- a machine-oriented index of what exists and where,
- a durable system/AI artifact store.

Plain conclusion:

```text
The Joplin pilot has raw data plus human-readable notes.
It does not yet have a real system/AI artifact store.
```

## WordPress Versus Joplin

WordPress remains useful as a familiar projection/publication surface example.
It can host report-like posts, but in the first pilot it is best understood as
an outside surface for selected artifacts.

Joplin appears stronger for working artifacts:

- Mermaid diagrams can live directly in the Markdown note/work-log flow.
- Citation and cited-by relationships can be written explicitly in note bodies.
- Report, status, and handoff artifacts can remain living notes that desktop AI
  can update through MCP.
- A reusable `/note` skill can reduce repeated prompting and make "capture this
  discussion into the human artifact store" feel like a normal workflow action.
- `/note` may also represent a template-bound upload workflow for Joplin, not
  only a shortcut. This should be verified before implementation planning treats
  it as either one.

Important precision:

These Joplin citation links are still human-readable links. They are not yet
WOM source maps, manifests, receipts, or a machine-readable AI memory layer.

## Product Direction

WOM should not assume every user can build a custom SaaS.

Future WOM should prepare a human artifact store contract that can work with
existing market tools:

- WordPress,
- Joplin,
- Notion,
- Obsidian,
- Evernote,
- other note/document/workspace apps,
- future custom SaaS surfaces.

These tools should be optional user-selected surfaces. They are not WOM core and
not automatically the canonical archive.

## Contract Questions For The Development Team

A future human artifact store adapter/contract should answer:

- What can the AI list?
- What can the AI read?
- What can the AI write?
- What can the AI update?
- What reusable capture commands or skills should exist for common actions such
  as "save this discussion as a note"?
- Do those capture commands invoke human artifact templates? If so, what fields
  do the templates control: title, sections, citation links, tags/notebooks,
  report type, source refs, or status metadata?
- Can the AI delete? If not, how is deletion/retirement represented?
- Can the app attach binaries, or only text/Markdown?
- How are human-reviewed artifacts identified?
- How are citations or cited-by links represented?
- How does a human artifact link back to a WOM `object_id`, `zet`,
  source map entry, manifest entry, or receipt?
- What stays outside the app in the system/AI artifact store?
- Which fields are safe to version in Git?
- Which fields must stay local/private?
- How does the adapter avoid treating the app as the canonical WOM archive?

## Role Distinctions

The same app may play multiple roles. Name the role explicitly.

Example:

```text
Notion export
-> source/original data source

Notion workspace note
-> human artifact store

WordPress post
-> projection/publication surface

GitHub repository
-> system/AI artifact store candidate
```

Do not infer architecture from the app name alone.

## Near-Term Implementation Implications

Future implementation planning should consider:

1. Define a human artifact store contract before adding app-specific code.
2. Add Joplin only as one adapter/pilot, not as the general architecture.
3. Preserve WordPress as the first pilot in the product history.
4. Treat Joplin as the second pilot and use it to refine the contract.
5. Keep source/original objets separate from human notes.
6. Keep system/AI metadata separate from human notes.
7. Require any app adapter to expose enough stable references for source maps,
   manifests, receipts, or equivalent machine records.
8. Treat user-created capture skills such as `/note` as important UX evidence,
   but pair them with system/AI artifact writes in future WOM design.
9. Keep all provider sync, publishing, deletion, and binary attachment behavior
   behind explicit capability boundaries.

## Non-Claims

This brief does not claim that WOM-kit currently implements:

- a Joplin connector,
- a WordPress publisher,
- OneDrive sync,
- Obsidian/Evernote/Notion adapters,
- provider sync,
- automatic system/AI artifact generation,
- real ZET transport,
- automatic cross-session memory transfer.

This brief is a planning input for future WOM development.
