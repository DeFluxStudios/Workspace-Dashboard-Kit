# Workspace dashboard kit

This folder gives another workspace its own dashboard: the same red, black and blazing-blue late-90s page, with that
workspace's projects, decisions, files and open questions on it. Nothing from the workspace it came from comes along
except the look and four paintings, which show the credit "Art that came with this kit" until the session asks who made
them and sets the credit, "Your art" if that is you. The paintings are by DeFluxStudios and may be shared under CC BY 4.0
with that credit (see License below). Version: see `VERSION`. This is a test build.

## The one prompt

Open Claude in the other workspace and paste this:

```
Read <path to this kit>/START_HERE.md and follow it to create
this workspace's dashboard from this workspace's own data.
```

Replace `<path to this kit>` with where this folder is on this PC. On another PC, unzip `workspace_dashboard_kit_<version>.zip`
first and use that folder's path. Use the zip with the highest version: an older one may hold problems since fixed.

## By hand

Python 3.9 or newer. Nothing else is needed: no packages, and Git is optional.

```
python install_dashboard.py <workspace> --dry-run          shows what would happen, changes nothing
python install_dashboard.py <workspace> --name "My Title"  installs and builds once
```

Then open `Open_Dashboard.cmd` in that workspace (`sh Open_Dashboard.sh` on Mac or Linux). Until someone fills it in, the
page says plainly what is missing, and its starter friends are labelled as placeholders.

## What gets written where

Everything is new files. An existing file is listed as kept and left alone, including on a re-run. `--force` replaces only
the kit's own program files, never your config, words, guestbook or documents, and never a launcher of your own. If you
already have an `Open_Dashboard.cmd` that is not the kit's, it stays, and the installer prints the direct build command
instead. A page or data file already at the page's path that is not the kit's stops the install. The `output` setting
cannot replace a file of yours either.

| In the workspace | What it is |
|---|---|
| `dashboard_config.json` | Everything specific to this workspace |
| `Open_Dashboard.cmd`, `Open_Dashboard.sh` | Build, start the updater and open the page |
| `docs/Works_in_Development.md`, `docs/project-ledger.md`, `docs/decision-log.md` | Starters, only where missing. An existing config can point at other documents instead |
| `workspace_dashboard/` | The generator, theme, art, `words.json`, guestbook, how-to-fill note, and `starter_docs.json`, which lets the page leave unedited starters out of its counts |
| `workspace_dashboard/Workspace_Dashboard.html` and `_data.js` | The generated page. Ignored by Git through `workspace_dashboard/.gitignore`, so your own `.gitignore` is untouched |

The installer does not edit `.gitignore`, hooks, your editor settings or the registry, and does not start the updater.

## Two dashboards at once

They do not collide. Each workspace gets its own updater lock port, hashed from its folder path into 49152-65535, with
fallbacks if something else holds the port. If every fallback is taken, the updater says so and does not start; a build
by hand still works. Browser storage is namespaced the same way, so visitor counts and "Stop the fire" stay separate. Do
not copy a config's `id` to another workspace: the two would share browser storage.

## Privacy

The dashboard is a local page for your own PC. It is not meant to be shared, because it shows your folder paths.

- **Secrets stay off the page.** Files that look like credentials (`.env`, `*.key`, `*secret*`, `id_rsa` and similar) are never read or listed. The page only says how many were left out.
- **Lines that look like passwords or keys are withheld**, for example `password: x`, `token: x` or `Authorization: Bearer x`, in documents, commit messages and the guestbook.
- **A final check stops the build** if anything that looks like a secret still reaches the page.
- **It errs on the safe side.** A harmless file such as `tokenizer.py`, or a line such as `Secret: door`, can be hidden too. The build note tells you what was withheld so you can reword it.

- **Detection is by pattern and can miss things.** Don't keep real passwords or keys in workspace documents.

The full rules, with every pattern and exception, are in [PRIVACY.md](PRIVACY.md).

## Optional screensaver (Windows)

The kit can also show the dashboard as a screensaver. It is not installed by default. After the install, see
`workspace_dashboard/optional/screensaver/README.md`: one PowerShell command builds it from readable source, and
`-Activate` makes it the screensaver (the old setting is saved and `-Remove` puts it back). The full beginner guide,
with a prompt for an AI assistant, is `payload/optional/screensaver/GUIDE.md`.

## How to remove it

1. Close the updater window, if it is running.
2. Delete `workspace_dashboard/`, `dashboard_config.json`, `Open_Dashboard.cmd` and `Open_Dashboard.sh`.
3. Delete the three starter documents, if you did not keep them.
4. If you enabled the opt-in Explorer links: run `install_explorer_links.ps1 -Scheme ... -Uninstall` before step 2.
5. If you installed the opt-in screensaver: run `workspace_dashboard\optional\screensaver\install_screensaver.ps1 -Remove` before step 2.
6. Browser storage left behind is a few small `wsdash-` keys, and it does nothing.

## In this kit

| Path | What it is |
|---|---|
| `START_HERE.md` | Steps for a Claude session in the other workspace |
| `install_dashboard.py` | The installer |
| `PRIVACY.md` | The full privacy rules the builder follows |
| `payload/` | What is copied: `build_dashboard.py`, `theme.css`, `theme.js`, `make_art.py`, `art/web/`, `optional/` |
| `starter/` | Templates for config, words, guestbook and the three documents, and `HOW_TO_FILL.md` |
| `psychology_checklist.md` | The design rules behind the fire section, mapped to the page |
| `kit_tests/` | Tests. Run `python kit_tests/test_kit.py`. Local and simulated, never a real workspace |
| `make_kit_zip.py` | Rebuilds the zip beside this folder |

Art: the flames, stars, cursor, avatars, die, emblem and mascot are all generated by `payload/make_art.py`, which needs
numpy and Pillow. It is optional, because they ship ready made.

## License

- **Code:** GNU General Public License version 2. See [LICENSE](LICENSE).
- **Documentation and artwork:** Creative Commons Attribution 4.0 (CC BY 4.0). Credit the artwork to DeFluxStudios.
- See [NOTICE.txt](NOTICE.txt).
