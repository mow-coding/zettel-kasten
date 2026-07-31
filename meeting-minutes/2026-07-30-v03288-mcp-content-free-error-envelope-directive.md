# v0.3.288 MCP Content-Free Error Envelope Directive

Date: 2026-07-30

Branch: `codex/v0.3.288-mcp-content-free-error-envelope`

Base: v0.3.287 candidate `3a36d4e9e8c296d19e5d0246d30e12aae71bc7bc`

## User Intent

The user asked WOM development to continue unattended and carefully through
the remaining beta-tester and independent-review backlog. Work must remain
split into small, independently reviewed public releases rather than combining
many unrelated risks into one release.

## Problem

The MCP stdio server currently exposes exception text through both tool-error
results and JSON-RPC protocol errors. That text can contain an archive path,
archive id, zettel id, filename, frontmatter value, provider detail, or other
operator-controlled content. The leak is systemic because most MCP tools route
service failures through the shared `call_service()` boundary.

The request parser also uses `or {}` for request parameters and tool
arguments. Falsey values with the wrong type can therefore be silently
converted into an empty object rather than rejected as invalid parameters.

## Required Product Contract

Every MCP tool execution failure must return exactly:

```json
{
  "content": [
    {
      "type": "text",
      "text": "Tool execution failed."
    }
  ],
  "structuredContent": {
    "error": "tool_execution_failed"
  },
  "isError": true
}
```

This envelope is deliberately content-free. No exception message, exception
type, path, id, title, body, frontmatter value, provider detail, user argument,
or method/tool name may be interpolated into it.

JSON-RPC errors must use only these fixed messages:

| Code | Message |
| --- | --- |
| `-32700` | `Parse error` |
| `-32600` | `Invalid Request` |
| `-32601` | `Method not found` |
| `-32602` | `Invalid params` |
| `-32603` | `Internal error` |

No dynamic method name, validation detail, exception string, JSON fragment, or
request value may appear in a JSON-RPC error message or data field.

## Required Implementation

Production scope is intentionally limited to:

```text
wom-kit/src/wom_kit/mcp_server.py
```

The implementation must:

1. make `tool_error_result()` accept no caller-provided text and always return
   the exact fixed envelope above;
2. catch `ToolError` without converting it to text;
3. make `call_service()` translate `ArchiveServiceError` to a content-free
   `ToolError` while retaining exception chaining only for in-process
   debugging;
4. normalize every JSON-RPC error at the protocol boundary to the fixed
   messages above;
5. classify an unknown `tools/call` tool as invalid parameters without
   echoing its name;
6. normalize only literal `None` parameters or arguments to `{}` and reject
   every other non-object value, including `false`, `0`, `""`, and `[]`;
7. preserve successful tool response shapes and all existing write-safety,
   approval, allowed-root, redaction, and dry-run enforcement;
8. avoid logging or printing the raw exception at this stdio boundary.

Internal `ToolError("detailed text")` call sites may keep their human-readable
construction in this release if the shared wire boundary proves that the text
cannot escape. Broadly rewriting all 120 tool implementations is outside this
release.

## Required Tests

Primary test scope:

```text
wom-kit/tests/test_mcp_server.py
```

Tests must:

1. define one exact expected error-envelope helper and migrate every assertion
   that currently depends on raw tool error text to exact-envelope equality;
2. keep the adjacent no-write, approval, dry-run, allowed-root, and redaction
   assertions intact rather than weakening tests to `isError` only;
3. inject sentinel secrets into:
   - a direct `ToolError`;
   - an `ArchiveServiceError` through `call_service()`;
   - an unexpected exception;
   - an unknown method;
   - an unknown tool name;
   - invalid request params and invalid tool arguments;
4. assert that no sentinel, local path, method name, tool name, exception
   class, or raw validation message appears anywhere in serialized wire
   output;
5. cover `params` and `arguments` values of `null`, `{}`, `false`, `0`, `""`,
   and `[]`, proving that only `null` and `{}` normalize to an object;
6. preserve successful initialize, ping, tools/list, and representative
   tools/call behavior;
7. cover fixed parse-error, invalid-request, method-not-found,
   invalid-params, and internal-error messages.

## Documentation And Release Work

The release must also update:

- `wom-kit` version truth to `0.3.288`;
- root and WOM-kit README current-release/install references;
- English and Korean Python install guides;
- capability matrix and runtime canonical-entrypoint status;
- a public release note plus packaged release-note mirror;
- one compact decision log;
- one chronological implementation record;
- deterministic packaged-resource manifest and parity checks.

The public release note must describe the privacy boundary without claiming
that internal errors are absent. The claim is that raw details do not cross
the MCP wire boundary.

## Hard Boundaries

- Do not access or modify
  `<private-beta-archive-root>`.
- Do not add a new MCP tool, CLI command, provider call, network call, archive
  write, migration, or beta-validation command.
- Do not change archive service semantics merely to make MCP tests pass.
- Do not remove safety checks whose former text assertions are being migrated.
- Do not claim a public release, tag, CI result, or beta validation before the
  corresponding evidence exists.
- Do not commit or push until the supervising thread has reviewed the combined
  diff and complete verification.

## Verification Gates

Before this candidate may be committed:

1. focused MCP tests pass;
2. content-sentinel privacy regressions pass;
3. full source suite passes;
4. release-readiness, public-link, documentation, capability, and package
   resource checks pass;
5. resource synchronization is exact;
6. `py_compile` and `git diff --check` pass;
7. an independent P1/P2 review finds no release blocker;
8. a clean exact-tree wheel installs in a fresh environment and verifies all
   four entrypoints, onboarding, and strict Doctor.

Remote PR, merge, exact main/tag CI, public Release, unauthenticated download,
and fresh public-wheel verification are later gates and must be recorded
separately.
