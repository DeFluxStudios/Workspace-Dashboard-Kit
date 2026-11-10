# Changelog

## 0.1.0-test.7 (2026-11-09)

- **Screensaver (optional, Windows):** `payload/optional/screensaver/` (installed to `workspace_dashboard/optional/screensaver/`). Source only: `install_screensaver.ps1` compiles `DashboardSaver.cs` with the Windows C# compiler and points it at the workspace's own page. `-Activate` makes it the current user's screensaver after saving the old setting; `-Remove` puts it back. Uses Edge or Chrome in kiosk mode with its own profile. Tested by a simulated install into a temporary workspace (build and page path); not yet run as a real screensaver on another PC.

## 0.1.0-test.6 (2026-11-04)

Fixes from a fifth review. Every result is still from simulated test workspaces in temporary folders.

- **Credentials:** new forms: `pw:`, `passcode:`, `creds:`, `pass word:`, `login: a / x`, `sshpass -p x`, `curl -u a:x`. With a strongly generated value: `pin:`, `auth:`,
  `session:`, `password x`, `password as x`, `password | x`, `the password is x`. Each line is also read with entities decoded, invisible characters removed, common lookalike
  letters replaced and spaced letters joined. The README lists what stays unmatched.
- **Markdown links:** a link's label is read alone, so `[token -> x](url)` and `[--token x](url)` are withheld. A strongly generated value directly after a looser label is withheld even as link text.
- **Last scan:** reads text with tags removed and escapes decoded, attribute values included, so `password: required` no longer stops a build, and `token -&gt; x` is seen.
  The same reading picks the document named in the stop message. A non-value word is also ignored after `password=`.
- **Build note:** one config line gives one note, whichever field holds it. Commit messages have their own wording: the credential is in Git history.
- **Ordinary lines:** `hall pass:`, `boarding pass:`, `bypass:`, `cache key:`, `answer key:` and similar stay unless the value looks strongly generated. README gives examples still withheld.

## 0.1.0-test.5 (2026-11-04)

Fixes from a fourth review. Every result is still from simulated test workspaces in temporary folders.

- **Credentials:** new forms: plurals, suffixed and glued labels, `key:`, `token (prod):`, arrows and dashes, a fullwidth colon,
  bracketed values, `<password>`, CLI flags, `mysql -p`, `Cookie:`, `?sig=`, and `pass: 74251` alone on a line. Looser forms need
  a value that looks generated, so prose and counts such as `max_tokens: 4000` stay. The README lists what stays unmatched.
- **Copies of a value:** now removed in any case. A generated-looking value also goes inside a longer word, split by Markdown
  marks, or in base64. README says which copies stay.
- **Encoded links:** a percent-encoded form in a link target is read decoded.
- **Config:** a credential line in `dashboard_config.json` is now reported in the build note.
- **File names:** credential-shaped names such as `dbpass-FaKeAb5.txt`, `auth=` and `key=` are hidden.
- **Stop message:** says "a name matching a hidden-name pattern" and checks the original documents as a source.
- **Counts:** the build line and `--doctor` count open items, and add resolved ones separately.
- **Doctor:** a status whose recognised word is after a semicolon says the first clause held no recognised word.

## 0.1.0-test.4 (2026-11-04)

Fixes from a third review. Every result is still from simulated test workspaces in temporary folders.

- **Credentials:** a line matching a credential form, now including `Authorization: Bearer`, `token:`, `secret =`, `pass:` and
  `passphrase:`, is withheld whole, as is a whole private key block, and the matched value goes from everywhere else on the page,
  including file lists. Prose such as "Rotate the tokens" stays. The last scan covers these too.
- **Truthful note:** the build note gives the number of lines and the file, says detection is by pattern and can miss things, and
  never says anything is clean. README matches.
- **File names:** more private key and credential names, such as `id_ecdsa`, `*.kdbx`, `*.jks`, `*.ppk`, `_netrc`, `.s3cfg`.
- **Header:** "Everything is committed" only when Git shows nothing at all, including the dashboard's own files.
- **Status:** a status with no recognised word counts as an idea, heat 1, never built locally. `status_words` has a `local` list.
- **Low items:** "Go to the project" is hidden with no project to go to, and a Spark no longer shows a one-word bold lead alone.
- **Zips:** older zips of this kit removed from `packages/`, keeping only this version's.

