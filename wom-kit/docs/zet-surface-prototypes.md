# ZET Surface Prototypes

This note records the first four user-selected ZET surface prototypes:
WordPress, Joplin, Notion, and Obsidian.

They are not canonical WOM archives. They are optional surfaces where a reviewed
zet projection may later appear. Posting, syncing, or writing to one of these
surfaces is not minting, not ZET transport, and not a replacement for WOM
receipts, manifests, or source maps.

## Current Command

```bash
archive zet-surface-prototype <archive-root> \
  --surface-kind wordpress \
  --surface-ref wordpress:example \
  --dry-run \
  --format json
```

Supported `--surface-kind` values:

- `wordpress`
- `joplin`
- `notion`
- `obsidian`

The command is read-only. It never starts OAuth, asks for tokens, calls
providers, creates notes, publishes posts, writes vault files, uploads
attachments, creates projection receipts, mints zets, or runs ZET transport.

## Prototype Families

| Surface | Prototype family | Likely role | Future write target |
| --- | --- | --- | --- |
| WordPress | remote REST API | projection surface | post or page draft |
| Joplin | local Data API | working note store | note in a notebook |
| Notion | remote workspace API | human artifact store | page or database item |
| Obsidian | local vault or URI | working note store | vault-relative Markdown file or URI |

## Source Notes

- WordPress exposes a REST API for JSON interaction with a site:
  <https://developer.wordpress.org/rest-api/>.
- Joplin's Data API is exposed by the desktop Web Clipper service and uses a
  local token: <https://joplinapp.org/help/api/references/rest_api/>.
- Notion integrations use workspace permissions and page/data-source parents:
  <https://developers.notion.com/guides/get-started/overview> and
  <https://developers.notion.com/reference/post-page>.
- Obsidian supports `obsidian://` URIs for vault/file actions:
  <https://obsidian.md/help/uri>. Advanced URI is a community plugin option for
  richer URI workflows: <https://publish.obsidian.md/advanced-uri-doc/Home>.

## Boundary

Each future adapter must keep these records separate:

- the canonical WOM zet and its mint/provenance receipts,
- the generated projection body or metadata,
- the external surface locator,
- the human approval event,
- provider/vault credentials or local paths, which must stay outside public
  archive records.

The first safe future step is still a dry-run projection plan. A later
provider-specific write adapter should add its own receipt before any real
publish, sync, note creation, or vault write.
