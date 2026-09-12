# Casio EX-word DATAPLUS 3 — jailbreak exploration

Goal: see what we can do with the dictionary beyond stock (content, file access, firmware).
Rule: read-only first. Nothing gets written to the device without a backup and an explicit go-ahead.

Tools: a patched [libexword](https://github.com/brijohn/libexword) that builds on Apple Silicon macOS, a read-only crawler (`crawl.py`), and a keep-alive session (`live.sh`). Device backups are personal data and are kept out of this repo.

## Quick start (macOS)

```sh
brew install automake libtool libusb readline
cd libexword
PATH="/opt/homebrew/opt/libtool/libexec/gnubin:$PATH" autoreconf --install --symlink
CPPFLAGS=-I/opt/homebrew/opt/readline/include LDFLAGS=-L/opt/homebrew/opt/readline/lib LIBS=-liconv ./configure
make && cd ..
./crawl.py --selftest
# turn on USB mode on the dictionary, then (read-only; copies files into dumps/):
./crawl.py library > session-crawl-library.log
```

## Layout

- `README.md` — this file: device info + findings log
- `libexword/` — vendored [libexword](https://github.com/brijohn/libexword) @ `f2a57ae` (GPL-2.0-or-later, see `libexword/COPYING`) with our macOS fixes
- `patches/libexword-macos.patch` — our changes to libexword vs upstream `f2a57ae`
- `dumps/<mode>/<medium>/` — files copied off the dictionary (backups; never edit in place). **Not in the public repo** (favourites, lookup history, copyrighted dictionary text); kept in a separate private repo
- `session-NN-*.log` — raw output of each device session
- `payloads/` — files we create to send *to* the dictionary (vs `dumps/`, which come *from* it). `payloads/generated/` holds the ~11 MB of limit-test files and is git-ignored; regenerate with the snippet in "Limit tests" below
- `live.sh` — keep-alive session: one connection held open, commands sent with `echo '<cmd>' > .live.in`, 30 s `model` ping. Saves a USB toggle per probe.
- `crawl.py` — read-only crawler: `./crawl.py text > session-NN-crawl-text.log` maps one connect mode in one USB toggle, copying files to `dumps/<mode>/<medium>/`. Only allows `connect`/`list`/`capacity`/`model`/`setpath`/`get`/`disconnect`. `./crawl.py --selftest` needs no device.

## Device (detected 2026-09-11)

| Field | Value |
|---|---|
| USB name | CESG502 |
| Manufacturer | CASIO (Casio Computer Co., Ltd.) |
| Vendor / Product ID | `0x07cf` / `0x6101` |
| Speed | Up to 12 Mb/s (full speed) |
| Connection | Through a Genesys USB2.0 hub |
| Mass storage? | No — speaks Casio's own protocol; no volume under `/Volumes` |

Needs USB mode turned on from the dictionary's menu before the Mac can see it.

## Findings log

- 2026-09-11 — Device enumerates as CESG502 (`07cf:6101`). No `/Volumes` entry, as expected.
- 2026-09-11 — `libexword/models.txt` lists DATAPLUS 3 (XD-GW9600, XD-SW4800) as `07cf:6101`. Same USB ID as ours, so the protocol should match.
- Protocol = modified OBEX (`libexword/protocol.txt`). Three connect modes: `library` (add-on dictionaries), `text` (TextLoader files), `cd` (CDLoader audio).
- Two storage roots: `/_INTERNAL_00` (internal memory) and `/_SD_00` (SD card).
- Auth quirk (from protocol.txt): in library mode, calling `_List` makes commands that need auth work without it. Worth checking on our device.
- Add-on dictionaries are encrypted. The key is derived from a `_CryptKey` exchange; `dict decrypt <id>` downloads and decrypts one.
- 2026-09-11 — **Session 01 (read-only)**, log in `session-01-readonly.log`. Connected in library mode, region `ja`, with no auth needed.
  - `model` → `gy131,ON,0100`, sub-model **`gy355`**. `models.txt` doesn't list gy355 (XD-SW4800 = gy350, XD-GW9600 = gy392), so this variant is undocumented upstream. The model number printed on the device (XD-…) would pin it down.
  - `dict list` → empty: no add-on dictionaries installed, which means nothing for `dict reset` to wipe.
  - Internal memory root (`/_INTERNAL_00`), `<x>` = directory:

    | Entry | Guess (not yet confirmed) |
    |---|---|
    | `<sys_bak>` | System backup |
    | `<data>` | User data |
    | `<cj900>`, `<cj900_01..05>`, `<cj901>`, `<cj901_01..05>` | Content slots; 12 numbered dirs look like TextLoader/add-on storage |
    | `<stdy0>` | Study / vocab-drill data |
    | `<hyaku>` | Hyakunin Isshu (百人一首) game data |
    | `<numplace>` | Number-place (Sudoku) game data |
    | `<temp.inf>` | Listed as a directory despite the `.inf` name |
    | `fav.inf`, `line3.inf`, `drvvewer.inf`, `siorivi.inf`, `jpush.wrk`, `jlpush.wrk` | Settings / history / work files |
  - `setpath sd://` and `setpath mem://` were rejected (`Format (sd|mem)://<path>`): a bare root isn't accepted. The root is `mem:///` (three slashes); a folder is `mem:///data`.
  - `capacity` → `52428800 / 52428800` (50 MiB / 50 MiB). **Unresolved**: `protocol.txt` says the numbers are total / *used*, but the code names the second field `free` and only byte-swaps it (`exword.c:708`). So this is either empty or full. Few files + no add-ons suggests "free", but that isn't proven.
- 2026-09-11 — **`disconnect` drops the device off USB.** After session 01 the dictionary left the bus (`ioreg` no longer showed CESG502), matching protocol.txt ("shuts down the usb device"). USB mode has to be re-enabled on the dictionary before every session. `exit` doesn't avoid this: `quit()` calls `disconnect()` (`libexword/src/main.c:229`). Workaround: end piped scripts with no `exit` line. End of input breaks the loop and the tool quits without disconnecting (relies on the EOF fix below).
- 2026-09-11 — Direction chosen: **back up & map first**, no writes to the device.
- 2026-09-11 — **Session 02 (read-only)**, log in `session-02-explore-backup.log`.
  - The no-`exit` workaround keeps the dictionary on USB, **but see session 03: the next `connect` then fails.** Still investigating; for now USB mode needs a toggle between sessions either way.
  - Backed up all 6 root files to `dumps/library/_INTERNAL_00/`, all `OK, Success`:

    | File | Bytes |
    |---|---|
    | `jpush.wrk` | 1,193,984 |
    | `jlpush.wrk` | 77,824 |
    | `drvvewer.inf` | 18,004 |
    | `siorivi.inf` | 4,000 |
    | `fav.inf` | 502 |
    | `line3.inf` | 24 |
  - No SD card inserted (`setpath sd:///` → `SD card not inserted.`).
  - **Every `setpath mem:///<dir>` returned `Not found`** (data, sys_bak, cj900, cj900_01, cj901, stdy0, hyaku, numplace, temp.inf). The folders can be listed but not entered yet.
    - `_setpath` (`main.c:194`) builds the path correctly: `mem:///data` → `\_INTERNAL_00\data`.
    - `exword_setpath` (`exword.c:606`) sends the **whole path in one SETPATH packet**: UTF-16 name header, flags byte `2` (don't create) or `0` (mkdir). The root works that way; subfolders don't. Next: capture the packets with `set debug 5`.
  - Capacity clue: the root holds ~1.3 MB of files yet reads `50 MiB / 50 MiB`. That fits "total / free" for a separate library area better than "total / used" (it can't be full with nothing installed). Leaning **free**, still not proven.
- 2026-09-11 — **Backup analysis** (local, `dumps/library/_INTERNAL_00/`):

  | File | Contents |
  |---|---|
  | `fav.inf` | Favourites list: records of content ID + Shift-JIS dictionary name (e.g. `cj450` = ケンブリッジ英英和辞典) |
  | `jpush.wrk` | Jump/lookup work buffer. Holds **internal file paths** and **plaintext entry text** (Shift-JIS) from the last entry viewed |
  | `jlpush.wrk` | Jump history; repeated content IDs |
  | `siorivi.inf` | `00`/`ff` flag pattern (bookmarks?), otherwise empty |
  | `drvvewer.inf`, `line3.inf` | All zeros |

  **Internal file system**, from paths in `jpush.wrk`. Four volumes; USB only exposes `drv0`:

  | Volume | Holds | Evidence |
  |---|---|---|
  | `\\drv0\` | User area = the USB root `\_INTERNAL_00` | `\\drv0\jpush.wrk`; `jpush.wrk` sits in the USB root |
  | `\\data0\cjNNN\` | Dictionary data: `*comp.cjd` (body), `*head.cjd` (headwords), `*tree.cjd` (index), `*wct.cjd` (?) | `\\data0\cj413\hon_comp.cjd`, `\\data0\cj002\jcomp.cjd` |
  | `\\data0\font\` | Bitmap fonts `.cjf`: Japanese (`gyfont`, `j2font` 12–64 px), Chinese, Korean, Latin | 17 font files |
  | `\\sys0\sys_bin\` | `.dca` per dictionary, e.g. `cj413m.dca`. Likely the dictionary's viewer/program module | Only one seen |

  Content IDs seen: `cj002`, `cj003`, `cj010`, `cj018`, `cj045`, `cj060`, `cj359`, `cj413`, `cj450`. The `cj900`/`cj901` folders in the USB root are probably user/add-on slots.

  **Jailbreak leads**: (1) `sys0\sys_bin\*.dca` look like per-dictionary code modules; if `setpath` can reach `\sys0`, that's the path to reading (and maybe replacing) code. (2) Dictionary text is only compressed, not encrypted, at least in the work buffer.
- 2026-09-11 — Folder renamed `16-caio-data-plus-jailbreak` → `17-casio-dataplus-jailbreak` (typo, and 16 was already taken). Re-ran `configure` + `make` because libtool bakes absolute paths into `src/exword`. Logs from sessions 01–02 still show the old path.
- 2026-09-11 — **Session 03 (read-only)**, log in `session-03-setpath-probe.log`. The device was still on USB, but **`connect failed`**. Likely cause: session 02 ended without `disconnect`, so the dictionary still holds that OBEX session and refuses a new one. So skipping `disconnect` doesn't save a USB toggle after all. Session 04 was meant to retry with `debug 5`, but never ran.
- 2026-09-11 — **The dictionary drops off USB on its own.** It was on the bus right after session 03 and gone a few minutes later, with no `disconnect` sent. Probably auto power-off after idle time (not confirmed). Since every session costs a USB toggle anyway, sessions now run as one batch ending in a clean `disconnect`, started by a background watcher the moment CESG502 appears on the bus.
- 2026-09-11 — **Session 05 (read-only)**, log in `session-05-raw-paths.log`. The watcher started it 39 s after the dictionary appeared.
  - `setpath raw://` + `list` (the storage-media list) → only **`_INTERNAL_00`**. No SD card, and no internal volume exposed.
  - `raw://\drv0`, `\sys0`, `\sys0\sys_bin`, `\data0`, `\data0\font` → all **`Not found`**. The USB OBEX server is limited to `_INTERNAL_00`, so `sys0` can't be reached through `setpath`.
  - Packet capture of `setpath mem:///data`:
    - Sent `\_INTERNAL_00\data` (UTF-16, flags `02 00`) → got back `C4` = Not Found.
    - The working root is sent as `\_INTERNAL_00\`, **with a trailing backslash**. Next test: `\_INTERNAL_00\data\`.
  - `capacity` → **Forbidden** this time. In session 01 it worked right after a root `list`. Consistent with protocol.txt's quirk that `list` unlocks commands needing auth; here the last `list` was at the media level, not the root.
- 2026-09-11 — **How libexword itself navigates** (`libexword/src/dict.c`), which the author tested on real devices:
  - Add-on dictionaries live at `\_INTERNAL_00\<id>\_CONTENT` (data) and `\_INTERNAL_00\<id>\_USER` (user data). Paths have no trailing backslash. `dict list` enters `\_INTERNAL_00` (also no trailing backslash).
  - So the `cj900`/`cj901` folders may refuse a plain `setpath` but open at `<id>\_CONTENT`. Session 06 tests this.
  - Add-on IDs are **5 characters** (`strncat(path, id, 5)`, `dict.c:124`), the same shape as `cj900`/`cj901`. `main.c:518` passes the root as `\_INTERNAL_00\` (trailing backslash), so a full path is `\_INTERNAL_00\cj900\_CONTENT`.
  - **Key cracking** (`_crack_key`, `dict.c:117`): `dict decrypt` enters `<id>\_CONTENT` and downloads `diction.htm` to derive the add-on's key. Session 06 also tries `get diction.htm` from `cj900`/`cj901` (copy to the Mac only).
  - **Add-on registry**: `dict list` reads the first non-empty file among `admini.inf` (ja), `adminikr.inf`, `adminicn.inf`, `adminide.inf`, `adminies.inf`, `adminifr.inf`, `adminiru.inf` (`dict.c:47`). Our root has none of them, which explains the empty `dict list`.
    - Each record is 180 bytes: `id[32]`, **`key[16]`**, `name[132]` (`admini_t`, `dict.c:33`). The per-add-on key is stored on the device.
  - **Encryption = 16-byte repeating XOR** (`_crypt`, `dict.c:58`). `diction.htm` always starts with `<html>\r\n<head>\r\n` (`plaintext`, `dict.c:39`). So encrypted bytes 0–15 XOR that known text = the key: a known-plaintext attack, no brute force needed. `key1`/`key2` (`dict.c:42`) are hardcoded constants; their role isn't traced yet.
  - 🐛 **`_crypt` is broken on 64-bit**, i.e. this Mac. It XORs `*(long *)ptr` but advances `ptr += 4` and indexes `((long *)key)[0..3]`. That assumes 4-byte `long`; on arm64 macOS `long` is 8 bytes. So it XORs overlapping 8-byte chunks and reads 32 bytes of a 16-byte key (out of bounds). Result: **`dict decrypt` gives garbage and `dict install` would write garbage to the device.** Fix before use: `long` → `uint32_t`. Known-answer check: encrypting 16 zero bytes must return the key exactly (a round-trip test can't catch this bug, because XOR cancels itself).
  - ⚠️ `dict install` calls `exword_setpath(..., 1)` (`dict.c:506`, `:522`), i.e. **mkdir on**. It creates folders on the device. Never run it without a backup.
- 2026-09-11 — **Session 06 (read-only)**, log in `session-06-content.log`. The watcher started it 75 s after the dictionary appeared.
  - Root `list` → `capacity` = `52428800 / 52428800`, **not Forbidden**. Confirms the unlock quirk: a root `list` enables auth-gated commands.
  - `\_INTERNAL_00\cj900\_CONTENT`, `cj900\_USER`, `cj901\_CONTENT` → **Not found**. `get diction.htm` from both → Not found. So `cj900`/`cj901` aren't libexword-style add-on folders (or library mode won't open them).
  - `\_INTERNAL_00\data\` (trailing `\`) and `\_INTERNAL_00\DATA` (uppercase) → Not found. `\_INTERNAL_00` (no trailing `\`) works.
  - **Conclusion: in library mode no subfolder of the root can be entered, whatever the spelling.** Best guess: the library-mode server only opens folders registered in `admini.inf`, and ours has none. Next: `text` (TextLoader) and `cd` (CDLoader) connect modes, which may expose a different view. `cj900_01..05` look like TextLoader slots.
- 2026-09-11 — **One connect mode per USB toggle.** `connect()` returns early if already connected (`main.c:265`), and `disconnect` drops USB. So `library`, `text` and `cd` each need their own toggle. That's why `crawl.py` exists: one toggle maps a whole mode without pre-guessing paths.
  - Side note: `connect()` ends with `_setpath(s, INTERNAL_MEM, "/", 2)` (`main.c:328`). mkdir=2 means the *create* flag, but the root always exists, so nothing is created.
- 2026-09-11 — `crawl.py` verified before first use: `--selftest` ok; a dry run with the dictionary off printed `connect failed` and exited in 2 s (no hang).
- 2026-09-11 — **Session 07: `crawl.py text` (TextLoader mode)**, log in `session-07-crawl-text.log`.
  - **Same view as library mode.** Media list = only `_INTERNAL_00`; same root entries; every subfolder `Not found`. `capacity` = `52428800 / 52428800`.
  - The 6 root files copied fine and are **byte-identical** to the library-mode copies (`cmp`), so the duplicate `dumps/text/` was deleted.
  - `temp.inf` is **a folder in library mode (`<temp.inf>`) but a file in text mode**. `get temp.inf` → Not found in text mode. Probably a hidden/locked system entry.
  - The root listing came back reordered (`siorivi.inf`, `jpush.wrk`, `jlpush.wrk`, `temp.inf` moved to the end) with identical file contents. The dictionary seems to re-save these files (on power-off or entering USB mode?).
  - Next: `crawl.py cd` (CDLoader), the last unmapped mode.
- 2026-09-11 — **Session 08: `crawl.py cd` (CDLoader mode)**, log in `session-08-crawl-cd.log`. **`connect failed`.**
  - The dictionary then **left USB mode without a `disconnect`**: a failed connect also costs a toggle. So the planned debug retry (session 09) never ran, and the device's rejection code is unknown.
  - Not a libexword bug: cd mode sends version byte `0xf0` + locale `0x20` (`exword_open2`, `exword.c:339`–`345`), exactly as protocol.txt specifies for CDLoader. For comparison, text sends `ver = locale` and library sends `ver = locale - 0x0f`.
  - Likely conclusion: **this model doesn't support CDLoader** (audio was on later DATAPLUS models). Not proven; it would take one more toggle with `set debug 5` to capture the reply.

## USB map: complete (2026-09-11)

| Mode | Connects? | What's reachable |
|---|---|---|
| `library` | ✅ | Storage media list = `_INTERNAL_00` only. Root: 6 files (all backed up), 17 folders, **none enterable** |
| `text` | ✅ | Same as library. Files byte-identical. `temp.inf` flips from folder to file |
| `cd` | ❌ `connect failed` | — |

Not reachable over USB: `\sys0` (program modules `.dca`), `\data0` (dictionary data `.cjd`, fonts `.cjf`), `\drv0` by name. Known only from paths inside `jpush.wrk`.
- 2026-09-11 — **Next phase chosen: load our own text** (TextLoader mode), via a keep-alive session (`live.sh`) so probes stop costing USB toggles.
  - First write to the device: `payloads/hello.txt` (ASCII, CRLF), sent to the text-mode root. Undo = `delete hello.txt`. The 6 original root files are backed up in `dumps/library/_INTERNAL_00/`.
- 2026-09-12 — **Session 10: first write to the device** (keep-alive `live.sh`, text mode), log in `session-10-live.log`.
  - `send payloads/hello.txt` → `uploading...OK, Success`. `hello.txt` now appears in the root listing. **Writing to the device works.**
  - **The firmware created `dlname.inf` by itself**, next to `hello.txt`. It wasn't in any earlier listing. Almost certainly TextLoader's index of loaded text files (name mapping).
  - ✅ **Capacity resolved: the second number is FREE space, not used.** Before: `52428800 / 52428800`; after uploading 65 bytes: `52428800 / 52420800`. It *decreased*, so `exword.c`'s `free` field name is right and protocol.txt's "amount of space used" is wrong. Internal memory is 50 MiB and was **empty**, not full.
  - **Allocation unit looks like 4,000 bytes**: 8,000 bytes disappeared for two new files (65-byte `hello.txt` + `dlname.inf`). Fits `siorivi.inf` being exactly 4,000 bytes.
  - **Keep-alive works.** The connection survived with a `model` ping every 30 s, so probes no longer cost a USB toggle.
  - **Uploads round-trip intact**: `hello.txt` fetched back is byte-identical to `payloads/hello.txt` (`cmp`).
  - 🔑 **`dlname.inf` = 16 bytes, contents: `\\drv0\hello.txt`** (raw string, no terminator). Two things follow:
    - **The USB root `\_INTERNAL_00` really is the internal `\\drv0\` volume** — confirmed by a path the *firmware itself* wrote, matching the inference from `jpush.wrk`.
    - It records the **most recently loaded file only** — not an index of all of them (see the second-file test below).
  - **Second-file test** (`payloads/hello2.txt`, 14 bytes):
    - `dlname.inf` became 17 bytes holding only `\\drv0\hello2.txt`. The `hello.txt` entry was **overwritten, not appended**. So `dlname.inf` = "name of the last file loaded", written by the firmware.
    - ✅ **4,000-byte allocation unit confirmed**: free went `52420800` → `52416800`, a drop of exactly 4,000 for one new file. The first upload's 8,000 = `hello.txt` (4,000) + the newly created `dlname.inf` (4,000); this time the index was rewritten in place at no extra cost.
    - Root now holds `hello.txt`, `hello2.txt`, `dlname.inf` alongside the original files.
  - ✅✅ **Confirmed on the device by the owner: TextLoader works.** Both `hello.txt` and `hello2.txt` are listed in the dictionary's text viewer, and the greeting text reads correctly on screen.
    - **A plain ASCII `.txt` (CRLF) in the USB root is enough.** No Casio TextLoader software, no Windows, no container format, no registration step — `exword` + `send` is the whole path. `dlname.inf` is written by the firmware afterwards, not a prerequisite.
    - This makes the dictionary a usable reader for our own text from macOS.
  - ⚠️ **The dictionary's keypad is locked while a USB connection is open.** It can't be browsed until `disconnect`, which hands control back (and drops it off the bus). So: connect → write/read → disconnect → check on the device → toggle USB mode again for the next round.
  - **Keep-alive endurance**: the connection held across 7 `model` pings (~3.5 min of idle-with-pings) plus several command batches, and ended only because we sent `disconnect` — it was never dropped by the device.
- `get <localpath>`: downloads the file named `basename(localpath)` from the *current device folder* and saves it to `localpath`. So `get /abs/dumps/fav.inf` pulls `fav.inf`. Backups go to `dumps/`.

## Limit tests (session 11, in progress)

Measuring how far TextLoader goes: biggest file that uploads and still opens, how many files the viewer lists, and how the device reports a filling disk. Every line in every payload is numbered (`000001 The quick brown fox…`, CRLF), so truncation is visible on screen.

| Payload | Size |
|---|---|
| `size-064k.txt` | 65,561 |
| `size-512k.txt` | 524,329 |
| `size-2m.txt` | 2,097,157 |
| `size-8m.txt` | 8,388,628 |
| `many/t01..t20.txt` | 704 B each |

Total ~10.9 MB against ~51 MB free, so the ladder can't fill the device by accident. `capacity` is read after each send (second number = free, confirmed in session 10). Filling all 50 MiB deliberately is a separate decision, not part of this run.

Regenerate the payloads:

```sh
python3 - <<'EOF'
import os
os.makedirs('payloads/generated/many', exist_ok=True)
def write(path, target):
    with open(path, 'wb') as f:
        n = 0
        while f.tell() < target:
            n += 1
            f.write(f'{n:06d} The quick brown fox jumps over the lazy dog.\r\n'.encode())
for kb, name in [(64,'size-064k.txt'), (512,'size-512k.txt'), (2048,'size-2m.txt'), (8192,'size-8m.txt')]:
    write(f'payloads/generated/{name}', kb * 1024)
for i in range(1, 21):
    write(f'payloads/generated/many/t{i:02d}.txt', 200)
EOF
```

## Custom firmware / homebrew: what's actually possible (research, 2026-09-12)

| Generation | OS | Homebrew status |
|---|---|---|
| DATAPLUS 3 (ours, XD-SW/XD-GW) | **PVOS 400** | No known custom apps or firmware |
| DATAPLUS 4 | PVOS 500 | No |
| **DATAPLUS 5/6/7** | PVOS 600, SH4 | **Yes** — active scene |

- [Brain Hackers](https://github.com/brain-hackers) ship a working toolchain for DATAPLUS 5/6/7: [`devkitSH4`](https://brain.fandom.com/ja/wiki/DevkitSH4) (SH4 cross-compiler + `libdataplus`), [`exword-template`](https://github.com/brain-hackers/exword-template) (app skeleton), [`EXplorer`](https://github.com/brain-hackers) (file manager that creates/deletes files on device), and [Gnuboy EX](https://wiki3.jp/brain/page/34) (Game Boy / GB Color emulator).
- **Gnuboy EX is reported to work on DATAPLUS 5/6/7 and *not* on DATAPLUS 4 or earlier.** So our DP3 is out for these apps.
- Apps install as **add-on dictionaries via libexword**, exactly the `<id>\_CONTENT` structure in `dict.c`: `connect` → `dict reset` (⚠️ erases all add-ons) → `dict auth <key>` → `dict install <ID>` → `send` for data/ROMs. The *transport* exists on our DP3; what's missing is an OS that executes add-on code.
- The USB protocol is the same family across generations (DATAPLUS 2 was reverse-engineered with the same `07cf:6101` IDs, [Thias' blog](https://wiesmann.codiferes.net/wordpress/archives/5877)), but that work reached protocol-level access only — no firmware extraction, no code execution.
- Replacing the firmware outright would need a flash dump over hardware (chip clip/JTAG), plus RE of an undocumented PVOS 400 boot chain on an unidentified SoC. No public precedent for any DATAPLUS model.
- ⚠️ **The dictionary has no text editor** — the text feature is a *viewer*. Journalling on the device itself isn't possible without custom code; as it stands, write on the Mac, read on the device.

### Test mode — entered 2026-09-12 ✅

Version screen on our device:

| Field | Value |
|---|---|
| MODEL | **L355** |
| OS ver. | 01.00 |
| APL ver. | 01.00 |

- **`L355` = the `gy355` sub-model** reported over USB, so the USB sub-model field is the internal model code.
- **OS 01.00 = the `0100` in the USB string `gy131,ON,0100`**, so that field is the OS version.
- No BIOS line, unlike the newer model quoted by Brain Hackers (`CY606, BIOS 2.0, OS 2.0`).

### Test mode — how to enter

Documented by Brain Hackers; needs no USB and no disassembly.

Sources disagree about which combination belongs to which generation, so try both — a wrong one just boots normally.

- **Try first** (2 of 3 sources put this on older models, and the [openexword post](https://openexword.livejournal.com/429.html) uses it generally): power off → hold **Back + Page-up** and press **Power** for 5 s → at the Model/BIOS/OS popup press **Right, Right, Enter** → two beeps → TEST MENU.
- **Otherwise**: power off → hold **Left + Back + Delete** and press **Power** for 5 s → same Right, Right, Enter.
- Exit: the **RESET** hole on the back returns to the dictionary screen.
- Our device shows the popup with `Back + Page-up + Power`, but **`Right, Right, Enter` did not get into the menu** (2026-09-12). Next to try: the documented older-model combo `Left + Back + Delete + Power`, and 訳/決定 as Enter, pressed after releasing the three keys.

**Full menu list** (Brain Hackers, from a DATAPLUS 8 `CY606`; ours is older so it may differ). The page 403s to fetchers but `curl` with a browser user-agent works:

```sh
curl -sS -A 'Mozilla/5.0' 'https://scrapbox.io/api/pages/brain-hackers/EX-word_%E3%83%86%E3%82%B9%E3%83%88%E3%83%A2%E3%83%BC%E3%83%89%E3%81%AE%E6%A9%9F%E8%83%BD%E4%B8%80%E8%A6%A7/text'
```

| Item | What it does |
|---|---|
| 1–5, 11–12 | Automated hardware checks (version, beep, keyboard, lid switch, touch panel, SDRAM/NAND, SD card, USB, audio, clock) |
| 6. MANUAL CHECK | Submenus: DISPLAY, MEMORY, **FLASH CHECK**, INPUT, SD-CARD, AUDIO, USB, OTHERS, **FLASH UTILITYS**, **SERVICE MENU** (password-protected), **FULL RESET (CONFIG&DICS)** ⚠️ |
| 7. VERSION | Version display; **CHECK SUM** prints `NAND 1 CHECK SUM =` then freezes |
| **8. OS UPDATE** | 🔑 "Appears to allow updating the OS; details unknown" — the most promising firmware hook found so far |
| 9. TOUCH PANEL PRESET | Calibration |
| **10. RESET** | ☠️ "**Immediately wipes everything, ignoring password locks**" |

### 🔑 Our L355 test menu: OS UPDATE exists (2026-09-12)

Entered the test menu successfully. **`OS UPDATE` offers two routes: `SD card update` and `USB OS update`.**

So this generation has a **built-in firmware flashing path** — undocumented for DATAPLUS 3 anywhere public. That is the realistic route to custom firmware, far cheaper than a chip-off dump.

⚠️ **Casio never published a firmware image for this generation.** Their [software download page](https://support.casio.jp/download.php?cid=003&pid=288) lists only EX-word TextLoader, TextLoader SC, CD Loader, Library and Educational Library — **no OS/firmware update for any series**, DATAPLUS 3 included. Consequences:
- No reference image to learn the format from.
- **No restore image if a flash goes wrong.** A bricked device stays bricked unless we dump its flash first over hardware.
- So the only safe order is: **dump the existing firmware first**, then experiment with the updater.

**Not selected yet, deliberately.** Some updaters erase flash *before* receiving an image; if this one does and we have nothing to send, the device bricks with no backup to restore. Order of work must be:

1. Find whether Casio published an official OS image for XD-SW/XD-GW (gives both a format reference and a restore path).
2. Only then probe the updater — SD route first (a missing-file error may name the expected filename), watching the USB bus during the USB route to see what it enumerates as.

### `USB OS update` mode probed (2026-09-12), log `session-12-osupdate-probe.log`

Owner selected **OS UPDATE → USB OS update**. What the Mac sees:

| Observation | Value |
|---|---|
| Enumeration | **Identical to normal mode**: `CESG502`, `07cf:6101`, `bcdDevice 0x0100`, 12 Mb/s, 1 configuration, `bDeviceClass 0` |
| OBEX connect (library `0x11`, text `0x20`, cd `0xf0`) | **All fail** |
| Bulk write to endpoint 1 | **Succeeds** — the 11-byte connect packet goes out fine |
| Bulk read back | **Stalls**: `obex_verify_seq(): Error reading seq number (-9)` = `LIBUSB_ERROR_PIPE` |

**Interpretation**: update mode is not a separate DFU device and not an OBEX server. It re-uses the same vendor interface but acts as a **one-way listener** — it accepts data on the bulk-out pipe and stalls reads. So it is waiting to be fed a firmware image and will not answer queries.

**Consequences**:
- Anything written to endpoint 1 in this mode goes straight into the updater. With no image, no format knowledge and no restore copy, writing arbitrary bytes is the one move that can permanently brick the device.
- Exit safely with the **RESET** hole on the back or a power cycle — no data is written by merely entering the mode.
- To go further we would need the image format (header/magic, checksum, signature). Nothing public exists, so the honest order stays: **dump the flash over hardware first**, then study the updater with a known-good image in hand.

### Raw write attempt — aborted, nothing sent (2026-09-12)

Owner authorised writing to the updater. Built `rawsend.c` for it: a small libusb program that bulk-writes a file straight to endpoint `0x01` (what `exword` cannot do, since update mode ignores OBEX) and then tries a read on `0x82` to see if feeding it data makes it answer.

```sh
cc rawsend.c -o rawsend $(pkg-config --cflags --libs libusb-1.0)
./rawsend payloads/generated/probe-4k.bin 0x01 4096
```

The plan was a 4 KB deliberately-invalid payload (`CLAUDE-PROBE-NOT-A-FIRMWARE-IMAGE…`) to test whether the updater validates a header *before* erasing, with the device's screen as the only feedback channel.

**It never ran.** The pre-send guard found the device had left the bus, so **no bytes were written by `rawsend`**.

### 🔑 The updater errors out instead of bricking (2026-09-12)

The device displayed **`ERROR`** on screen and dropped off USB by itself.

It had, however, already been fed data: the three OBEX `connect` attempts each bulk-wrote an 11-byte packet to endpoint `0x01` (`Write to endpoint 1` succeeded each time) — 33 bytes of definitely-not-firmware. The updater took it, waited, then errored and exited update mode.

**So this updater does not erase-then-wait.** It either validates what it receives or times out, and fails safe. That materially lowers the risk of experimenting with the USB route — though it says nothing yet about what happens to a payload large enough to look like a real image.

✅ **Confirmed by the owner: the dictionary boots normally afterwards.** The message was a bare `ERROR` with no code.

So the full sequence — enter `USB OS update`, feed it 33 bytes of non-firmware, get `ERROR`, device drops off USB, RESET, boots fine — **is safe and repeatable**. The USB updater can be probed without risking the device, at least with small invalid payloads.

Still unknown: whether a payload large enough to look like a real image is validated the same way, and what a valid header/checksum looks like.

### 🔑🔑 `MANUAL CHECK → FLASH UTILITYS` on our L355 (2026-09-12)

| Item | Reading |
|---|---|
| **1. DATA OUT** | Flash → out. **The dump route**: if it writes flash contents to SD, that is the firmware image, obtained without opening the case |
| **2. DATA IN** | Data → flash. ☠️ **The brick button.** Never select without a verified image |
| **3. USERAREA copy (DVRO → SD)** | Copies the user area to SD. `DVRO` = **`DRV0`**, the internal volume identified from `jpush.wrk` paths and `dlname.inf` — independent confirmation of that mapping |
| 4. USERAREA copy (SD → DVRO) | The reverse: overwrites the user area from SD. Recoverable (we have the 6 root files backed up) but not to be run casually |
| **5. TJFS PHYSICAL FORMAT** | ☠️ Physically formats the filesystem. `TJFS` is Casio's own filesystem name — new information |
| **6. FORCE STRONG FORMAT** | ☠️ Worse. Never select |

`DATA OUT` and `USERAREA copy` only *read* device flash, so they cannot brick it; they write to the SD card. `DATA IN` is the one irreversible option.

⚠️ **Card constraint**: this generation takes **full-size SD, ~1 GB maximum, no SDHC** (per the XD-SW6400 spec; our exact retail model is still unidentified, so confirm against the manual or the slot). A modern SDHC/SDXC card will simply not be recognised, so the dump needs an old ≤1 GB SD card, FAT-formatted.

**Dump plan, safest order:**

1. **`3. USERAREA copy (DVRO → SD)`** first — reads flash only, and proves the whole pipeline works (card recognised, file written, readable on the Mac) before anything that matters. Also gives a second, device-made copy of `drv0` to compare against our USB backups in `dumps/library/_INTERNAL_00/`.
2. **`1. DATA OUT`** — the firmware read. Whatever lands on the card gets analysed here (size, headers, entropy, strings) and becomes the restore image that makes `DATA IN` survivable later.
3. Only with a verified image in hand does `2. DATA IN` become a reasonable experiment.

Never: `5. TJFS PHYSICAL FORMAT`, `6. FORCE STRONG FORMAT`, and not `4` (SD → DRV0) while the user area still holds the only copy of anything.

This makes a full backup plausible **without hardware work**, which reverses the earlier conclusion that a chip-off dump was the only way. Plan: insert a card → test menu → `FLASH UTILITYS` → `DATA OUT` → read the card on the Mac and identify what came off.

**Also relevant**: the L355's own test menu may be able to *read* flash. The DATAPLUS 8 menu has `MANUAL CHECK → FLASH CHECK` / `FLASH UTILITYS` and `VERSION → CHECK SUM`. If our generation offers any dump-to-SD function, that yields the firmware image **without opening the case** — which is the backup that makes every later experiment reversible.

**Leads for a firmware route**: `OS UPDATE` (how does it read an image — SD card? USB? what format/signature?), `FLASH UTILITYS`, and `SERVICE MENU` (needs a password we don't have). `CHECK SUM` suggests NAND flash.

☠️ **Never select** top-level `RESET` or `MANUAL CHECK → FULL RESET`: both wipe the device, and we have no firmware backup to restore.
- The [function list](https://scrapbox.io/brain-hackers/EX-word_%E3%83%86%E3%82%B9%E3%83%88%E3%83%A2%E3%83%BC%E3%83%89%E3%81%AE%E6%A9%9F%E8%83%BD%E4%B8%80%E8%A6%A7) blocks automated fetching (403). Read the menu off the screen instead. ⚠️ A test menu may contain format/erase functions — inspect only, select nothing that writes.

## Do NOT run (destructive)

| Command | Effect |
|---|---|
| `dict reset` / `_AuthInfo` | Resets auth **and deletes every installed add-on dictionary** |
| `format` / `_SdFormat` | Erases the SD card |
| `delete`, `dict remove` | Deletes files or add-ons |
| `send`, `dict install` | Writes to the device (only after a backup) |
| `dict decrypt`, `dict install` | **Broken on 64-bit until `_crypt` is fixed** (see findings): garbage output, and install would write it to the device |

Safe, read-only: `connect`, `model`, `capacity`, `list`, `setpath` (incl. `raw://`, with `set mkdir` left off), `get`, `dict list`.

## Build notes (macOS, Apple Silicon)

`brew install automake libtool libusb`. Old code, so it needs patches for modern clang:
- `configure.ac`: dropped `-Werror` from `AM_INIT_AUTOMAKE` (newer automake warns about `AM_PROG_AR`)
- `configure` needs `LIBS=-liconv` (the iconv check only looks for `libiconv_open`)
- `src/main.c`: added a prototype for `dict_reset`
- `src/obex.h`: the declaration was misnamed `obex_object_add_header`; the definition in `obex.c` is `obex_object_addheader`. Renamed the declaration to match.
- `src/main.c` `interactive()`: at end of input (`readline()` returns `NULL`, e.g. piped stdin or Ctrl-D) the loop `continue`d forever at 100% CPU. It now `break`s.
- `src/main.c` `setpath()`: **added `raw://<path>`**, which sends the path to the device as-is (e.g. `raw://\sys0\sys_bin`) instead of prefixing `\_INTERNAL_00\`. mkdir is forced off, so it can never create folders. `raw://` alone sends an empty path, which lists the storage media (`exword.c:600`). Added to probe the internal `sys0` / `data0` / `drv0` volumes.
- `src/main.c` `main()`: `setvbuf(stdout, NULL, _IONBF, 0)`. Unbuffered output, so `crawl.py` can read each reply as it arrives through a pipe.

`exword` has no command-line flags; it's an interactive shell. `--help` just opens the shell. Run it as `./libexword/src/exword`, or pipe commands in: `printf 'connect\nmodel\n' | ./libexword/src/exword`.
