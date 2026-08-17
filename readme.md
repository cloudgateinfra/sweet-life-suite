```
 ███████╗██╗    ██╗███████╗███████╗████████╗    ██╗     ██╗███████╗███████╗
 ██╔════╝██║    ██║██╔════╝██╔════╝╚══██╔══╝    ██║     ██║██╔════╝██╔════╝
 ███████╗██║ █╗ ██║█████╗  █████╗     ██║       ██║     ██║█████╗  █████╗
 ╚════██║██║███╗██║██╔══╝  ██╔══╝     ██║       ██║     ██║██╔══╝  ██╔══╝
 ███████║╚███╔███╔╝███████╗███████╗   ██║       ███████╗██║██║     ███████╗
 ╚══════╝ ╚══╝╚══╝ ╚══════╝╚══════╝   ╚═╝       ╚══════╝╚═╝╚═╝     ╚══════╝
```

> **rename. remux. deduplicate. manage. repeat.**

---

## 💡 The Idea

Years of running a home server. Years of random bash scripts, one-off aliases, half-remembered ffmpeg flags, and scattered Python snippets living in `~/scripts/maybe/` or worse — lost in a terminal history from 2019.

One day you look at your `.bashrc` and realize you've got 40 aliases that each do one tiny thing, shell functions you copy-paste between machines, and a folder of scripts named things like `clean2_final_FINAL.sh`.

So you consolidate. Everything goes into one file. One script to rule them all. No dependencies, no pip install, no virtual environments, no config files, no Docker container for your Docker management tool. Just Python and the coreutils you already have.

Is it over-engineered for what it does? Maybe. Does it have a colorful ASCII banner? Obviously. Does it work every single time you need it at 3am when you're reorganizing your media server? Yeah. Yeah it does.

**One file. 22 commands. Zero bullshit.**

---

## 🚀 One-Time Setup

```bash
mkdir -p ~/bin
cp sweet_life.py ~/bin/sweet_life
chmod +x ~/bin/sweet_life
dos2unix ~/bin/sweet_life
source ~/.profile
```

or
```
mkdir -p ~/bin && cp sweet_life.py ~/bin/sweet_life && chmod +x ~/bin/sweet_life && dos2unix ~/bin/sweet_life && source ~/.profile
```

That's it. Your `~/.profile` already adds `~/bin` to PATH. Verify:

```bash
sweet_life
```

### 🔄 Updating (after edits)

```bash
cp sweet_life.py ~/bin/sweet_life && dos2unix ~/bin/sweet_life
```

### ⚡ Optional: alias shortcut

```bash
echo "alias sl='sweet_life'" >> ~/.bashrc && source ~/.bashrc
```

Now: `sl clean /mnt/pool -r` / `sl docker ps` / `sl size /mnt/pool` etc.

---

## 📦 Requirements

| Dependency | Needed for | Install |
|---|---|---|
| Python 3.7+ | everything | already there |
| ffmpeg/ffprobe | `restag` `probe` `hq` `audio` `extract` `remux` | `sudo apt install ffmpeg` |
| jdupes | `jclean` `jcompare` | `sudo apt install jdupes` |
| rsync | `copy` | `sudo apt install rsync` |
| dos2unix | one-time setup | `sudo apt install dos2unix` |

Or just grab everything:
```bash
sudo apt install ffmpeg jdupes rsync dos2unix
```

---

## 🎯 Commands

