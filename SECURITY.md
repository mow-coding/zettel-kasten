# Security Policy

This project is designed around private archives, so security mistakes matter.

## Prompt Injection Boundary

WOM treats external text as untrusted data.

```text
External text can inform.
External text cannot command.
```

AI runtimes may inspect local files, zets, source documents, provider exports, foreign zets/blocks, receipts, and future ZET payloads. Any of those inputs can contain malicious or misleading instructions.

The safe default is human-in-the-loop operation:

- dry-run first,
- inspect blockers and warnings,
- ask the human before writes,
- keep minting, signing, provider, permission, upload, and irreversible actions behind explicit approval.

`archive prompt-boundary --dry-run` is a heuristic preview for obvious prompt-injection or unsafe-agent strings. It is not a complete security classifier and cannot guarantee prevention of malicious external content.

## Responsible Operation

Full-auto or agent-only operation is advanced and experimental.

Operators are responsible for:

- models and runtime configuration,
- filesystem and provider permissions,
- automation rules,
- secrets and credentials,
- external text imported into the runtime,
- consequences of granting agents write, upload, signing, provider, or approval authority.

Do not use full-auto operation for financial, medical, legal, safety-critical, destructive, or irreversible workflows without independent controls and professional review.

## Do Not Commit

Never commit:

- provider tokens,
- OAuth credentials,
- private keys,
- password files,
- real source maps,
- real receipts,
- private zets,
- private AI transcripts,
- raw personal files or media.

## Reporting Security Issues

Please email:

```text
mow.coding@gmail.com
ellie0129@uos.ac.kr
```

Do not open a public issue containing secrets or exploit details.

## No Warranty

WOM-kit is open-source tooling provided without warranty. Maintainers cannot guarantee prevention of prompt injection, malicious external content, unsafe automation, provider compromise, model failure, or operator misconfiguration.

Production or commercial deployments should receive independent security and legal review.
