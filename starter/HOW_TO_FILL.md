# How to fill the dashboard

Everything on the page comes from files in this workspace. Fill them only from what is really here. Never invent a
fact, a progress claim or a quote. Anything you cannot find out goes under "Items for the user" in the ledger.

After each edit, run these two. The first rebuilds the page. The second only reports: it prints what parsed, how each
status was read, and what looked close but did not. Files are UTF-8. A file with a BOM or UTF-16 also reads correctly.

```
python workspace_dashboard/build_dashboard.py
python workspace_dashboard/build_dashboard.py --doctor
```

## Already have these documents?

A document counts only if its format already matches the sections below. Then point `dashboard_config.json` at it instead
of writing a new one: `overview`, `ledger`, `decisions`. Delete the starters you no longer use. An ordinary TODO or
changelog does not match, and pointing at one gives an empty section, which the doctor reports. Keep the starter beside it,
copy the facts across with a link back, and ask before adding headings to someone's own files.

## Overview (`overview`)

`## ` is a group and `### ` is a project. Text before the first `###` is ignored. In a single-product repository, use
one card per major feature if the features have different states, otherwise one card. The page's percentage depends on
this choice, so say which you made.

```markdown
## Group name

### Project name

**Status: Local candidate**

One short paragraph, which may run
over two lines.

- A bullet stays off the card, but any link in it is collected.

**Next:** The next step.

[Readme](../README.md) | [Site](https://example.com/)
```

`**Status: x**`, `**Status:** x` and `Status: x` all work, in any case, and the same for Next. A line holding only links
becomes the card's links. Links are relative to the document. Write spaces as `%20` or use `[a](<my file.md>)`.

Status words decide the heat, using whole words. Blocked anywhere in the text wins; otherwise only the part before the
first `;` counts, because later clauses describe what is still to come.

| Kind | Words (change them in `status_words`) | Heat |
|---|---|---|
| Blocked | blocked, disabled | 2 |
| Live | live, shipped, released, in production, done, deployed, published | 3 |
| Idea | proposal, suggestion, handoff, idea, planned, not started, not begun, to do, backlog | 1 |
| Local | local, locally, built, building, working, works, in progress, under way, underway, ongoing, active, wip, draft, drafted, drafting, started, prototype, beta, alpha, testing, tested, implemented, in development, existing, delivered, unblocked, half done, partly done, partially done, almost done, nearly done, mostly done | 2 |
| Idea | any other text: no recognised word | 1 |
| None | no status line | 1 |

"Not live", "half done", "almost done", "nearly done", "unblocked", "alive" and "live soon" do not count as live or blocked. "Half done" reads as local; "not live" with nothing else reads as an idea.
A status with no recognised word counts as an idea, heat 1, and the doctor says so. It never reads as built.

This reads words, not meaning: "Design done, code not written" still reads as live. Check the doctor's `Status:` lines, and
reword a status that reads wrongly. Only call something live if it really is out.

## Ledger (`ledger`)

Only the section headed `## Items for the user` is read, up to the next `#` or `##` heading or the end of the file.
Each item starts with `- `, `* `, `+ ` or a number such as `1. ` at the start of a line. Anything else continues the
current item. Words before the first item are not shown, and are reported as a problem. So are a repeated heading and a
code fence that never closes.

```markdown
## Items for the user

- **Look at this:** one thing to do,
  continued on an indented line.
- ~~**Finished thing**~~ Resolved: crossed-out items show as SLAIN.
```

Spark picks from these, using the leading bold text as its label, and skips labels that say "waiting on".

## Decision log (`decisions`)

Any `##` or `###` heading that starts with an ID ending in digits, or with a date, is one decision. Restating a decision
recorded elsewhere is fine: keep its words and date, and link where it came from.

```markdown
## ABC-001: First decision

## 2026-01-31 Second decision

### DEF-TWO-002 - Third decision
```

## Words (`workspace_dashboard/words.json`)

Replace the placeholders, then delete each `"placeholder": true`.

- **Quotes (`lines`):** each needs `text` and `file`. The text must appear word for word in that file, inside this
  workspace, or it is dropped, and it needs at least 3 words and 12 characters. The page names the file as the source.
  `who` replaces that only if those words also appear in the file. Files that look private, the kit's own files and
  unedited starters never count as evidence.
- **Friends:** a friend's name must be playful and invented, never a real person. The page labels all comments as flavor
  text, and the build notes a name that looks real. The comment must use `{number}` names, or a quote whose `evidence`
  appears in the named `file`. A filled-in comment with neither is dropped. So is a comment whose number is absent or zero,
  and one holding a typed number, in digits or words, that its `evidence` does not contain. You may delete a friend you
  have no use for. A complete example:
  `{"pic": "avatar_1.png", "name": "soup_ladle", "says": "{tests} test files. And: We keep the receipts.", "evidence": "We keep the receipts.", "file": "docs/notes.md"}`