| # | Command | What it does |
|:---:|---------|---|
| 1 | `clean` | 🧹 Strip junk from filenames — brackets, dots, underscores → clean spaces |
| 2 | `dirname` | 📁 Rename files to match their parent directory name |
| 3 | `restag` | 🏷️ Add resolution tags (4k/5k/6k/7k/8k) via ffprobe |
| 4 | `probe` | 🔍 Full anonymized video metadata report (HDR, bit depth, audio, encoding) |
| 5 | `hq` | 💎 HQ peer-bitrate analysis with 2-stage plan system (probe → apply) |
| 6 | `uhdtag` | 🏋️ Tag files ≥ 40 GiB with "UHD HQ" |
| 7 | `audio` | 🎵 Extract audio tracks (auto-detect codec) |
| 8 | `names` | 👤 Find recurring name patterns in filenames |
| 9 | `dupes` | 🔎 Find duplicate/similar filenames (token analysis) |
| 10 | `compare` | ↔️ Cross-compare 2+ directories for duplicates |
| 11 | `dedup` | 🗑️ Smart dupe deletion with duration + date filtering |
| 12 | `jclean` | 🧬 jdupes content-hash scan + delete (single dir) |
| 13 | `jcompare` | 🧬 jdupes compare two directories + delete |
| 14 | `move` | 📦 Move directories matching a name pattern |
| 15 | `extract` | 🎧 Batch audio extract (mp4→mp3, webm→opus) |
| 16 | `remux` | 🎬 Remux any video → mp4 (copy video, AAC audio) |
| 17 | `docker` | 🐳 Docker/compose shortcuts (recreate, update, ps, restart) |
| 18 | `copy` | 📋 rsync -aPh with progress |
| 19 | `permit` | 🔑 chmod 755 recursive |
| 20 | `own` | 👑 chown -R recursive |
| 21 | `size` | 📊 Disk usage sorted by size (fast, uses `du`) |
| 22 | `clip` | 📎 Copy file contents to clipboard (WSL clip.exe) |

---

## 🗺️ Original Scripts → sweet_life

Every standalone script that was consolidated into this one file:

| Original Script | Command | What it became |
|---|---|---|
| `clean_master.py` | `clean` | Strip junk from filenames |
| `rename_by_dir.py` | `dirname` | Rename files to parent dir name |
| `res_tag.py` | `restag` | Resolution tag via ffprobe |
| `probe_scramble.py` | `probe` | Full anonymized metadata report (HDR, bit depth, audio, encoding) |
| `probe_full.py` | `hq` | Peer-bitrate HQ detection + 2-stage plan system |
| `rename_hq.py` | `uhdtag` | Tag files ≥ 40 GiB with UHD HQ |
| `audio.sh` + `audio_key.sh` | `audio` | Extract audio tracks |
| `common_keywords.ps1` | `names` | Recurring name patterns |
| `dup_finder.py` | `dupes` | Filename duplicate scanner |
| `dup_finder_compare.py` | `compare` | Cross-directory compare (2 dirs) |
| `dup_finder_compare_multi.py` | `compare` | Multi-directory compare (2+) |
| `del_finder_simple.py` | `dedup` | Interactive dupe deletion |
| `del_finder_multi.py` | `dedup --auto` | Auto deletion w/ duration + date filtering |
| `media_dup_finder.py` | `dupes` | Hardcoded-path version (now parameterized) |
| `media_dup_del.py` | `dedup` | Hardcoded-path version (now parameterized) |

---

## ⚡ Quick Start

```bash
# Interactive menu with tab-completion + path memory
sweet_life

# Direct command
sweet_life <command> [options]

# Help for any command
sweet_life <command> --help
```

### 🧠 Path Memory

The interactive menu remembers paths you use. Next time you pick a command, your recent paths show up as shortcuts:

```
  Recent paths:
    !1 /mnt/pool/media/_new
    !2 /mnt/pool/media
    !3 /mnt/disk1/media

  path [.]: !1
    → /mnt/pool/media/_new
```

Type `!1`, `!2`, etc. to instantly reuse a previous path. History is saved to `~/.sweet_life_history.json`.

### ⛓️ Command Chain

Type `c` or `chain` at the menu to run multiple commands in sequence:

```
  + Add command: 1        (clean)
  + Add command: 3        (restag)
  + Add command: 5        (hq)
  + Add command: done

  Chain (3 commands):
    1. clean
    2. restag
    3. hq

  Shared path (Enter to set per-command): /mnt/pool/media/_new
```

All three commands execute in order on the same path. Options are asked per-command. Perfect for cleanup pipelines.

---

## 📖 Usage Examples

### 🧹 File Management

