# Start here

You are a Claude session in some workspace, and you have been pointed at this folder to give that workspace a dashboard:
one local page, generated from the workspace's own files. You need no outside knowledge. Follow these steps in order.

## What the developer wants

These are the wishes of the developer this kit was made for, and they are the kit's defaults. They are not facts about
whoever owns the workspace you are in, unless that is the same person.

- **Look:** red, black and blazing light blue with sound color theory, in an animated late-90s homepage style. Keep it.
  The reasons are in `psychology_checklist.md`.
- **Motion stays on:** the page ignores the browser's reduce-motion signal, and offers a visible "Stop the fire" switch.
  Do not "fix" this for that developer. If someone else owns this workspace, ask once whether they want motion forced on,
  and set `"motion": "respect-os"` if they do not. If you cannot ask now, list the question under "Items for the user".
- **Visible means real:** the developer relies on what is visible. Anything new must be reachable from the dashboard.
- **No pressure:** no login pressure, breakable streaks, expiring rewards or losable progress.
- **Plain truth:** every number comes from real files. A page that says "not known yet" is fine. A page that guesses is not.

## Rules while you work

1. Read the target workspace first, before changing anything.
2. Follow the workspace's own instructions over this kit's, wherever they differ.
3. Fill the overview, needs and words ONLY from evidence in that workspace.
4. Never invent facts, progress or quotes. Unknowns go under "Items for the user" in the ledger.
5. Do not overwrite existing files. Show what you would change first.
6. Never put credentials on the page. Do not open files that look like credentials, even to check them.
7. If the workspace's rules require approval to add files, ask once before installing.
8. Do not write em dashes in text a person reads on the page.

## Steps

Run the commands from the workspace root. Do not commit what the install adds: tell the developer what is untracked, so
they can decide.

**1. Read the workspace.** Read its CLAUDE.md, README and any contributing or agent rules, and look at its folder tree
and Git log. Note: what its projects are, where it already records status, decisions and open questions, what its tests
look like, and what it says about adding files.

**2. Preview.** From anywhere, run:

```
python <this kit>/install_dashboard.py <workspace> --dry-run --name "A Good Title"
```

Nothing changes. Tell the developer what would be added and what the workspace rules say about it. Ask once if those
rules require it.

A document counts as the workspace's own overview, ledger or decision log only if it already matches the formats in
`starter/HOW_TO_FILL.md`. If it does, write a `dashboard_config.json` in the workspace root pointing at it first, using
`starter/dashboard_config.json` as the shape, so no starter is made beside it. Set `title` in that file too, because
`--name` is not applied to a config that already exists. An ordinary TODO or changelog does not match: let the starter sit
beside it, copy the facts across with a link back, and ask before adding headings to the developer's own files.

**3. Install.**

```
python <this kit>/install_dashboard.py <workspace> --name "A Good Title"
```

It only adds files, prints each one, and runs one build. It will not replace anything, and it refuses a page it did not
write. Re-running is safe. What it writes is listed in `README.md`. Do not use `--force` unless asked: it replaces the
kit's own program files.

**4. Fill it in.** Read `workspace_dashboard/HOW_TO_FILL.md` in the workspace for the exact formats.

- **Overview:** one `###` card per real project, with a status taken from what you can actually see. In a single-product
  repository, use one card per major feature if the features have different states, otherwise one card. Say which you
  chose in your report, because the percentage on the page depends on it.
- **Ledger:** real items needing the developer's attention. Everything you could not determine goes here, as a question.
- **Decisions:** only decisions the workspace records, or that you make with the developer now. Restating a recorded
  decision as a heading is fine: keep its words and its date, and link where it came from.
- **Words:** replace placeholders in `workspace_dashboard/words.json`. Quotes must be copied word for word from real
  files in the workspace; the build drops any that are not found. A friend's name may be playful and invented, but the
  comment must use a `{number}` or a quote whose `evidence` appears in the named file. Remove a `"placeholder": true`
  only once that entry is really replaced, including `late_night` and `profile`. Leave a placeholder rather than making
  something up. Deleting a friend you do not need is fine. Friends must be invented characters, never real people. The
  `late_night` comment and its `{clock}` are exempt from the evidence rule. The heading, song, mascot and other look and
  voice lines stay as defaults, and a single-product repository may reword "projects" as "features".
- **Paintings:** they came with the kit and show a neutral credit until someone confirms it. Ask once whether the owner of
  this workspace made them. If so, set each `credit` to "Your art". If not, set a true credit or swap them. If you cannot
  ask now, leave the default and list the question under "Items for the user".
- **Config:** title, tagline and the `editor` they use. If the editor is not known, keep the default and ask under Items
  for the user. Do not infer the owner's name from Git. Set `live_record` only if the workspace has a real record of what
  is released, such as tags, a release page or a deploy log, and `hidden_folders` for anything bulky.

**5. Rebuild and check.** The commands after the first only check: they do not change the page.

```
python workspace_dashboard/build_dashboard.py
python workspace_dashboard/build_dashboard.py --doctor
python workspace_dashboard/build_dashboard.py --check
```

Fix what the doctor calls close and what the check calls broken. Read every "Note" and "Status" line: each status line
says how a card's words were read, so correct any that read wrongly. Rebuild after each fix. Then open
`workspace_dashboard/Workspace_Dashboard.html` and look: quotes, Spark, Campfire, the rune ring, comments. Look for hidden
files too: no name matching `.env`, `*secret*`, `*credential*`, `*token*`, `*api key*`, `*.pem`, `*.key` or `id_rsa` may
appear. Patterns cannot catch every name, so also look by eye for private-looking ones such as `mykey.txt`, and add them to
`secret_patterns`.

**6. Make it reachable.** Suggest a short addition to the workspace's CLAUDE.md or README, with consent and never by
overwriting, along these lines: "Dashboard: run Open_Dashboard. Keep new work linked from the overview document, and put
what needs attention under Items for the user." Mention that the page is local and holds folder paths, so it is not for
sharing.

**7. Report.** Tell the developer: how to open it (`Open_Dashboard.cmd` on Windows, `Open_Dashboard.sh` elsewhere), what
was added and is untracked, how many placeholders remain, and what you could not determine. Say that anything you tested without opening
a real browser was simulated.

## If something goes wrong

The build reports problems on the page and in the console and keeps going. A bad word, a missing document, no Git or a
broken link is never fatal. It stops, without writing, in three cases, and each says what to do:

- A page or data file is already at the output path and is not this kit's. Move it, or set `output`.
- A theme file is missing. Run the installer again.
- A hidden file's name or a credential would have reached the page. The message names the source, never the thing itself.
  Fix it there, and do not work around the check.

Removing the kit is in `README.md`.

## Not installed unless asked

Commit check (`optional/pre-commit.sample`) and Explorer links (`optional/explorer_links`). Offer them. Do not enable
them on your own: one touches the workspace's hooks and the other touches the Windows registry.
