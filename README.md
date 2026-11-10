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

The page is local and is not for sharing: it holds this computer's folder paths. Files whose names look like credentials
(`.env`, `*secret*`, `*credential*`, `*token*`, `*api key*`, `*.pem`, `*.key`, `*.pfx`, `*.p12`, `*.kdbx`, `id_rsa`, `id_ecdsa`, `.netrc`, `.npmrc`, `.pypirc`, `service-account*` and others) are left off every list,
their names are taken out of document text and commit messages, including names only in Git history, and their contents are never read. The page shows only how many were left
off. That matching is by name, so a harmless `tokenizer.py` or `vault_notes.md` is hidden too. A name shaped like a credential, such as `pass=x1y2z3.txt`, `auth=FaKe7abc.txt` or `dbpass-FaKeAb5.txt`, is hidden the same way. A hidden name that is a
single plain word, such as a folder called `tokens`, is only taken out of text when written as a path: "Rotate the tokens"
stays as written. A line in a document, commit message or guestbook that matches a credential form, such as a known key
format, `Authorization: Bearer x`, `token: x`, `secret = x`, `pass: x`, `passphrase: x`, `<password>x</password>`, `Cookie: a=x`
or `mysql -px`, is withheld whole. Link targets are also read percent-decoded. A `words.json` entry holding one is dropped.
Looser forms count only when the value looks generated, meaning at least 6 characters with letters and digits, or 8 with inner
capitals: plurals (`tokens: x`), suffixed or glued labels (`TOKEN_PROD=x`, `dbpass=x`), `key: x`, `token (prod): x`, `token -> x`,
`password - x`, a value in brackets (`secret: [x]`), `--token x`, `pw: x`, `creds: x`, `pass word: x`, `login: a / x`, and `?sig=x` or `?key=x` in an address.
`passcode: x`, `sshpass -p x` and `curl -u a:x` count like `pass: x`. Labels that are everyday words need a value that looks strongly generated, meaning 8 or more
characters with inner capitals, or three changes between letters and digits, or 12 or more unbroken characters with letters and digits: `pin: x`, `auth: x`, `session: x`,
`password x`, `password as x`, `password | x` and `the password is x`. So does a phrase such as `hall pass:`, `boarding pass:`, `bypass:`, `cache key:` or `answer key:`, which otherwise stays as prose.
Each line is also read with HTML entities decoded, invisible characters removed, common Cyrillic and Greek lookalike letters replaced and spaced letters joined, and a Markdown link's label is read alone.

The matched value is then removed wherever else it appears on the page, in any case. A value of 8 or more characters that looks
generated also goes when it sits inside a longer word, is split by Markdown marks, or is written in base64. A plain word or a
number goes only as a whole word, and base64 of it stays. Other encodings and altered copies stay. The build note says how many
lines were withheld and from which file, including `dashboard_config.json`. A last scan stops the build if a matched value or form
still reaches the page, except a value that is only a number, which could be a port or a time. That scan reads the page's text with tags removed and escapes decoded.

Some ordinary lines are withheld too, because they fit a form: `Secret: door`, `pass: first`, `Next step for the password: rotate`. The note reports them. Reword the line to keep it.
A word in the list of non-values after a label, as in `password: required` or `API key: none`, stays and does not stop the build.

The note for a commit message says the credential is in Git history, because it stays there until that history is rewritten.

**Detection is by pattern and can miss things.** A withheld line does not mean the rest of the file or the page holds no
credential, and no note means only that no pattern matched. These can still reach the page: a plain password with no label,
one in a sentence ("the password is x"), one in a table cell, a single word after a colon followed by two or more words, which
reads as prose, a plain word after a looser form (`tokens: hunter`, `--password hunter`), a short number after `pass:` or `token:`
(under 4 digits, or with other text on the line, or after other words, as in "Tests pass: 1200"), a value that does not look generated enough after `pw:`, `creds:`, `pin:`, `auth:` or `session:`
or after `password` with no separator (`pin: 1234`, `pw: hunter`, `password hunter`), letters that look alike from other alphabets beyond the common Cyrillic and Greek ones, labels split other ways
(`p-a-s-s-w-o-r-d: x`), other commands that take a password, and file names of other shapes.
Values under 4 characters go with their line but are not searched for elsewhere. Keep credentials out of
the documents the page reads, and do not share the page.

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
5. Browser storage left behind is a few small `wsdash-` keys, and it does nothing.

## In this kit

| Path | What it is |
|---|---|
| `START_HERE.md` | Steps for a Claude session in the other workspace |
| `install_dashboard.py` | The installer |
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