```bash
sweet_life clean /mnt/pool/videos -r          # strip junk from filenames
sweet_life dirname /mnt/pool/sorted            # rename files to match folders
sweet_life move "vacation" /mnt/pool/dump /mnt/pool/media  # move matching dirs
sweet_life permit /mnt/pool/media                  # chmod 755 everything
sweet_life own joe:joe /mnt/pool/media             # chown -R
sweet_life size /mnt/pool -n 20                 # what's eating disk space
sweet_life copy /mnt/disk1/big.mp4 /mnt/disk2/  # rsync with progress
sweet_life clip ~/scripts/config.yaml           # copy file to clipboard (WSL)
```

### 🎬 Video Tools

```bash
sweet_life restag /mnt/pool/media --apply         # add 4k/5k/6k/7k/8k tags
sweet_life hq /mnt/pool/media                     # probe + save HQ plan (no rename)
sweet_life hq /mnt/pool/media --apply-hq          # apply saved plan (no reprobe)
sweet_life uhdtag /mnt/pool/media -r              # tag files >= 40 GiB
sweet_life probe /mnt/pool/media                  # full metadata report (HDR, audio, etc.)
sweet_life audio /mnt/pool/media -k "interview"   # extract audio tracks
sweet_life extract /mnt/pool/media -f mp4         # batch mp4→mp3
sweet_life remux /mnt/pool/media -f mkv           # remux mkv→mp4
sweet_life remux /mnt/pool/media                  # remux ALL non-mp4→mp4
```

### 🔎 Duplicate Detection

```bash
# Filename-based (smart token analysis, catches similar names)
sweet_life dupes /mnt/disk1 /mnt/disk2 /mnt/disk3
sweet_life compare /mnt/disk1 /mnt/disk2       # cross-dir only
sweet_life dedup --auto                        # auto-delete (duration + date filter)
sweet_life dedup                               # interactive mode (pick which to delete)
sweet_life dedup --auto --debug                # show filtering diagnostics

# Content-based (jdupes, exact byte-for-byte matches)
sweet_life jclean /mnt/pool/media                    # single dir
sweet_life jcompare /mnt/disk1/media /mnt/disk2/media  # cross-dir
```

### 🐳 Docker

```bash
sweet_life docker ps                            # running containers
sweet_life docker recreate -C /opt/stacks/plex  # down + up -d
sweet_life docker update -C /opt/stacks/plex    # down + pull + up -d
sweet_life docker restart plex                  # restart one container
sweet_life docker logs -C /opt/stacks/plex      # tail logs
sweet_life docker stop -C /opt/stacks/app       # compose down
sweet_life docker start -C /opt/stacks/app      # compose up -d
```

---

## 🔁 Typical Workflows

### Full cleanup pipeline

```bash
sweet_life clean /mnt/pool/media -r        # 1. normalize filenames
sweet_life restag /mnt/pool/media --apply  # 2. tag resolutions
sweet_life hq /mnt/pool/media              # 3. analyze for HQ (saves plan)
sweet_life hq /mnt/pool/media --apply-hq   # 4. apply HQ renames from plan
sweet_life uhdtag /mnt/pool/media -r       # 5. tag 40GiB+ files
```

### Nuke duplicates across drives

```bash
sweet_life compare /mnt/disk1 /mnt/disk2 /mnt/disk3
sweet_life dedup --auto
```

### Remux everything to mp4

```bash
sweet_life remux /mnt/pool/media
```

### Server maintenance

```bash
sweet_life own joe:joe /mnt/pool
sweet_life permit /mnt/pool
sweet_life size /mnt/pool -n 20
sweet_life docker update -C /opt/stacks/plex
```

---

## 🛡️ Safety

| Protection | Details |
|---|---|
| 👀 Preview first | Every destructive command shows what it would do before acting |
| 🏳️ `--dry-run` | Available on all rename commands for extra paranoia |
| ⌨️ Confirmation | Dupe deletion requires typing `YES` |
| 🔐 Double confirm | Resolution/HQ renames require `RENAME RES` / `RENAME HQ` |
| 🚫 No surprise writes | Nothing is modified unless you explicitly say yes |
| 📖 Read-only probes | ffprobe commands never touch your files |
| 🔗 No symlink traversal | Symlinks are never followed |

---

## 📁 File Structure

```
sweet_life.py          ← the one script (entire suite)
SWEET_LIFE_README.md   ← this file
```

One file. No packages. No venvs. No setup.py. No bullshit.

---

## 📜 License

Do whatever you want with it.