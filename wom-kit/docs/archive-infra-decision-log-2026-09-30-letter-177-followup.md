# Archive infra decision log: letter 177 follow-up (2026-09-30)

Status: implemented for v0.4.54 under the owner's standing instruction to
finish every implementable item before the reply.

## 1. The general Git backup preview could not read a private remote

Letter 177 reported that the general Git backup preview stopped with the
remote reference not observable. v0.4.53 did not reproduce it. Reading the
code found the cause: `git-backup-plan` defaulted to `--credential-mode
anonymous`, which disables every credential helper, so a private backup
repository (the normal case for personal records) always answers
`git_transport_ref_observation_unavailable`. The session-scoped backup and the
exact writer already used `stored`, and `docs/git-backup-plan.md` described
the anonymous limit since v0.4.2, but nothing in the result told the operator
or the helper AI to switch.

Decision:

- `git-backup-plan` defaults to `--credential-mode stored`: Git reads the
  remote with the login already saved on the PC, non-interactively; WOM never
  asks for, shows or stores it. `--credential-mode anonymous` remains for
  public repositories.
- When the remote cannot be read the plan names the next step: switch to
  `stored` if it ran anonymously; otherwise sign in once with the normal Git
  tools and rerun; for `configured_remote_unavailable_or_unsafe`, the remote
  must be one `https://` URL without a user name or token (SSH unsupported).
- `git-backup-reconcile-plan` keeps its defaults; its session route is bound to
  the original inputs and the exact apply already requires `stored`.

This is a change of a default set in v0.4.2, made because the old default
could not serve the owner's intended use (a private backup of personal
records). It is recorded here as such.

Not proven: no real private remote was queried; the customer's run will show
whether their remote is https and their saved login works.

## 2. Old index snapshots piled up on the disk

While checking whether already-committed snapshot files could keep blocking
backups, a larger problem appeared: every index run published a new
content-addressed generation in `db/search-snapshots` (a full copy of the
index), `db/relation-snapshots`, `db/title-snapshots` and
`db/finder-snapshots`, and nothing ever deleted old generations.

Decision (the owner's rule that clean-up means delete):

- after each publication WOM deletes older generations in that folder; the
  current one, the newest other one and anything younger than one hour (a
  search cursor or a reviewed plan may still read it) stay. Partial files
  abandoned for more than a day are deleted too. Only WOM-named files are
  touched; a file a reader still holds open is left for the next run.
- A generation an older backup had committed to Git now appears only as a
  small deletion, which the next backup records; Git then stops carrying it
  forward. The history still holds the old bytes; rewriting history is outside
  WOM.

Validation: synthetic example archive, five index runs with edits, a committed
archive whose old generations become deletions.
