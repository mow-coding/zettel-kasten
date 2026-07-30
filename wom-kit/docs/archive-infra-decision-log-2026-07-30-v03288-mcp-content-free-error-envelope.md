# Decision Log — v0.3.288 MCP Content-Free Error Envelope

Date: 2026-07-30

## Context

The shared MCP boundary copied exception text into tool and JSON-RPC error
responses. Individual tools could be careful and still leak an archive path,
identifier, frontmatter value, provider detail, or caller-controlled string
when a shared service or protocol handler failed.

## Decision

All failed MCP tools return one exact content-free envelope with
`tool_execution_failed`. JSON-RPC failures use fixed category messages only.
Only `null` and an object are accepted for request parameters and tool
arguments; falsey non-object values are rejected.

Internal exceptions may remain chained for in-process diagnosis, but their
type and message never become wire data.

## Consequences

- MCP clients receive a stable machine-readable failure code instead of an
  unstable human exception message.
- Operators must diagnose details locally rather than asking a remote MCP
  client to display raw failures.
- Existing safety checks remain active even though their internal wording is
  no longer part of the public wire contract.
- Successful tool schemas and archive-service behavior remain unchanged.

Implementation detail and verification evidence are recorded in
`meeting-minutes/2026-07-30-v03288-mcp-content-free-error-envelope-implementation.md`.
