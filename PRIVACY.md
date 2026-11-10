# Privacy: the full rules

The exact rules the dashboard builder uses to keep credentials and private names off the page. Most people only need the short version in the [README](README.md#privacy). This file is for anyone checking or changing the builder.

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