- **Late night (`late_night`):** a comment shown after midnight. It starts as a placeholder too. `{clock}` is the browser's
  time and works only here. This comment states no fact about the workspace, so it is exempt from the evidence rule.
- **Marquee and about:** use `{number}` names, not typed figures. The build notes any typed number there.
- **Profile:** while it is a placeholder its name is labelled, its interests, mood and network line are hidden, and the
  Friend Space counts only friends that are no longer placeholders. Do not claim anything about the owner that this
  workspace does not show, and do not infer the owner's name from Git.
- **Paintings:** `key` is a file name in `workspace_dashboard/art/web/` without `.jpg`. Credit defaults to "Art that came with
  this kit", and the page lists it as still to fill in. Ask whether the workspace's owner made them. If so, set `credit` to
  "Your art"; if not, set a true credit or swap them. To use other images, run
  `make_art.py --originals`, or copy a `.jpg` into that folder.
- **Loops:** the `when` lines for Spark, Campfire and Beacon are the size of the sitting, not a measurement. Change them to suit.
- **Mascot:** `image` and the `word` that summons a crowd of them. Set `"mascot": {}` to turn it off.

- **Other starter text:** the heading, song, mascot, webring, badges and loop titles are the look and voice. They are kept as
  defaults and are not claims, so changing them is optional. In a single-product repository you may reword "projects" as
  "features".

Numbers: `commits`, `decisions`, `files`, `projects`, `under_way`, `tests`, `heat`, `next_mark`, `mark_steps`, and
`preserved`, `live_total` or any `count_files` name when those exist. `under_way` counts cards being worked on: built locally or blocked, not idea, no-status
or live cards. `tests` counts code files that look like tests, not documents in a test or spec folder. Override it in `count_files`.
A card shows HOT! only if it has a status beyond idea and its own linked files changed in the last 14 days. If every card
would qualify, none shows it.

## Config (`dashboard_config.json`)

| Key | What it does |
|---|---|
| `title`, `tagline` | The page header. The title defaults to the folder's name |
| `overview`, `ledger`, `decisions` | Where those documents are |
| `links` | Extra rows in Living documents: `{"label": "Guide", "path": "docs/guide.md"}` or `{"label": "Site", "url": "https://..."}` |
| `live_record` | Optional count of things out in the world: `{"path": "RELEASES.md", "section": "Shipped", "match": "optional pattern"}` counts table rows and `- ` lines. Use it only for a real record of what is released, such as tags, a release page or a deploy log. A list of versions with no sign of release does not count. Leave `null` to claim nothing |
| `count_files` | Extra counted numbers: `{"stories": ["stories/.*\\.txt$"]}`, or a new pattern list for `tests` |
| `activity_skip`, `activity_skip_types` | Paths and file types left out of the recent activity lists |
| `unlinked_skip` | Paths left out of "Not linked from any project" |
| `hidden_folders` | Added to the hidden folder list, for bulky folders |
| `secret_patterns` | Added to the private-file patterns. The defaults cannot be removed |
| `status_words`, `heat`, `heat_marks` | How statuses map to heat, and the marks to reach |
| `poll_seconds`, `watch_seconds` | How often the open page reloads, and how often the updater rebuilds |
| `editor` | `vscode`, `cursor`, `zed`, `none` or a URL template holding `{path}`, and optionally `{line}`. If you cannot tell which they use, keep the default and ask under Items for the user |
| `motion` | `always` (the default look) or `respect-os`. Stop the fire works in both |
| `reveal_links` | `true` shows "Show in Explorer" on Windows. See `optional/explorer_links`. It needs approval to install |
| `preservation_glob` | An optional convention: where logs of preserved copies are. A log is a tab-separated file with a header row and one row per copy. If none exist, nothing is claimed. Files outside this workspace are not counted |
| `max_folder_rows`, `max_file_rows` | Caps on file rows. Extra files show as "+N more", and the counts stay true |
| `output` | Where the page goes: an `.html` path that is free or already this kit's page. Anything else is refused, and the default is used. Add the page and its `_data.js` to your own ignore rules if you move it |
| `id` | Overrides the storage and lock id, which otherwise comes from the folder path. Never copy one to another workspace: the two would share browser storage. The doctor warns if it sees that |

## Opt-in extras

None is installed by default. See `workspace_dashboard/optional/`.

- **Commit check:** `pre-commit.sample` blocks work committed without a documentation change. Read it first.
- **Explorer links:** `explorer_links/` registers a per-workspace link type for the current Windows user. Ask first.
- **Screensaver (Windows):** `screensaver/` shows the dashboard full screen when the PC is idle. It changes the person's screensaver setting only with `-Activate`. Ask first. See its README.