## 0.1.0-test.3 (2026-11-04)

Fixes from a second review. Every result is still from simulated test workspaces in temporary folders.

- **Privacy:** file-like words matching the secret patterns are hidden from commit messages and documents even if the file is
  gone, and the last scan checks for them. More name patterns, such as `prod.env.bak`, `env.production`, `creds.txt`, `auth.json`.
- **Truth on the page:** the paintings show a neutral credit until someone confirms it, and the page and doctor say so. Starter
  words no longer claim decisions have reasons. `tests` counts code files only. `under_way` leaves out idea and no-status cards.
  HOT! needs a change in the last 14 days, uses the sidebar's dates, skips idea cards, and shows nowhere if every card would qualify.
- **Friends and claims:** a filled-in comment with no number and no evidence is dropped, as is a spelled-out number with no
  evidence. Notes for a typed number in the marquee or about, a real-looking friend name, and the starter profile name.
- **Installer:** reads a UTF-16 config as the generator does, and refuses a document path that is a folder the kit needs, or
  one too long, before the first write. A forbidden character in `output` falls back to the default with a note.
- **Updater:** the launcher passes the full script path, the lock reports its PID, and the doctor prints it.
- **Instructions:** run from the root, do not commit, what to do if nobody can answer, `{clock}`, and which starter text may stay.
  The placeholder note names what is left. The Friend Space heading is neutral while the profile is a placeholder.
- **Profile:** removing its `placeholder` flag now really marks it as filled in. The flag used to come back from the defaults.
- **Zip:** `make_kit_zip.py` warns about older zips beside the new one, and does not delete them.

## 0.1.0-test.2 (2026-11-04)

Fixes from review. Every result is still from simulated test workspaces in temporary folders.

- **Builds that failed:** a hidden file beside a longer-named visible one, a hidden name matching the workspace's own
  folder, and Python 3.9 all build now. Python 3.8 is no longer claimed.
- **Files protected:** `output` cannot replace a file of yours, a page or data file that is not the kit's stops the install,
  an existing launcher stays even with `--force`, and a different generator is not run. Paths are checked before the first
  write. Bad config, words, guestbook or theme files give a plain message, not a traceback.
- **Truth on the page:** "half done" and similar no longer read as live, and "not started" reads as an idea. The doctor prints how
  each status was read. Non-list lines, repeated headings and unclosed fences are reported. "Live" needs a running updater.
  Kit files and unedited starters are not counted as work. Quotes need 3 words and 12 characters and are credited to their file.
  A friend comment with an uncounted digit is dropped, and all comments are labelled flavor text. Placeholder profiles claim
  no friends, mood or network. Files with no uncommitted change use their commit date.
- **Privacy:** more credential forms and file names. Hidden names are also caught percent-encoded, wrapped and split by
  Markdown, while a plain word such as `tokens` is only treated as a name when written as a path. Tokens in file names, the title and the
  tagline are hidden, and a last scan covers them. A stop message names the source, never the thing itself.
- **Updater:** a copied `id` no longer stops another workspace's updater, and with no free lock port the updater does not start.
- **Instructions:** the rebuild command is in the steps, and the doctor and check say they do not rebuild. Added rules for matching
  documents, friends, single-product repositories, the owner, the editor and `live_record`. Reworded the developer's wishes as kit
  defaults, and the session now asks about motion and "Your art" if someone else owns the workspace.
- **Kit contents:** no absolute path in the README, and the list of source words moved out of the kit.

## 0.1.0-test.1 (2026-11-04)

First test build. Not yet used in a real workspace: every result so far is from simulated test
workspaces in temporary folders.

- Installer that only adds files, and generator with everything workspace-specific read from `dashboard_config.json`.
- Builds with no Git, no commits, no documents, a BOM, or a path with spaces and non-ASCII characters.
- Hidden file names, per-workspace updater lock port and browser storage, tolerant parsers, a doctor mode.
- Starter words with labelled placeholders, generated avatars, die, emblem and mascot, and four paintings as "Your art".
