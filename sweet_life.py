#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       SWEET LIFE SUITE                                      ║
║              All-in-one system management suite                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage:
    python3 sweet_life.py              Interactive menu (with path history + chain mode)
    python3 sweet_life.py <command>    Run a specific tool
    python3 sweet_life.py --help       Show all commands

Commands:
    clean       Clean filenames (strip junk, normalize spacing)
    dirname     Rename files to match parent directory name
    restag      Add resolution tags (4k–8k) via ffprobe
    probe       Anonymized video metadata report
    hq          HQ peer-bitrate analysis + plan system (2-stage)
    uhdtag      Tag large files (≥40 GiB) with UHD HQ
    audio       Extract audio tracks from video files
    names       Find recurring name patterns in filenames
    dupes       Find duplicate/similar filenames
    compare     Compare 2+ directories for cross-duplicates
    dedup       Interactive duplicate deletion from a report
    jclean      jdupes scan + delete duplicates (single dir)
    jcompare    jdupes compare two dirs + delete duplicates
    move        Move directories matching a pattern
    extract     Batch audio extract (mp4→mp3, webm→opus)
    remux       Remux any video → mp4 (copy video, AAC audio)
    docker      Docker/compose shortcuts (recreate, update, ps, etc.)
    copy        rsync copy with progress
    permit      Fix permissions (chmod 755 recursive)
    own         Change ownership (chown -R)
    size        Disk usage sorted by size
    clip        Copy file contents to clipboard (WSL clip.exe)

Examples:
    python3 sweet_life.py clean /mnt/pool/videos --dry-run -r
    python3 sweet_life.py dirname /mnt/pool/sorted --dry-run
    python3 sweet_life.py restag /mnt/pool/videos
    python3 sweet_life.py hq /mnt/pool/media
    python3 sweet_life.py hq /mnt/pool/media --apply-hq
    python3 sweet_life.py dupes /mnt/disk1/media /mnt/disk2/media
    python3 sweet_life.py dedup filename_duplicate_report.txt --auto
    python3 sweet_life.py jclean /mnt/pool/media
    python3 sweet_life.py jcompare /mnt/disk1/media /mnt/disk2/media
    python3 sweet_life.py move "vacation" /mnt/pool/dump /mnt/pool/sorted
    python3 sweet_life.py extract /mnt/pool/videos
    python3 sweet_life.py remux /mnt/pool/videos -f mkv
    python3 sweet_life.py docker recreate -C /opt/stacks/plex
    python3 sweet_life.py docker ps
    python3 sweet_life.py size /mnt/pool -n 20
    python3 sweet_life.py clip ~/notes/todo.txt
"""

import os
import sys
import re
import json
import shutil
import random
import subprocess
import statistics
import argparse
from pathlib import Path
from fractions import Fraction
from collections import defaultdict
from datetime import datetime
from functools import lru_cache

import glob as _glob_mod

try:
    import readline
except ImportError:
    readline = None


# ═══════════════════════════════════════════════════════════════════════════════
# PATH HISTORY — remembers commonly used paths
# ═══════════════════════════════════════════════════════════════════════════════

HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".sweet_life_history.json")
_MAX_HISTORY = 20


def _load_path_history():
    """Load path usage history from disk."""
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("paths", {})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_path_history(history):
    """Persist path history to disk (keeps top N by count)."""
    top = dict(sorted(history.items(), key=lambda x: -x[1])[:_MAX_HISTORY])
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"paths": top}, f, indent=2)
    except OSError:
        pass


def record_path(path_str):
    """Record a path usage (call after user enters a valid path)."""
    if not path_str or path_str == ".":
        return
    resolved = str(Path(path_str).resolve()) if os.path.exists(path_str) else path_str
    history = _load_path_history()
    history[resolved] = history.get(resolved, 0) + 1
    _save_path_history(history)


def get_recent_paths(limit=8):
    """Return top paths sorted by usage count."""
    history = _load_path_history()
    return sorted(history.items(), key=lambda x: -x[1])[:limit]


# ═══════════════════════════════════════════════════════════════════════════════
# READLINE + PATH INPUT
# ═══════════════════════════════════════════════════════════════════════════════

def _path_completer(text, state):
    """Readline completer for filesystem paths."""
    if text.startswith("~"):
        text = os.path.expanduser(text)
    if not text:
        text = "./"

    if text.endswith(os.sep):
        pattern = text + "*"
    else:
        pattern = text + "*"

    matches = []
    for path in _glob_mod.glob(pattern):
        if os.path.isdir(path):
            matches.append(path + os.sep)
        else:
            matches.append(path)

    matches.sort()
    if state < len(matches):
        return matches[state]
    return None


def setup_readline():
    """One-time readline init (tab binding)."""
    if not readline:
        return
    readline.set_completer_delims(" \t\n;")
    if "libedit" in (readline.__doc__ or ""):
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")


def _show_path_suggestions():
    """Display recent paths as numbered shortcuts."""
    recent = get_recent_paths(6)
    if not recent:
        return []
    print(f"  {C.DIM}Recent paths:{C.RST}")
    for i, (p, count) in enumerate(recent, 1):
        short = p if len(p) <= 50 else "..." + p[-47:]
        print(f"    {C.BYELLOW}!{i}{C.RST} {C.DIM}{short}{C.RST}")
    print()
    return [p for p, _ in recent]


def input_path(prompt, show_history=False):
    """input() with filesystem tab-completion and optional history shortcuts."""
    suggestions = []
    if show_history:
        suggestions = _show_path_suggestions()

    if readline:
        old_completer = readline.get_completer()
        readline.set_completer(_path_completer)
    try:
        val = input(prompt)
        # Handle history shortcut (!1, !2, etc.)
        if val.strip().startswith("!") and val.strip()[1:].isdigit():
            idx = int(val.strip()[1:]) - 1
            if 0 <= idx < len(suggestions):
                val = suggestions[idx]
                print(f"    {C.BGREEN}→{C.RST} {val}")
        # Record the path for future suggestions
        stripped = val.strip()
        if stripped and stripped != "." and not stripped.startswith("!"):
            record_path(stripped)
        return val
    finally:
        if readline:
            readline.set_completer(old_completer)


def setup_path_completer():
    """Legacy wrapper — calls setup_readline."""
    setup_readline()

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS & STYLING
# ═══════════════════════════════════════════════════════════════════════════════

class C:
    """ANSI color codes for terminal output."""
    RST      = "\033[0m"
    BOLD     = "\033[1m"
    DIM      = "\033[2m"
    ITALIC   = "\033[3m"
    ULINE    = "\033[4m"

    BLACK    = "\033[30m"
    RED      = "\033[31m"
    GREEN    = "\033[32m"
    YELLOW   = "\033[33m"
    BLUE     = "\033[34m"
    MAGENTA  = "\033[35m"
    CYAN     = "\033[36m"
    WHITE    = "\033[37m"

    BRED     = "\033[91m"
    BGREEN   = "\033[92m"
    BYELLOW  = "\033[93m"
    BBLUE    = "\033[94m"
    BMAGENTA = "\033[95m"
    BCYAN    = "\033[96m"
    BWHITE   = "\033[97m"

    BG_BLACK   = "\033[40m"
    BG_RED     = "\033[41m"
    BG_GREEN   = "\033[42m"
    BG_YELLOW  = "\033[43m"
    BG_BLUE    = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN    = "\033[46m"

    @staticmethod
    def disable():
        for attr in dir(C):
            if attr.isupper() and not attr.startswith("_"):
                setattr(C, attr, "")


if not sys.stdout.isatty():
    C.disable()


def banner():
    print(f"""
{C.BMAGENTA}{C.BOLD}╔══════════════════════════════════════════════════════════════════════════╗
║{C.BCYAN}  ███████╗██╗    ██╗███████╗███████╗████████╗    ██╗     ██╗███████╗███████╗  {C.BMAGENTA}║
║{C.BCYAN}  ██╔════╝██║    ██║██╔════╝██╔════╝╚══██╔══╝    ██║     ██║██╔════╝██╔════╝  {C.BMAGENTA}║
║{C.BCYAN}  ███████╗██║ █╗ ██║█████╗  █████╗     ██║       ██║     ██║█████╗  █████╗    {C.BMAGENTA}║
║{C.BCYAN}  ╚════██║██║███╗██║██╔══╝  ██╔══╝     ██║       ██║     ██║██╔══╝  ██╔══╝    {C.BMAGENTA}║
║{C.BCYAN}  ███████║╚███╔███╔╝███████╗███████╗   ██║       ███████╗██║██║     ███████╗  {C.BMAGENTA}║
║{C.BCYAN}  ╚══════╝ ╚══╝╚══╝ ╚══════╝╚══════╝   ╚═╝       ╚══════╝╚═╝╚═╝     ╚══════╝  {C.BMAGENTA}║
║                                                                          ║
║{C.DIM}{C.BWHITE}            All-in-one system management suite                   {C.RST}{C.BMAGENTA}{C.BOLD}║
╚══════════════════════════════════════════════════════════════════════════╝{C.RST}
""")


def section(title):
    w = 60
    print(f"\n{C.BBLUE}{C.BOLD}{'═' * w}")
    print(f"  {title}")
    print(f"{'═' * w}{C.RST}\n")


def success(msg):
    print(f"  {C.BGREEN}✓{C.RST} {msg}")


def warn(msg):
    print(f"  {C.BYELLOW}⚠{C.RST} {msg}")


def error(msg):
    print(f"  {C.BRED}✗{C.RST} {msg}")


def info(msg):
    print(f"  {C.BCYAN}→{C.RST} {msg}")


def dim(msg):
    print(f"  {C.DIM}{msg}{C.RST}")


def confirm(prompt="Proceed?", default=False):
    hint = "Y/n" if default else "y/N"
    answer = input(f"  {C.BYELLOW}?{C.RST} {prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def gg():
    """Print 'gg ez git gud' in bold random colors and exit."""
    colors = [C.BRED, C.BGREEN, C.BYELLOW, C.BBLUE, C.BMAGENTA, C.BCYAN, C.BWHITE]
    msg = "gg ez git gud"
    colored = "".join(f"{random.choice(colors)}{C.BOLD}{ch}{C.RST}" for ch in msg)
    print(f"\n  {colored}\n")
    sys.exit(0)


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".m4v", ".avi", ".webm",
    ".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".wmv"
}

RESOLUTION_TAGS = {"4k", "5k", "6k", "7k", "8k"}
QUALITY_TAGS = {"hq", "uhd"}

ROMAN_NUMERALS = {
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
    "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx"
}

NOISE_TOKEN_PATTERNS = [
    re.compile(r'^\d+p$'),
    re.compile(r'^\d+x\d+$'),
    re.compile(r'^\d+k$'),
    re.compile(r'^\d+kuhd$'),
    re.compile(r'^\d+fps$'),
    re.compile(r'^f\d{2,3}$'),
    re.compile(r'^mkx\d+$'),
    re.compile(r'^fisheye\d*$'),
]

NOISE_WORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "is", "its", "it", "my", "your", "her", "his",
    "our", "their", "this", "that", "as", "be", "vs", "you", "i",
    "lr", "tb", "sbs", "ou", "mvc", "3dh", "3dv", "mono", "stereo", "alpha",
    "hd", "fhd", "uhd", "hq", "uhq", "hevc", "avc", "h264", "h265", "av1", "aac", "mp4", "mkv",
    "original", "originals", "studio", "master", "remastered", "passthrough", "edition",
    "version", "official", "exclusive", "full", "new",
    "vol", "volume", "part", "pt", "ep", "episode", "chapter", "ch", "scene",
}


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def discover_videos(root, recursive=True):
    videos = []
    root = Path(root).resolve()
    for dirpath, dirs, filenames in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(dirpath, d))]
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            if os.path.islink(path):
                continue
            if os.path.splitext(filename)[1].lower() in VIDEO_EXTENSIONS:
                videos.append(path)
        if not recursive:
            break
    videos.sort()
    return videos


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_fps(stream):
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = stream.get(key)
        if value and value != "0/0":
            try:
                return float(Fraction(value))
            except Exception:
                pass
    return None


def fps_bucket(fps):
    if fps is None:
        return None
    buckets = [(23.976, 24.0, 0.5), (24.0, 24.0, 0.5), (25.0, 25.0, 0.5),
               (29.97, 30.0, 0.5), (30.0, 30.0, 0.5), (50.0, 50.0, 0.5),
               (59.94, 60.0, 0.5), (60.0, 60.0, 0.5), (90.0, 90.0, 0.5),
               (119.88, 120.0, 0.75), (120.0, 120.0, 0.75)]
    for target, bucket, tolerance in buckets:
        if abs(fps - target) <= tolerance:
            return bucket
    return round(fps, 1)


def fmt_num(value, decimals=3):
    return f"{value:.{decimals}f}" if value is not None else "Unknown"


def fmt_duration(seconds):
    if seconds is None:
        return "??:??"
    seconds = int(round(seconds))
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_size(size_bytes):
    if size_bytes is None or size_bytes < 0:
        return "??"
    return f"{size_bytes / (1024**3):.2f} GiB"


def detected_resolution_tag(width, height):
    if not width or not height:
        return None
    long_side = max(width, height)
    if long_side >= 7680: return "8k"
    if long_side >= 7000: return "7k"
    if long_side >= 6000: return "6k"
    if long_side >= 5120: return "5k"
    if long_side >= 3840: return "4k"
    return None


def classify_resolution(width, height):
    if not width or not height:
        return "Unknown"
    long_side = max(width, height)
    if long_side >= 7680: return "8K-class"
    if long_side >= 7000: return "7K-class"
    if long_side >= 6000: return "6K-class"
    if long_side >= 5120: return "5K-class"
    if long_side >= 3840: return "4K/UHD-class"
    if long_side >= 2560: return "1440p-class"
    if long_side >= 1920: return "1080p-class"
    if long_side >= 1280: return "720p-class"
    return "Below 720p"


def determine_bit_depth(pix_fmt, bits_raw_sample=None):
    if bits_raw_sample:
        try:
            bits = int(bits_raw_sample)
            if bits > 0:
                return bits
        except Exception:
            pass
    if not pix_fmt:
        return None
    p = pix_fmt.lower()
    if "p16" in p or "16le" in p or "16be" in p: return 16
    if "p14" in p or "14le" in p or "14be" in p: return 14
    if "p12" in p or "12le" in p or "12be" in p: return 12
    if "p10" in p or "10le" in p or "10be" in p: return 10
    if "p9" in p or "9le" in p or "9be" in p: return 9
    if p.startswith(("yuv", "nv12", "nv21", "rgb", "bgr")):
        return 8
    return None


def hdr_description(stream):
    transfer = (stream.get("color_transfer") or "").lower()
    primaries = (stream.get("color_primaries") or "").lower()
    color_space = (stream.get("color_space") or "").lower()
    if transfer == "smpte2084":
        return "HDR/PQ (likely HDR10-family)"
    if transfer == "arib-std-b67":
        return "HDR/HLG"
    if "bt2020" in primaries or "bt2020" in color_space:
        return "BT.2020 metadata present"
    return "No obvious HDR metadata"


def create_unique_aliases(paths):
    """Prevent alias collisions by appending _02, _03, etc."""
    counts = defaultdict(int)
    aliases = []
    for path in paths:
        stem = os.path.splitext(os.path.basename(path))[0]
        words = re.findall(r"[A-Za-z0-9]+", stem)
        base = "_".join(w[:3] for w in words) if words else "FIL"
        counts[base] += 1
        if counts[base] == 1:
            aliases.append(base)
        else:
            aliases.append(f"{base}_{counts[base]:02d}")
    return aliases


def run_ffprobe(path, streams_only=False):
    cmd = ["ffprobe", "-v", "error", "-of", "json"]
    if streams_only:
        cmd += ["-select_streams", "v:0", "-show_entries", "stream=width,height"]
    else:
        cmd += ["-show_format", "-show_streams"]
    cmd.append(str(path))
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=120, check=False)
        if result.returncode != 0:
            return None, result.stderr.strip()
        return json.loads(result.stdout), None
    except Exception as exc:
        return None, str(exc)


@lru_cache(maxsize=None)
def get_duration(path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def filename_tokens(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return [t.lower() for t in re.findall(r"[A-Za-z0-9]+", stem)]


def split_camel(text):
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', text)


def tokenize(filename):
    stem = Path(filename).stem
    stem = split_camel(stem).lower()
    stem = re.sub(r'[._\-\[\](){}!@#$%^&*+=,<>?/\\|`~"\']', ' ', stem)
    return [t for t in stem.split() if t]


def is_noise_token(tok):
    if tok in NOISE_WORDS:
        return True
    return any(pat.match(tok) for pat in NOISE_TOKEN_PATTERNS)


def is_identifier_token(tok):
    if tok.isdigit() or tok in ROMAN_NUMERALS:
        return True
    return len(tok) == 1 and tok.isalpha()


def is_series_marker(tok):
    if is_identifier_token(tok):
        return True
    return bool(re.match(r'^(sc|scene|s|part|pt|ep|e|vol|v|ch|chapter|p)\d+$', tok))


# ═══════════════════════════════════════════════════════════════════════════════
#  1. CLEAN — Filename cleaner
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_clean(args):
    """Strip junk from filenames: non-ASCII, brackets, dots, underscores."""

    section("CLEAN FILENAMES")

    path = Path(args.path).resolve()
    if not path.is_dir():
        error(f"Path does not exist: {path}")
        sys.exit(1)

    info(f"Path      : {C.BWHITE}{path}{C.RST}")
    info(f"Recursive : {C.BWHITE}{'yes' if args.recursive else 'no'}{C.RST}")
    print()

    def clean_filename(name):
        base, ext = os.path.splitext(name)
        base = re.sub(r'[^\x00-\x7F]', '', base)
        base = re.sub(r'[\[\]]', '', base)
        base = re.sub(r'(\w)\.(\w)', r'\1 \2', base)
        base = re.sub(r'[_-]', ' ', base)
        base = re.sub(r'\s+', ' ', base).strip(' -_')
        return base + ext

    candidates = []
    skipped = 0
    walker = os.walk(path) if args.recursive else [(str(path), [], os.listdir(path))]

    for dirpath, _, filenames in walker:
        for filename in filenames:
            new_name = clean_filename(filename)
            if new_name == filename:
                continue
            src = os.path.join(dirpath, filename)
            dst = os.path.join(dirpath, new_name)
            if os.path.exists(dst) and src != dst:
                warn(f"SKIP (exists): {new_name}")
                skipped += 1
                continue
            candidates.append((src, dst, filename, new_name))

    if not candidates:
        success("Nothing to rename — all filenames are clean.")
        return

    for _, _, old, new in candidates:
        print(f"  {C.DIM}{old}{C.RST}")
        print(f"  {C.BGREEN}→ {new}{C.RST}\n")

    print(f"  {C.BWHITE}{len(candidates)}{C.RST} file(s) to rename, {skipped} skipped.\n")

    if args.dry_run:
        success("DRY RUN — no changes made.")
        return

    if not confirm("Apply renames?"):
        warn("Aborted.")
        return

    for src, dst, _, _ in candidates:
        os.rename(src, dst)
    success(f"Done: {C.BWHITE}{len(candidates)}{C.RST} renamed.")


# ═══════════════════════════════════════════════════════════════════════════════
#  2. DIRNAME — Rename files to match parent directory
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_dirname(args):
    """Rename files to match their parent directory name."""

    section("RENAME BY DIRECTORY")

    path = Path(args.path).resolve()
    if not path.is_dir():
        error(f"Not a directory: {path}")
        sys.exit(1)

    info(f"Path : {C.BWHITE}{path}{C.RST}")
    print()

    candidates = []
    skipped = 0

    for dirpath, _, filenames in os.walk(path):
        dirpath = Path(dirpath).resolve()
        if dirpath == path:
            continue
        files = [f for f in filenames if not f.startswith('.')]
        if not files:
            continue

        dir_name = dirpath.name
        for index, filename in enumerate(sorted(files), start=1):
            ext = Path(filename).suffix
            new_name = f"{dir_name}{ext}" if len(files) == 1 else f"{dir_name}_{index:02d}{ext}"
            src, dst = dirpath / filename, dirpath / new_name

            if src == dst:
                skipped += 1
                continue
            if dst.exists():
                warn(f"SKIP (exists): {new_name}")
                skipped += 1
                continue
            candidates.append((src, dst, dir_name, filename, new_name))

    if not candidates:
        success("Nothing to rename.")
        return

    current_dir = None
    for src, dst, dir_name, old, new in candidates:
        if dir_name != current_dir:
            current_dir = dir_name
            print(f"  {C.BCYAN}[{dir_name}]{C.RST}")
        print(f"    {C.DIM}{old}{C.RST}")
        print(f"    {C.BGREEN}→ {new}{C.RST}")

    print(f"\n  {C.BWHITE}{len(candidates)}{C.RST} file(s) to rename, {skipped} skipped.\n")

    if args.dry_run:
        success("DRY RUN — no changes made.")
        return

    if not confirm("Apply renames?"):
        warn("Aborted.")
        return

    errors = 0
    for src, dst, _, _, _ in candidates:
        try:
            src.rename(dst)
        except OSError as e:
            error(f"  {e}")
            errors += 1
    success(f"Done: {len(candidates) - errors} renamed, {errors} errors.")


# ═══════════════════════════════════════════════════════════════════════════════
#  3. RESTAG — Resolution tagging via ffprobe
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_restag(args):
    """Add 4k/5k/6k/7k/8k resolution tags to video filenames."""

    section("RESOLUTION TAGGER")

    root = Path(args.path).resolve()
    if not root.is_dir():
        error(f"Not a directory: {root}")
        sys.exit(1)

    videos = discover_videos(root)
    already_tagged = [p for p in videos if set(filename_tokens(p)) & RESOLUTION_TAGS]
    needs_probe = [p for p in videos if not (set(filename_tokens(p)) & RESOLUTION_TAGS)]

    info(f"Repository      : {C.BWHITE}{root}{C.RST}")
    info(f"Videos found    : {C.BWHITE}{len(videos)}{C.RST}")
    info(f"Already tagged  : {C.BGREEN}{len(already_tagged)}{C.RST}")
    info(f"Need resolution : {C.BYELLOW}{len(needs_probe)}{C.RST}")
    print()

    if args.dry_run:
        success("DRY RUN — no ffprobe executed, no files renamed.")
        return

    if not needs_probe:
        success("All videos already have resolution tags.")
        return

    if not confirm("Proceed with read-only resolution probe?"):
        warn("Cancelled.")
        return

    candidates, probe_errors = [], []
    for i, path in enumerate(needs_probe, 1):
        print(f"  {C.DIM}[{i}/{len(needs_probe)}]{C.RST} {os.path.basename(path)}", end="\r")
        data, err = run_ffprobe(path, streams_only=True)
        if err:
            probe_errors.append((path, err))
            continue
        streams = data.get("streams", [])
        if not streams:
            continue
        w, h = streams[0].get("width"), streams[0].get("height")
        tag = detected_resolution_tag(w, h)
        if tag:
            stem, ext = os.path.splitext(path)
            new_path = f"{stem} {tag}{ext}"
            candidates.append({"path": path, "new_path": new_path, "tag": tag, "w": w, "h": h})

    print()
    section("PROBE COMPLETE")
    info(f"Candidates : {C.BWHITE}{len(candidates)}{C.RST}")
    info(f"Errors     : {C.BYELLOW}{len(probe_errors)}{C.RST}")
    print()

    if not candidates:
        dim("No files qualify for resolution tags (all below 4K).")
        return

    for rec in candidates[:20]:
        print(f"  {C.DIM}{os.path.basename(rec['path'])}{C.RST}")
        print(f"  {C.BGREEN}→ {os.path.basename(rec['new_path'])}{C.RST} ({rec['tag']})\n")
    if len(candidates) > 20:
        dim(f"  ... and {len(candidates) - 20} more")

    if not args.apply:
        print()
        warn("Run with --apply to rename files.")
        return

    print()
    answer = input(f'  {C.BYELLOW}?{C.RST} Type {C.BOLD}RENAME RES{C.RST} to confirm: ').strip()
    if answer != "RENAME RES":
        warn("Cancelled.")
        return

    for rec in candidates:
        if not os.path.exists(rec["new_path"]):
            os.rename(rec["path"], rec["new_path"])
    success(f"Renamed {len(candidates)} files.")


# ═══════════════════════════════════════════════════════════════════════════════
#  4. PROBE — Anonymized video metadata report
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_probe(args):
    """Full ffprobe metadata scan with anonymized report (from probe_scramble.py)."""

    section("VIDEO PROBE")

    root = Path(args.path).resolve()
    if not root.is_dir():
        error(f"Not a directory: {root}")
        sys.exit(1)

    output = Path(args.output).resolve() if args.output else Path("video_probe_report.txt").resolve()
    videos = discover_videos(root)

    info(f"Path        : {C.BWHITE}{root}{C.RST}")
    info(f"Videos      : {C.BWHITE}{len(videos)}{C.RST}")
    info(f"Report      : {C.BWHITE}{output}{C.RST}")
    print()

    if args.dry_run:
        success("DRY RUN — no ffprobe, no report written.")
        return

    if not videos:
        warn("No video files found.")
        return

    if not confirm("Proceed with read-only ffprobe scan?"):
        warn("Cancelled.")
        return

    aliases = create_unique_aliases(videos)

    with open(output, "w", encoding="utf-8") as report:
        report.write("=" * 78 + "\n")
        report.write("ANONYMIZED READ-ONLY VIDEO FFPROBE REPORT\n")
        report.write("=" * 78 + "\n")
        report.write(f"Total files probed: {len(videos)}\n")
        report.write("Full source filenames and paths omitted.\n")
        report.write("Identifiers use the first 3 case-sensitive characters of each filename word.\n")
        report.write("Source files were opened by ffprobe for reading only.\n")
        report.write("=" * 78 + "\n\n")

        for i, (path, alias) in enumerate(zip(videos, aliases), 1):
            print(f"  {C.DIM}[{i}/{len(videos)}]{C.RST} {alias}", end="\r")
            data, err = run_ffprobe(path)

            report.write("=" * 78 + "\n")
            report.write(f"{alias}\n")
            report.write("=" * 78 + "\n")

            if err or not data:
                report.write(f"FFPROBE ERROR: {err}\n\n")
                continue

            streams = data.get("streams", [])
            fmt = data.get("format", {})
            video_streams = [s for s in streams if s.get("codec_type") == "video"]
            audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

            if not video_streams:
                report.write("No video stream detected.\n\n")
                continue

            v = video_streams[0]
            w, h = v.get("width"), v.get("height")
            fps = get_fps(v)
            dur = safe_float(v.get("duration")) or safe_float(fmt.get("duration"))
            size_bytes = safe_float(fmt.get("size"))
            vbr = safe_float(v.get("bit_rate"))
            overall_br = safe_float(fmt.get("bit_rate"))

            video_mbps = vbr / 1e6 if vbr else None
            overall_mbps = overall_br / 1e6 if overall_br else None
            size_gib = size_bytes / (1024**3) if size_bytes else None
            size_gb = size_bytes / 1e9 if size_bytes else None
            gb_per_hour = (size_bytes / 1e9) / (dur / 3600) if size_bytes and dur and dur > 0 else None
            bpp = vbr / (w * h * fps) if vbr and w and h and fps and fps > 0 else None
            pix_fmt = v.get("pix_fmt")
            bit_depth = determine_bit_depth(pix_fmt, v.get("bits_per_raw_sample"))

            # VIDEO
            report.write("VIDEO\n")
            report.write(f"  Resolution             : {w} x {h}\n")
            report.write(f"  Resolution class       : {classify_resolution(w, h)}\n")
            report.write(f"  Codec                  : {v.get('codec_name', 'Unknown')}\n")
            report.write(f"  Codec long name        : {v.get('codec_long_name', 'Unknown')}\n")
            report.write(f"  Profile                : {v.get('profile', 'Unknown')}\n")
            report.write(f"  Codec level            : {v.get('level', 'Unknown')}\n")
            report.write(f"  Pixel format           : {pix_fmt or 'Unknown'}\n")
            report.write(f"  Estimated bit depth    : {bit_depth if bit_depth else 'Unknown'}\n")
            report.write(f"  FPS                    : {fmt_num(fps, 3)}\n")
            report.write(f"  Avg frame rate raw     : {v.get('avg_frame_rate', 'Unknown')}\n")
            report.write(f"  Real frame rate raw    : {v.get('r_frame_rate', 'Unknown')}\n")
            report.write(f"  Video bitrate          : {fmt_num(video_mbps, 3)} Mbps\n")

            # COLOR / HDR
            report.write("\nCOLOR / HDR\n")
            report.write(f"  Color range            : {v.get('color_range', 'Unknown')}\n")
            report.write(f"  Color space            : {v.get('color_space', 'Unknown')}\n")
            report.write(f"  Color transfer         : {v.get('color_transfer', 'Unknown')}\n")
            report.write(f"  Color primaries        : {v.get('color_primaries', 'Unknown')}\n")
            report.write(f"  HDR interpretation     : {hdr_description(v)}\n")

            # FILE / COMPRESSION
            report.write("\nFILE / COMPRESSION\n")
            report.write(f"  Duration               : {fmt_duration(dur)}\n")
            report.write(f"  Duration seconds       : {fmt_num(dur, 3)}\n")
            report.write(f"  File size GiB          : {fmt_num(size_gib, 3)} GiB\n")
            report.write(f"  File size GB           : {fmt_num(size_gb, 3)} GB\n")
            report.write(f"  File size bytes        : {int(size_bytes) if size_bytes is not None else 'Unknown'}\n")
            report.write(f"  Overall bitrate        : {fmt_num(overall_mbps, 3)} Mbps\n")
            report.write(f"  Data per hour          : {fmt_num(gb_per_hour, 3)} GB/hour\n")
            report.write(f"  Bits/pixel/frame       : {fmt_num(bpp, 6)}\n")
            report.write(f"  Container              : {fmt.get('format_name', 'Unknown')}\n")

            # STREAMS
            report.write("\nSTREAMS\n")
            report.write(f"  Total streams          : {len(streams)}\n")
            report.write(f"  Video streams          : {len(video_streams)}\n")
            report.write(f"  Audio streams          : {len(audio_streams)}\n")

            for ai, audio in enumerate(audio_streams, 1):
                a_br = safe_float(audio.get("bit_rate"))
                a_mbps = a_br / 1e6 if a_br else None
                report.write(f"\n  Audio #{ai}\n")
                report.write(f"    Codec                : {audio.get('codec_name', 'Unknown')}\n")
                report.write(f"    Profile              : {audio.get('profile', 'Unknown')}\n")
                report.write(f"    Sample rate          : {audio.get('sample_rate', 'Unknown')} Hz\n")
                report.write(f"    Channels             : {audio.get('channels', 'Unknown')}\n")
                report.write(f"    Channel layout       : {audio.get('channel_layout', 'Unknown')}\n")
                report.write(f"    Bitrate              : {fmt_num(a_mbps, 3)} Mbps\n")

            # ENCODING METADATA
            tags = v.get("tags", {})
            useful_keys = ["encoder", "ENCODER", "BPS", "BPS-eng",
                           "NUMBER_OF_FRAMES", "NUMBER_OF_FRAMES-eng"]
            selected_tags = {k: tags[k] for k in useful_keys if k in tags}
            if selected_tags:
                report.write("\nENCODING METADATA\n")
                for key, value in selected_tags.items():
                    report.write(f"  {key:<22}: {value}\n")

            report.write("\n")

    print()
    success(f"Report written: {output}")


# ═══════════════════════════════════════════════════════════════════════════════
#  5. HQ — Peer-based high-quality detection
# ═══════════════════════════════════════════════════════════════════════════════

HQ_RATIO_THRESHOLD = 1.12
MIN_GROUP_SIZE = 5
MIN_LONG_SIDE_FOR_HQ = 3840

HQ_PLAN_FILE = "HQ_RENAME_PLAN.json"
HQ_DRY_RUN_REPORT = "HQ_DRY_RUN.txt"
HQ_FULL_REPORT = "video_probe_full_report.txt"


def _hq_proposed_path(record):
    """Build proposed filename: append missing resolution + HQ tags."""
    path = record["path"]
    stem, ext = os.path.splitext(path)
    tokens = set(filename_tokens(path))
    additions = []
    res_tag = record.get("detected_resolution_tag") or record.get("res_tag")
    if not (RESOLUTION_TAGS & tokens) and res_tag:
        additions.append(res_tag)
    if not (QUALITY_TAGS & tokens):
        additions.append("HQ")
    if not additions:
        return path
    return stem + " " + " ".join(additions) + ext


def _hq_save_plan(root, candidates):
    """Persist HQ rename plan to JSON (zero reprobe needed to apply later)."""
    plan = {
        "version": 1,
        "repository_root": os.path.realpath(str(root)),
        "created_from_single_probe_run": True,
        "candidates": [],
    }
    for rec in candidates:
        old_path = rec["path"]
        new_path = _hq_proposed_path(rec)
        try:
            stat = os.stat(old_path)
        except OSError:
            continue
        plan["candidates"].append({
            "path": old_path,
            "new_path": new_path,
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "width": rec.get("w") or rec.get("width"),
            "height": rec.get("h") or rec.get("height"),
            "fps": rec.get("fps"),
            "codec": rec.get("codec"),
            "video_mbps": rec.get("mbps") or rec.get("video_mbps"),
            "bpp": rec.get("bpp"),
            "resolution_tag": rec.get("res_tag") or rec.get("detected_resolution_tag"),
            "group_size": rec.get("peers") or rec.get("group_size"),
            "median_bitrate": rec.get("median_bitrate"),
            "bitrate_ratio": rec.get("ratio") or rec.get("bitrate_ratio"),
        })
    plan["candidate_count"] = len(plan["candidates"])
    with open(HQ_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return HQ_PLAN_FILE


def _hq_write_dry_run(root, candidates):
    """Write HQ_DRY_RUN.txt showing proposed renames without applying."""
    with open(HQ_DRY_RUN_REPORT, "w", encoding="utf-8") as rpt:
        rpt.write("=" * 100 + "\n")
        rpt.write("HQ RENAME DRY RUN\nNO SOURCE FILES HAVE BEEN RENAMED\n")
        rpt.write("=" * 100 + "\n")
        rpt.write(f"Repository root : {root}\nHQ candidates   : {len(candidates)}\n")
        rpt.write("=" * 100 + "\n\n")
        if not candidates:
            rpt.write("NO HQ CANDIDATES FOUND.\n")
            return
        for idx, rec in enumerate(candidates, 1):
            rpt.write(f"[{idx}]\nCURRENT:\n{rec['path']}\n\nPROPOSED:\n{_hq_proposed_path(rec)}\n\n")
            rpt.write(f"Resolution : {rec.get('w', '?')}x{rec.get('h', '?')} ({rec.get('res_tag', '?')})\n")
            rpt.write(f"FPS        : {fmt_num(rec.get('fps'), 3)}\n")
            rpt.write(f"Codec      : {rec.get('codec', '?')}\n")
            rpt.write(f"Bitrate    : {fmt_num(rec.get('mbps'), 3)} Mbps\n")
            rpt.write(f"BPP/frame  : {fmt_num(rec.get('bpp'), 6)}\n")
            rpt.write(f"Peers      : {rec.get('peers', '?')}\n")
            if rec.get("median_bitrate"):
                rpt.write(f"Peer median: {rec['median_bitrate']:.3f} Mbps\n")
            rpt.write(f"HQ ratio   : {rec.get('ratio', 0):.3f}x\n")
            rpt.write("-" * 100 + "\n\n")


def _hq_validate_plan(plan):
    """Validate saved plan: source exists, unchanged, dest free."""
    errors = []
    dest_map = defaultdict(list)
    for rec in plan.get("candidates", []):
        old, new = rec["path"], rec["new_path"]
        if not os.path.isfile(old):
            errors.append((old, new, "source file no longer exists"))
            continue
        if os.path.islink(old):
            errors.append((old, new, "source is now a symlink"))
            continue
        try:
            stat = os.stat(old)
        except OSError as e:
            errors.append((old, new, f"could not stat: {e}"))
            continue
        if rec.get("size_bytes") is not None and stat.st_size != rec["size_bytes"]:
            errors.append((old, new, "file size changed since probe"))
        if rec.get("mtime_ns") is not None and stat.st_mtime_ns != rec["mtime_ns"]:
            errors.append((old, new, "modification time changed since probe"))
        if os.path.exists(new):
            errors.append((old, new, "destination already exists"))
        dest_map[os.path.normcase(os.path.abspath(new))].append(old)
    for dest, sources in dest_map.items():
        if len(sources) > 1:
            for s in sources:
                errors.append((s, dest, "multiple sources target same destination"))
    return errors


def _hq_apply_plan(root):
    """Stage 2: Load saved plan, validate, and rename (zero ffprobe)."""
    section("APPLY SAVED HQ PLAN")

    if not os.path.isfile(HQ_PLAN_FILE):
        error(f"No saved plan found: {HQ_PLAN_FILE}")
        info("Run 'hq <path>' first to probe and generate the plan.")
        return

    with open(HQ_PLAN_FILE, "r", encoding="utf-8") as f:
        plan = json.load(f)

    saved_root = os.path.realpath(plan.get("repository_root", ""))
    requested_root = os.path.realpath(str(root))
    if saved_root != requested_root:
        error("Repository mismatch!")
        info(f"Plan root     : {saved_root}")
        info(f"Requested root: {requested_root}")
        return

    candidates = plan.get("candidates", [])
    info(f"Saved HQ candidates : {C.BWHITE}{len(candidates)}{C.RST}")
    info(f"Plan file           : {C.BWHITE}{HQ_PLAN_FILE}{C.RST}")
    info(f"ffprobe will NOT run.")
    print()

    if not candidates:
        warn("Plan contains no candidates.")
        return

    errors = _hq_validate_plan(plan)
    if errors:
        error("PLAN VALIDATION FAILED — nothing renamed.")
        print()
        for old, new, reason in errors[:15]:
            print(f"  {C.BRED}✗{C.RST} {os.path.basename(old)}")
            print(f"    {C.DIM}{reason}{C.RST}\n")
        if len(errors) > 15:
            dim(f"  ... and {len(errors) - 15} more errors")
        return

    success("Plan validated.")
    print()
    for idx, rec in enumerate(candidates, 1):
        print(f"  {C.DIM}[{idx}/{len(candidates)}]{C.RST}")
        print(f"    {C.DIM}{os.path.basename(rec['path'])}{C.RST}")
        print(f"    {C.BGREEN}→ {os.path.basename(rec['new_path'])}{C.RST}\n")

    print()
    answer = input(f'  {C.BYELLOW}?{C.RST} Type {C.BOLD}RENAME HQ{C.RST} to apply: ').strip()
    if answer != "RENAME HQ":
        warn("Cancelled. Nothing renamed.")
        return

    renamed = 0
    for rec in candidates:
        try:
            os.rename(rec["path"], rec["new_path"])
            renamed += 1
        except OSError as e:
            error(f"  {os.path.basename(rec['path'])}: {e}")

    print()
    success(f"Renamed {renamed}/{len(candidates)} files.")

    try:
        os.replace(HQ_PLAN_FILE, HQ_PLAN_FILE + ".applied")
        dim(f"  Plan archived: {HQ_PLAN_FILE}.applied")
    except OSError:
        pass


def cmd_hq(args):
    """HQ peer-bitrate analysis with 2-stage workflow (probe_full.py)."""

    root = Path(args.path).resolve()
    if not root.is_dir():
        error(f"Not a directory: {root}")
        sys.exit(1)

    # Stage 2: apply saved plan (zero ffprobe)
    if args.apply_hq:
        _hq_apply_plan(root)
        return

    # Stage 1: probe + analyze + save plan
    section("HQ ANALYZER")

    videos = discover_videos(root)

    def is_fully_tagged(path):
        tokens = set(filename_tokens(path))
        return bool(QUALITY_TAGS & tokens) and bool(RESOLUTION_TAGS & tokens)

    to_probe = [p for p in videos if not is_fully_tagged(p)]
    skipped = [p for p in videos if is_fully_tagged(p)]

    info(f"Repository    : {C.BWHITE}{root}{C.RST}")
    info(f"Total videos  : {C.BWHITE}{len(videos)}{C.RST}")
    info(f"Already tagged: {C.BGREEN}{len(skipped)}{C.RST}")
    info(f"Need analysis : {C.BYELLOW}{len(to_probe)}{C.RST}")
    print()

    if args.dry_run:
        success("DRY RUN — filename analysis only, no ffprobe.")
        return

    if not to_probe:
        success("All videos fully tagged.")
        return

    info(f"ffprobe will READ {len(to_probe)} files ONCE.")
    info("After this run, HQ_RENAME_PLAN.json will hold the rename plan.")
    info("Use --apply-hq to rename WITHOUT re-probing.")
    print()

    if not confirm(f"Proceed with one-pass read-only analysis?"):
        warn("Cancelled.")
        return

    records = []
    errors = []
    for i, path in enumerate(to_probe, 1):
        print(f"  {C.DIM}[{i}/{len(to_probe)}]{C.RST} {os.path.basename(path)[:60]}", end="\r")
        data, err = run_ffprobe(path)
        if err or not data:
            errors.append((path, err or "Unknown"))
            continue
        streams = data.get("streams", [])
        fmt = data.get("format", {})
        vs = [s for s in streams if s.get("codec_type") == "video"]
        if not vs:
            errors.append((path, "No video stream"))
            continue
        v = vs[0]
        w, h = v.get("width"), v.get("height")
        fps = get_fps(v)
        vbr = safe_float(v.get("bit_rate")) or safe_float(fmt.get("bit_rate"))
        if not all([w, h, fps, vbr]):
            continue
        dur = safe_float(v.get("duration")) or safe_float(fmt.get("duration"))
        size_bytes = safe_float(fmt.get("size"))
        bpp = vbr / (w * h * fps) if fps > 0 else None
        records.append({
            "path": path, "w": w, "h": h, "fps": fps,
            "codec": v.get("codec_name", "?"),
            "profile": v.get("profile", "?"),
            "vbr": vbr, "mbps": vbr / 1e6, "bpp": bpp,
            "duration": dur, "size_bytes": size_bytes,
            "group_key": (v.get("codec_name"), w, h, fps_bucket(fps)),
            "res_tag": detected_resolution_tag(w, h),
        })

    # Classify using peer groups
    groups = defaultdict(list)
    for r in records:
        if r["bpp"]:
            groups[r["group_key"]].append(r)

    candidates = []
    for key, group in groups.items():
        if len(group) < MIN_GROUP_SIZE:
            continue
        median_mbps = statistics.median(r["mbps"] for r in group)
        median_bpp = statistics.median(r["bpp"] for r in group)
        for r in group:
            if max(r["w"], r["h"]) < MIN_LONG_SIDE_FOR_HQ or not r["res_tag"]:
                continue
            ratio = r["mbps"] / median_mbps
            bpp_ratio = r["bpp"] / median_bpp
            if ratio >= HQ_RATIO_THRESHOLD and bpp_ratio >= HQ_RATIO_THRESHOLD:
                r["ratio"] = ratio
                r["bpp_ratio"] = bpp_ratio
                r["peers"] = len(group)
                r["median_bitrate"] = median_mbps
                r["median_bpp"] = median_bpp
                candidates.append(r)

    candidates.sort(key=lambda r: r.get("ratio", 0), reverse=True)

    # Write reports + plan
    _hq_write_dry_run(root, candidates)
    plan_path = _hq_save_plan(root, candidates)

    print()
    section("HQ ANALYSIS COMPLETE")
    info(f"Probed          : {C.BWHITE}{len(records)}{C.RST}")
    info(f"Probe errors    : {C.BYELLOW}{len(errors)}{C.RST}")
    info(f"HQ candidates   : {C.BMAGENTA}{len(candidates)}{C.RST}")
    print()

    for rec in candidates[:30]:
        base = os.path.basename(rec["path"])
        print(f"  {C.BMAGENTA}{rec['ratio']:.2f}x{C.RST} {base[:55]}")
        print(f"       {rec['mbps']:.1f} Mbps | {rec['res_tag']} | {rec['peers']} peers\n")

    if not candidates:
        dim("No HQ candidates found.")
    else:
        print()
        success(f"Dry-run report : {HQ_DRY_RUN_REPORT}")
        success(f"Rename plan    : {plan_path}")
        print()
        info("NO FILENAMES HAVE BEEN CHANGED.")
        info(f"To apply: {C.BWHITE}sweet_life hq {root} --apply-hq{C.RST}")


# ═══════════════════════════════════════════════════════════════════════════════
#  6. UHDTAG — Tag large files with UHD HQ
# ═══════════════════════════════════════════════════════════════════════════════

MIN_SIZE_BYTES = 40 * 1024**3  # 40 GiB

def cmd_uhdtag(args):
    """Rename files >= 40 GiB to end with 'UHD HQ'."""

    section("UHD HQ TAGGER")

    target = Path(args.path).resolve()
    quality_re = re.compile(r"(?:[\s._-]+(?:UHD|HQ))+\s*$", re.IGNORECASE)

    info(f"Path         : {C.BWHITE}{target}{C.RST}")
    info(f"Min size     : {C.BWHITE}40 GiB{C.RST}")
    info(f"Recursive    : {C.BWHITE}{'yes' if args.recursive else 'no'}{C.RST}")
    print()

    if not target.exists():
        error(f"Path does not exist: {target}")
        return

    def new_filename(fp):
        stem = fp.stem
        clean = quality_re.sub("", stem).rstrip(" ._-")
        return fp.with_name(f"{clean} UHD HQ{fp.suffix}")

    files = []
    if target.is_file():
        files = [target]
    else:
        it = target.rglob("*") if args.recursive else target.iterdir()
        files = [p for p in it if p.is_file()]

    candidates = []
    for fp in files:
        try:
            size = fp.stat().st_size
        except OSError:
            continue
        if size < MIN_SIZE_BYTES:
            continue
        dest = new_filename(fp)
        if dest == fp:
            continue
        if dest.exists():
            warn(f"Cannot rename (exists): {dest.name}")
            continue
        candidates.append((fp, dest, size))

    if not candidates:
        success("No files >= 40 GiB need tagging.")
        return

    for fp, dest, size in candidates:
        gib = size / (1024**3)
        print(f"  {C.DIM}{fp.name}{C.RST} ({gib:.1f} GiB)")
        print(f"  {C.BGREEN}→ {dest.name}{C.RST}\n")

    print(f"  {C.BWHITE}{len(candidates)}{C.RST} file(s) to tag.\n")

    if args.dry_run:
        success("DRY RUN — no changes made.")
        return

    if not confirm("Apply UHD HQ tags?"):
        warn("Aborted.")
        return

    for fp, dest, _ in candidates:
        fp.rename(dest)
    success(f"Renamed {len(candidates)} files.")


# ═══════════════════════════════════════════════════════════════════════════════
#  7. AUDIO — Extract audio tracks
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_audio(args):
    """Extract audio tracks from video files using ffmpeg."""

    section("AUDIO EXTRACTOR")

    target = Path(args.path).resolve()
    if not target.is_dir():
        error(f"Not a directory: {target}")
        sys.exit(1)

    info(f"Path    : {C.BWHITE}{target}{C.RST}")
    if args.keyword:
        info(f"Filter  : {C.BYELLOW}{args.keyword}{C.RST}")
    print()

    exts = (".webm", ".mkv", ".mp4", ".mov")
    files = [f for f in target.iterdir() if f.suffix.lower() in exts and f.is_file()]

    if args.keyword:
        kw = args.keyword.lower()
        files = [f for f in files if kw in f.name.lower()]

    info(f"Files   : {C.BWHITE}{len(files)}{C.RST}")
    print()

    if not files:
        warn("No matching files.")
        return

    if not confirm("Extract audio tracks?"):
        warn("Cancelled.")
        return

    for vid in files:
        try:
            cmd = ["ffprobe", "-hide_banner", "-loglevel", "panic",
                   "-select_streams", "a:0", "-show_entries", "stream=codec_name",
                   "-of", "default=noprint_wrappers=1:nokey=1", str(vid)]
            codec = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
            if not codec:
                warn(f"No audio: {vid.name}")
                continue
            out = vid.with_suffix(f".{codec}")
            print(f"  {C.BCYAN}{vid.name}{C.RST} → {C.BGREEN}{out.name}{C.RST}")
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-i", str(vid),
                           "-acodec", "copy", str(out)],
                          capture_output=True, timeout=300)
        except Exception as e:
            error(f"{vid.name}: {e}")

    print()
    success("Audio extraction complete.")


# ═══════════════════════════════════════════════════════════════════════════════
#  8. NAMES — Recurring name pattern finder
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_names(args):
    """Find recurring 2–3 word name patterns in filenames."""

    section("NAME PATTERN FINDER")

    root = Path(args.path).resolve()
    if not root.is_dir():
        error(f"Not a directory: {root}")
        sys.exit(1)

    output = root / "top_names.txt"

    ignore_words = {
        "1080", "720", "2160", "4k", "uhd", "hd", "fhd",
        "trim", "scene", "clip", "video", "movie", "full", "part",
        "mp4", "mkv", "mov", "avi", "wmv", "webm", "www", "com", "net", "org"
    }

    info(f"Scanning: {C.BWHITE}{root}{C.RST}")
    print()

    files = list(root.rglob("*")) if args.recursive else list(root.iterdir())
    files = [f for f in files if f.is_file()]
    info(f"Files: {C.BWHITE}{len(files)}{C.RST}")

    counts = defaultdict(int)
    for f in files:
        clean = f.stem.lower()
        clean = re.sub(r'[_\-.\(\)\[\]{},]+', ' ', clean)
        clean = re.sub(r'\b\d{1,4}p?\b', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        words = [w for w in clean.split() if len(w) >= 2 and w.isalpha() and w not in ignore_words]

        for i in range(len(words) - 1):
            counts[f"{words[i]} {words[i+1]}"] += 1
        for i in range(len(words) - 2):
            counts[f"{words[i]} {words[i+1]} {words[i+2]}"] += 1

    results = sorted(((k, v) for k, v in counts.items() if v >= 2),
                     key=lambda x: -x[1])[:100]

    with open(output, "w", encoding="utf-8") as f:
        f.write("Top Recurring Name Patterns\n" + "=" * 40 + "\n\n")
        for name, count in results:
            f.write(f"{name} : {count}\n")

    print()
    for name, count in results[:20]:
        bar = "█" * min(count, 30)
        print(f"  {C.BMAGENTA}{count:3d}{C.RST} {C.BCYAN}{bar}{C.RST} {name}")

    if len(results) > 20:
        dim(f"  ... {len(results) - 20} more in report")
    print()
    success(f"Report: {output}")


# ═══════════════════════════════════════════════════════════════════════════════
#  9. DUPES — Find duplicates within directories
# ═══════════════════════════════════════════════════════════════════════════════

def classify_pair(signal_a, signal_b):
    if not signal_a or not signal_b:
        return None
    if signal_a == signal_b:
        return "DUPLICATE" if len(signal_a) >= 3 else None
    diff = (signal_a - signal_b) | (signal_b - signal_a)
    if 0 < len(diff) <= 4 and all(is_series_marker(t) for t in diff):
        return "SERIES"
    union = signal_a | signal_b
    overlap = len(signal_a & signal_b)
    jaccard = overlap / len(union)
    if overlap >= 4 and jaccard >= 0.75:
        return "SIMILAR"
    return None


def run_dupe_scan(all_files, output_file, cross_only=False, side_labels=None):
    """Core duplicate scanning logic shared by dupes/compare commands."""

    total = len(all_files)
    side = side_labels or ["A"] * total

    with output_file.open("w", encoding="utf-8") as report:
        def log(line=""):
            print(line)
            report.write(line + "\n")

        log(f"{'=' * 70}")
        log(f"DUPLICATE SCAN REPORT — {datetime.now().isoformat(timespec='seconds')}")
        log(f"Files: {total}")
        log(f"{'=' * 70}\n")

        # Exact matches
        name_groups = defaultdict(lambda: defaultdict(list))
        for i, (filename, path) in enumerate(all_files):
            name_groups[filename][side[i]].append(path)

        exact_count = 0
        log("=== EXACT FILENAME MATCHES ===\n")
        for filename, groups in sorted(name_groups.items()):
            all_paths = []
            for s in sorted(groups.keys()):
                all_paths.extend((s, p) for p in groups[s])
            if cross_only:
                if len(groups) < 2:
                    continue
            else:
                if sum(len(v) for v in groups.values()) < 2:
                    continue
            exact_count += 1
            log(f"[EXACT #{exact_count}] {filename}")
            for s, p in all_paths:
                log(f"  {s}: {p}")
            log()
        if exact_count == 0:
            log("  None found.\n")

        # Token analysis
        raw_tokens_list = []
        doc_freq = defaultdict(int)
        for filename, _ in all_files:
            raw = tokenize(filename)
            cleaned = [t for t in raw if not is_noise_token(t)]
            raw_tokens_list.append(cleaned)
            for t in set(cleaned):
                doc_freq[t] += 1

        common_max = max(8, int(total * 0.004))
        common_tokens = {t for t, c in doc_freq.items() if c > common_max and not is_series_marker(t)}
        signal_sets = [frozenset(t for t in cleaned if t not in common_tokens) for cleaned in raw_tokens_list]

        # Inverted index
        index = defaultdict(list)
        for i, signal in enumerate(signal_sets):
            for t in signal:
                index[t].append(i)

        candidate_pairs = set()
        for token, idxs in index.items():
            if len(idxs) > 300:
                continue
            for a in range(len(idxs)):
                for b in range(a + 1, len(idxs)):
                    i, j = idxs[a], idxs[b]
                    if cross_only and side[i] == side[j]:
                        continue
                    candidate_pairs.add((min(i, j), max(i, j)))

        dup_pairs, sim_pairs, series_skip = [], [], 0
        for i, j in candidate_pairs:
            if all_files[i][0] == all_files[j][0]:
                continue
            result = classify_pair(signal_sets[i], signal_sets[j])
            if result == "SERIES":
                series_skip += 1
            elif result == "DUPLICATE":
                dup_pairs.append((all_files[i][1], all_files[j][1], signal_sets[i]))
            elif result == "SIMILAR":
                sim_pairs.append((all_files[i][1], all_files[j][1], signal_sets[i], signal_sets[j]))

        log("=== HIGH-CONFIDENCE DUPLICATES ===\n")
        if dup_pairs:
            for idx, (a, b, sig) in enumerate(dup_pairs, 1):
                log(f"[DUPLICATE #{idx}]")
                log(f"  Shared words ({len(sig)}): {sorted(sig)}")
                log(f"  1: {a}")
                log(f"  2: {b}")
                log()
        else:
            log("  None found.\n")

        log("=== POSSIBLE SIMILAR ===\n")
        if sim_pairs:
            for idx, (a, b, sa, sb) in enumerate(sim_pairs, 1):
                shared = sorted(sa & sb)
                log(f"[SIMILAR #{idx}]")
                log(f"  Shared words ({len(shared)}): {shared}")
                log(f"  1: {a}")
                log(f"  2: {b}")
                log()
        else:
            log("  None found.\n")

        log("=== SUMMARY ===")
        log(f"Files scanned       : {total}")
        log(f"Exact groups        : {exact_count}")
        log(f"High-confidence     : {len(dup_pairs)}")
        log(f"Similar pairs       : {len(sim_pairs)}")
        log(f"Series ignored      : {series_skip}")
        log(f"Report              : {output_file.resolve()}")

    return exact_count, len(dup_pairs), len(sim_pairs)


def cmd_dupes(args):
    """Find duplicate/similar filenames across directories."""

    section("DUPLICATE FINDER")

    roots = [Path(p).resolve() for p in args.paths]
    output = Path(args.output).resolve()

    for r in roots:
        status = f"{C.BGREEN}EXISTS{C.RST}" if r.exists() else f"{C.BRED}MISSING{C.RST}"
        info(f"{r} [{status}]")
    print()

    if not confirm("Read-only scan — no files changed. Proceed?"):
        warn("Aborted.")
        return

    all_files = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink()]
            for filename in filenames:
                path = Path(dirpath) / filename
                try:
                    if path.is_file() and not path.is_symlink():
                        all_files.append((filename, path.resolve()))
                except (PermissionError, OSError):
                    pass

    info(f"Total files: {C.BWHITE}{len(all_files)}{C.RST}")
    print()
    run_dupe_scan(all_files, output)
    print()
    success(f"Report: {output}")


# ═══════════════════════════════════════════════════════════════════════════════
# 10. COMPARE — Cross-directory duplicate comparison
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_compare(args):
    """Compare 2+ directories for duplicates between them (not within)."""

    section("DIRECTORY COMPARE")

    dirs = [Path(p).resolve() for p in args.dirs]
    output = Path(args.output).resolve()

    if len(dirs) < 2:
        error("Need at least 2 directories.")
        sys.exit(1)

    for i, d in enumerate(dirs, 1):
        status = f"{C.BGREEN}OK{C.RST}" if d.exists() else f"{C.BRED}MISSING{C.RST}"
        info(f"Dir {i}: {d} [{status}]")
    print()

    if not confirm("Read-only cross-compare. Proceed?"):
        warn("Aborted.")
        return

    all_files = []
    side_labels = []
    for i, d in enumerate(dirs, 1):
        if not d.exists():
            continue
        label = str(i)
        for dirpath, dirnames, filenames in os.walk(d, followlinks=False):
            dirnames[:] = [dn for dn in dirnames if not (Path(dirpath) / dn).is_symlink()]
            for filename in filenames:
                path = Path(dirpath) / filename
                try:
                    if path.is_file() and not path.is_symlink():
                        all_files.append((filename, path.resolve()))
                        side_labels.append(label)
                except (PermissionError, OSError):
                    pass

    info(f"Total files: {C.BWHITE}{len(all_files)}{C.RST}")
    print()
    run_dupe_scan(all_files, output, cross_only=True, side_labels=side_labels)
    print()
    success(f"Report: {output}")


# ═══════════════════════════════════════════════════════════════════════════════
# 11. DEDUP — Interactive duplicate deletion
# ═══════════════════════════════════════════════════════════════════════════════

def _dedup_extract_date_tokens(name):
    """Pull number sequences that look like dates from a filename."""
    name = re.sub(r'[.\-_]', ' ', name.lower())
    return set(re.findall(r'\b\d{2,4}\b', name))


def _dedup_has_common_date(name1, name2):
    """True if both filenames share 2+ numeric tokens (date-like match)."""
    d1 = _dedup_extract_date_tokens(name1)
    d2 = _dedup_extract_date_tokens(name2)
    return len(d1 & d2) >= 2


def _dedup_choose_largest(paths):
    """Return (keep_path, [delete_paths]) sorted by size descending."""
    existing = [(p, p.stat().st_size) for p in paths if p.exists() and p.is_file()]
    if len(existing) < 2:
        return None, []
    existing.sort(key=lambda x: (-x[1], str(x[0])))
    return existing[0][0], [p for p, _ in existing[1:]]


def _dedup_short(name, max_len=48):
    return name if len(name) <= max_len else ".." + name[-(max_len - 2):]


def cmd_dedup(args):
    """Auto/interactive duplicate deletion with duration + date filtering."""

    section("SMART DEDUP")

    report_path = Path(args.report).resolve()
    if not report_path.exists():
        error(f"Report not found: {report_path}")
        sys.exit(1)

    info(f"Report : {C.BWHITE}{report_path}{C.RST}")
    info(f"Mode   : {C.BWHITE}{'auto (keep largest + filter)' if args.auto else 'interactive'}{C.RST}")
    if args.debug:
        info(f"Debug  : {C.BYELLOW}ON{C.RST}")
    print()

    # Parse report
    exact_groups, dup_pairs, sim_pairs = [], [], []
    current_exact = None
    current_pair = None
    current_kind = None
    path_re = re.compile(r'^\s*(\d+):\s*(.+)$')

    with report_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("[EXACT #"):
                if current_exact:
                    exact_groups.append(current_exact)
                if current_pair and current_kind:
                    (dup_pairs if current_kind == "DUPLICATE" else sim_pairs).append(current_pair)
                    current_pair = current_kind = None
                current_exact = {"label": line, "paths": []}
                continue
            if line.startswith("[DUPLICATE #") or line.startswith("[SIMILAR #"):
                if current_exact:
                    exact_groups.append(current_exact)
                    current_exact = None
                if current_pair and current_kind:
                    (dup_pairs if current_kind == "DUPLICATE" else sim_pairs).append(current_pair)
                current_kind = "DUPLICATE" if line.startswith("[DUPLICATE") else "SIMILAR"
                current_pair = {"label": line, "paths": []}
                continue
            if current_exact is not None:
                m = path_re.match(line)
                if m:
                    current_exact["paths"].append(Path(m.group(2).strip()))
            elif current_pair is not None:
                m = path_re.match(line)
                if m:
                    current_pair["paths"].append(Path(m.group(2).strip()))
                elif line.strip().startswith("A:") or line.strip().startswith("B:"):
                    p = line.split(":", 1)[1].strip() if ":" in line else ""
                    if p:
                        current_pair["paths"].append(Path(p))
    if current_exact:
        exact_groups.append(current_exact)
    if current_pair and current_kind:
        (dup_pairs if current_kind == "DUPLICATE" else sim_pairs).append(current_pair)

    all_groups = exact_groups + dup_pairs + sim_pairs
    info(f"Exact: {C.BWHITE}{len(exact_groups)}{C.RST} | "
         f"Dupes: {C.BWHITE}{len(dup_pairs)}{C.RST} | "
         f"Similar: {C.BWHITE}{len(sim_pairs)}{C.RST}")
    print()

    if not all_groups:
        warn("Nothing to review.")
        return

    if not args.auto:
        # Interactive mode (unchanged behavior)
        to_delete = []
        for group in all_groups:
            paths = [p for p in group.get("paths", []) if p.exists()]
            if len(paths) < 2:
                continue
            print(f"\n  {C.BCYAN}{C.BOLD}{group['label']}{C.RST}")
            sized = [(p, p.stat().st_size) for p in paths]
            sized.sort(key=lambda x: -x[1])
            largest = sized[0][1]

            for idx, (p, sz) in enumerate(sized, 1):
                marker = f" {C.BGREEN}<-- LARGEST{C.RST}" if sz == largest and len(sized) > 1 else ""
                dur = fmt_duration(get_duration(p))
                print(f"    {C.BYELLOW}[{idx}]{C.RST} {dur:>7} | {fmt_size(sz):>10} | {p.name}{marker}")
            print()

            while True:
                choices = "/".join(str(i) for i in range(1, len(sized) + 1))
                ans = input(f"    Delete? ({choices}/s=skip/q=quit): ").strip().lower()
                if ans == "q":
                    warn("Quitting.")
                    break
                if ans == "s":
                    dim("    Skipped.")
                    break
                if ans.isdigit() and 1 <= int(ans) <= len(sized):
                    to_delete.append(sized[int(ans) - 1][0])
                    success(f"    Marked: {sized[int(ans)-1][0].name}")
                    break
                error("    Invalid.")
            else:
                continue
            if ans == "q":
                break

        if not to_delete:
            warn("Nothing marked for deletion.")
            return

        total_bytes = sum(p.stat().st_size for p in to_delete if p.exists())
        print(f"\n  {C.BOLD}Marked: {len(to_delete)} files ({fmt_size(total_bytes)}){C.RST}\n")
        answer = input(f"  {C.BYELLOW}?{C.RST} Type {C.BOLD}YES{C.RST} to delete: ").strip()
        if answer != "YES":
            warn("Aborted.")
            return

        count = 0
        for p in to_delete:
            try:
                if p.exists():
                    p.unlink()
                    count += 1
            except OSError as e:
                error(f"{p.name}: {e}")
        print()
        success(f"Deleted {count} files.")
        return

    # AUTO MODE with duration + date filtering
    decisions = []
    for group in all_groups:
        paths = [p for p in group.get("paths", []) if p.exists()]
        keep, deletes = _dedup_choose_largest(paths)
        if keep and deletes:
            decisions.append((keep, deletes))
        elif args.debug and paths:
            dim(f"  [debug] skipped: {group.get('label', '?')} (<2 existing)")

    if not decisions:
        warn("Nothing to delete (no groups with 2+ existing files).")
        return

    # Probe durations
    to_probe = []
    for keep, deletes in decisions:
        to_probe.append(keep)
        to_probe.extend(deletes)
    to_probe = list(dict.fromkeys(to_probe))

    info(f"Probing duration on {C.BWHITE}{len(to_probe)}{C.RST} files...")
    print()
    for i, p in enumerate(to_probe, 1):
        print(f"  {C.DIM}[{i}/{len(to_probe)}] {p.name[:60]}{C.RST}", end="\r")
        get_duration(p)
    print()

    # Filter: keep only pairs where duration matches (within 1s) OR dates match
    filtered_decisions = []
    skipped_count = 0
    date_forced = 0
    for keep, deletes in decisions:
        keep_dur = get_duration(keep)
        matching = []
        for d in deletes:
            d_dur = get_duration(d)
            dur_match = (keep_dur is not None and d_dur is not None and abs(d_dur - keep_dur) <= 1.0)
            dates_match = _dedup_has_common_date(keep.name, d.name)
            if dur_match or dates_match:
                matching.append(d)
                if dates_match and not dur_match:
                    date_forced += 1
            elif args.debug:
                dim(f"  [debug] drop {d.name} (keep_dur={keep_dur:.1f}s del_dur={d_dur}s dates={dates_match})")
        if matching:
            filtered_decisions.append((keep, matching))
        else:
            skipped_count += 1

    print()
    info(f"After filter: {C.BWHITE}{len(filtered_decisions)}{C.RST} groups kept")
    info(f"Skipped (no duration/date match): {C.DIM}{skipped_count}{C.RST}")
    if date_forced:
        info(f"Forced in by shared date: {C.DIM}{date_forced}{C.RST}")
    print()

    if not filtered_decisions:
        warn("Nothing left to delete after duration/date filter.")
        return

    # Two-column summary
    keep_items = []
    del_items = []
    all_delete = []
    total_bytes = 0
    for keep, deletes in filtered_decisions:
        keep_items.append((fmt_duration(get_duration(keep)), _dedup_short(keep.name)))
        for d in deletes:
            del_items.append((fmt_duration(get_duration(d)), _dedup_short(d.name)))
            all_delete.append(d)
            sz = d.stat().st_size if d.exists() else 0
            total_bytes += sz

    print(f"  {C.BYELLOW}{C.BOLD}KEEPING{C.RST}{'':>30}{C.BMAGENTA}{C.BOLD}DELETING{C.RST}")
    print(f"  {C.BBLUE}{'─' * 56}  {'─' * 56}{C.RST}")
    max_rows = max(len(keep_items), len(del_items))
    for i in range(min(max_rows, 30)):
        left = f"{keep_items[i][0]:>7} {keep_items[i][1]}" if i < len(keep_items) else ""
        right = f"{del_items[i][0]:>7} {del_items[i][1]}" if i < len(del_items) else ""
        print(f"  {C.BYELLOW}{left:<56}{C.RST}  {C.BMAGENTA}{right}{C.RST}")
    if max_rows > 30:
        dim(f"  ... and {max_rows - 30} more rows")
    print(f"  {C.BBLUE}{'─' * 56}  {'─' * 56}{C.RST}")
    print(f"\n  Delete {C.BMAGENTA}{len(all_delete)}{C.RST} files | "
          f"Free {C.BMAGENTA}{fmt_size(total_bytes)}{C.RST}\n")

    answer = input(f"  {C.BYELLOW}?{C.RST} Type {C.BOLD}YES{C.RST} to delete: ").strip()
    if answer != "YES":
        warn("Aborted.")
        return

    count = 0
    for p in all_delete:
        try:
            if p.exists():
                p.unlink()
                count += 1
                print(f"  {C.BMAGENTA}DELETED{C.RST} {p.name}")
        except OSError as e:
            error(f"{p.name}: {e}")
    print()
    success(f"Deleted {count} files.")


# ═══════════════════════════════════════════════════════════════════════════════
# 12. JCLEAN — jdupes single-directory cleanup
# ═══════════════════════════════════════════════════════════════════════════════

DUPES_FILE = "dupes.txt"


def jdupes_delete_loop(dupes_path):
    """Parse jdupes output and delete duplicates (keep first in each group)."""
    deleted = 0
    first_in_group = True

    with open(dupes_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                first_in_group = True
                continue
            if not (line.startswith("/") or line.startswith("./")):
                continue
            if first_in_group:
                first_in_group = False
                print(f"  {C.BGREEN}keeping:{C.RST}  {line}")
            else:
                if os.path.isfile(line):
                    os.remove(line)
                    print(f"  {C.BRED}deleted:{C.RST}  {line}")
                    deleted += 1
    return deleted


def cmd_jclean(args):
    """Scan directory for exact duplicates using jdupes, then interactively delete."""

    section("JDUPES CLEAN")

    target = Path(args.path).resolve()
    dupes = Path(DUPES_FILE)

    info(f"Path : {C.BWHITE}{target}{C.RST}")
    print()

    if dupes.exists():
        warn(f"{DUPES_FILE} already exists.")
        choice = input(f"  {C.BYELLOW}?{C.RST} Use existing file or rescan? (use/rescan): ").strip().lower()
        if choice == "rescan":
            info(f"Scanning for duplicates in: {target}")
            result = subprocess.run(["jdupes", "-r", "-S", str(target)],
                                    capture_output=True, text=True)
            dupes.write_text(result.stdout, encoding="utf-8")
            print(result.stdout)
        else:
            info("Using existing dupes.txt")
    else:
        info(f"Scanning for duplicates in: {target}")
        result = subprocess.run(["jdupes", "-r", "-S", str(target)],
                                capture_output=True, text=True)
        dupes.write_text(result.stdout, encoding="utf-8")
        print(result.stdout)

    if not dupes.exists() or dupes.stat().st_size == 0:
        success("No duplicates found.")
        return

    content = dupes.read_text(encoding="utf-8", errors="replace")
    group_count = sum(1 for line in content.splitlines() if line.startswith("./") or line.startswith("/"))

    if group_count == 0:
        success("No duplicates found.")
        return

    warn(f"Results saved to {DUPES_FILE}")
    print()

    if not confirm("Proceed with delete?"):
        warn("Aborted. No files deleted.")
        return

    print(f"  {C.BRED}Deleting duplicates...{C.RST}")
    deleted = jdupes_delete_loop(str(dupes))
    print()
    success(f"Done. {deleted} file(s) deleted.")


# ═══════════════════════════════════════════════════════════════════════════════
# 13. JCOMPARE — jdupes cross-directory comparison
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_jcompare(args):
    """Compare two directories for exact duplicates using jdupes, then delete."""

    section("JDUPES COMPARE")

    path1 = Path(args.path1).resolve()
    path2 = Path(args.path2).resolve()
    dupes = Path(DUPES_FILE)

    info(f"Dir 1 : {C.BWHITE}{path1}{C.RST}")
    info(f"Dir 2 : {C.BWHITE}{path2}{C.RST}")
    print()

    if dupes.exists():
        warn(f"{DUPES_FILE} already exists.")
        choice = input(f"  {C.BYELLOW}?{C.RST} Use existing file or rescan? (use/rescan): ").strip().lower()
        if choice == "rescan":
            info(f"Comparing:\n    {path1}\n    {path2}")
            result = subprocess.run(["jdupes", "-r", "-S", "-I", str(path1), str(path2)],
                                    capture_output=True, text=True)
            dupes.write_text(result.stdout, encoding="utf-8")
            print(result.stdout)
        else:
            info("Using existing dupes.txt")
    else:
        info(f"Comparing:\n    {path1}\n    {path2}")
        result = subprocess.run(["jdupes", "-r", "-S", "-I", str(path1), str(path2)],
                                capture_output=True, text=True)
        dupes.write_text(result.stdout, encoding="utf-8")
        print(result.stdout)

    if not dupes.exists() or dupes.stat().st_size == 0:
        success("No duplicates found between directories.")
        return

    content = dupes.read_text(encoding="utf-8", errors="replace")
    group_count = sum(1 for line in content.splitlines() if line.startswith("/"))

    if group_count == 0:
        success("No duplicates found between directories.")
        return

    warn(f"Results saved to {DUPES_FILE}")
    print()

    if not confirm("Proceed with delete?"):
        warn("Aborted. No files deleted.")
        return

    print(f"  {C.BRED}Deleting duplicates...{C.RST}")
    deleted = jdupes_delete_loop(str(dupes))
    print()
    success(f"Done. {deleted} file(s) deleted.")


# ═══════════════════════════════════════════════════════════════════════════════
# 14. MOVE — Pattern-based directory mover
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_move(args):
    """Move directories matching a pattern from source to destination."""

    section("PATTERN MOVE")

    source = Path(args.source).resolve()
    dest = Path(args.dest).resolve()
    pattern = args.pattern

    info(f"Pattern : {C.BYELLOW}{pattern}{C.RST}")
    info(f"Source  : {C.BWHITE}{source}{C.RST}")
    info(f"Dest    : {C.BWHITE}{dest}{C.RST}")
    print()

    if not source.is_dir():
        error(f"Source not found: {source}")
        return
    if not dest.is_dir():
        error(f"Destination not found: {dest}")
        return

    matches = [d for d in source.iterdir() if d.is_dir() and pattern.lower() in d.name.lower()]

    if not matches:
        warn(f"No directories matching '*{pattern}*' found in {source}")
        return

    info(f"Found {C.BWHITE}{len(matches)}{C.RST} matching directories:")
    print()
    for d in matches:
        print(f"  {C.BCYAN}{d.name}{C.RST}")
    print()

    if args.dry_run:
        success(f"DRY RUN: {len(matches)} directories would be moved.")
        return

    if not confirm(f"Move {len(matches)} directories to {dest}?"):
        warn("Aborted.")
        return

    moved = 0
    for d in matches:
        target = dest / d.name
        if target.exists():
            warn(f"SKIP (exists at dest): {d.name}")
            continue
        shutil.move(str(d), str(target))
        success(f"{d.name}")
        moved += 1

    print()
    success(f"Moved {moved} directories.")


# ═══════════════════════════════════════════════════════════════════════════════
# 15. EXTRACT — Batch audio extraction (mp4→mp3, webm→opus)
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_extract(args):
    """Batch extract audio from video files (mp4→mp3, webm→opus)."""

    section("BATCH AUDIO EXTRACT")

    target = Path(args.path).resolve()
    if not target.is_dir():
        error(f"Not a directory: {target}")
        return

    info(f"Path   : {C.BWHITE}{target}{C.RST}")
    info(f"Format : {C.BWHITE}{args.format or 'auto (mp4→mp3, webm→opus)'}{C.RST}")
    print()

    mp4s = list(target.glob("*.mp4"))
    webms = list(target.glob("*.webm"))

    format_filter = args.format
    if format_filter == "mp4":
        webms = []
    elif format_filter == "webm":
        mp4s = []

    info(f"MP4 files  : {C.BWHITE}{len(mp4s)}{C.RST}")
    info(f"WebM files : {C.BWHITE}{len(webms)}{C.RST}")
    print()

    if not mp4s and not webms:
        warn("No matching video files found.")
        return

    if not confirm("Extract audio from all found videos?"):
        warn("Cancelled.")
        return

    count = 0
    for vid in mp4s:
        out = vid.with_suffix(".mp3")
        print(f"  {C.BCYAN}{vid.name}{C.RST} → {C.BGREEN}{out.name}{C.RST}")
        try:
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-i", str(vid),
                           "-q:a", "0", str(out)],
                          capture_output=True, timeout=600)
            count += 1
        except Exception as e:
            error(f"  {vid.name}: {e}")

    for vid in webms:
        out = vid.with_suffix(".opus")
        print(f"  {C.BCYAN}{vid.name}{C.RST} → {C.BGREEN}{out.name}{C.RST}")
        try:
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-i", str(vid),
                           "-acodec", "copy", str(out)],
                          capture_output=True, timeout=600)
            count += 1
        except Exception as e:
            error(f"  {vid.name}: {e}")

    print()
    success(f"Extracted audio from {count} files.")


# ═══════════════════════════════════════════════════════════════════════════════
# 16. REMUX — Remux any video format to mp4
# ═══════════════════════════════════════════════════════════════════════════════

REMUX_EXTENSIONS = {".mkv", ".mov", ".avi", ".webm", ".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".wmv", ".flv"}

def cmd_remux(args):
    """Remux video files to mp4 (copy video, re-encode audio to AAC)."""

    section("REMUX TO MP4")

    target = Path(args.path).resolve()
    if not target.is_dir():
        error(f"Not a directory: {target}")
        return

    info(f"Path : {C.BWHITE}{target}{C.RST}")
    print()

    files = [f for f in target.iterdir()
             if f.is_file() and f.suffix.lower() in REMUX_EXTENSIONS]

    if args.format:
        ext = f".{args.format.lstrip('.')}"
        files = [f for f in files if f.suffix.lower() == ext]

    if not files:
        warn("No remuxable video files found.")
        return

    candidates = []
    for f in files:
        out = f.with_suffix(".mp4")
        if out.exists() and not args.overwrite:
            warn(f"SKIP (exists): {out.name}")
            continue
        candidates.append((f, out))

    if not candidates:
        success("All files already have mp4 versions.")
        return

    for src, dst in candidates:
        print(f"  {C.DIM}{src.name}{C.RST}")
        print(f"  {C.BGREEN}→ {dst.name}{C.RST}\n")

    print(f"  {C.BWHITE}{len(candidates)}{C.RST} file(s) to remux.\n")

    if not confirm("Start remux?"):
        warn("Cancelled.")
        return

    done = 0
    for src, dst in candidates:
        print(f"  {C.BCYAN}Remuxing:{C.RST} {src.name}...", end="", flush=True)
        try:
            cmd = ["ffmpeg", "-y" if args.overwrite else "-n", "-nostdin",
                   "-i", str(src), "-c:v", "copy", "-c:a", "aac",
                   "-b:a", "192k", "-movflags", "+faststart", str(dst)]
            result = subprocess.run(cmd, capture_output=True, timeout=1800)
            if result.returncode == 0:
                print(f" {C.BGREEN}✓{C.RST}")
                done += 1
            else:
                print(f" {C.BRED}✗{C.RST}")
                stderr = result.stderr.decode(errors="replace")[-200:]
                if stderr:
                    dim(f"    {stderr}")
        except Exception as e:
            print(f" {C.BRED}✗{C.RST}")
            error(f"    {e}")

    print()
    success(f"Remuxed {done}/{len(candidates)} files to mp4.")


# ═══════════════════════════════════════════════════════════════════════════════
# 17. DOCKER — Docker/compose shortcuts
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_docker(args):
    """Docker/docker-compose management shortcuts."""

    section("DOCKER")

    action = args.action

    docker_actions = {
        "recreate":  ["docker-compose", "down", "&&", "docker-compose", "up", "-d"],
        "update":    ["docker-compose", "down", "&&", "docker-compose", "pull", "&&", "docker-compose", "up", "-d"],
        "stop":      ["docker-compose", "down"],
        "start":     ["docker-compose", "up", "-d"],
        "pull":      ["docker-compose", "pull"],
        "logs":      ["docker-compose", "logs", "--tail=50", "-f"],
        "ps":        ["docker", "ps", "--format", "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"],
        "restart":   ["docker", "restart"],
    }

    if action == "restart" and args.container:
        info(f"Action    : {C.BYELLOW}restart {args.container}{C.RST}")
        print()
        if not confirm(f"Restart container '{args.container}'?"):
            warn("Cancelled.")
            return
        result = subprocess.run(["docker", "restart", args.container])
        print()
        if result.returncode == 0:
            success(f"Restarted {args.container}.")
        else:
            error(f"docker restart exited with code {result.returncode}")
        return

    if action not in docker_actions:
        error(f"Unknown action: {action}")
        info(f"Available: {', '.join(sorted(docker_actions.keys()))}")
        return

    cmd_parts = docker_actions[action]
    info(f"Action  : {C.BYELLOW}{action}{C.RST}")

    if args.directory:
        info(f"Dir     : {C.BWHITE}{args.directory}{C.RST}")

    cmd_display = " ".join(cmd_parts)
    info(f"Command : {C.DIM}{cmd_display}{C.RST}")
    print()

    if action in ("ps", "logs"):
        if args.directory:
            subprocess.run(" ".join(cmd_parts), shell=True, cwd=args.directory)
        else:
            subprocess.run(" ".join(cmd_parts), shell=True)
        return

    if not confirm(f"Run '{action}'?"):
        warn("Cancelled.")
        return

    cwd = args.directory or None
    result = subprocess.run(" ".join(cmd_parts), shell=True, cwd=cwd)
    print()
    if result.returncode == 0:
        success(f"'{action}' complete.")
    else:
        error(f"Exited with code {result.returncode}")


# ═══════════════════════════════════════════════════════════════════════════════
# 18. COPY — rsync wrapper
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_copy(args):
    """Copy files/directories using rsync with progress."""

    section("RSYNC COPY")

    src = args.source
    dst = args.dest

    info(f"Source : {C.BWHITE}{src}{C.RST}")
    info(f"Dest   : {C.BWHITE}{dst}{C.RST}")
    print()

    cmd = ["rsync", "-aPh", src, dst]
    if args.sudo:
        cmd = ["sudo"] + cmd

    info(f"Command: {C.DIM}{' '.join(cmd)}{C.RST}")
    print()

    if not confirm("Start copy?"):
        warn("Cancelled.")
        return

    result = subprocess.run(cmd)
    print()
    if result.returncode == 0:
        success("Copy complete.")
    else:
        error(f"rsync exited with code {result.returncode}")


# ═══════════════════════════════════════════════════════════════════════════════
# 17. PERMIT — Fix permissions recursively
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_permit(args):
    """Set permissions to 755 recursively for dirs and files."""

    section("FIX PERMISSIONS")

    target = Path(args.path).resolve()
    if not target.exists():
        error(f"Path does not exist: {target}")
        return

    info(f"Path : {C.BWHITE}{target}{C.RST}")
    info(f"Mode : {C.BWHITE}755 (dirs + files){C.RST}")

    count = sum(1 for _ in target.rglob("*"))
    info(f"Items: {C.BWHITE}~{count}{C.RST}")
    print()

    if args.dry_run:
        success(f"DRY RUN: Would chmod 755 on ~{count} items.")
        return

    if not confirm(f"chmod 755 recursively on {target}?"):
        warn("Cancelled.")
        return

    applied = 0
    for item in target.rglob("*"):
        try:
            item.chmod(0o755)
            applied += 1
        except OSError:
            pass
    try:
        target.chmod(0o755)
    except OSError:
        pass

    print()
    success(f"Set 755 on {applied} items.")


# ═══════════════════════════════════════════════════════════════════════════════
# 18. OWN — Change ownership recursively
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_own(args):
    """Change ownership recursively (calls chown -R)."""

    section("CHANGE OWNERSHIP")

    target = Path(args.path).resolve()
    owner = args.owner

    info(f"Path  : {C.BWHITE}{target}{C.RST}")
    info(f"Owner : {C.BWHITE}{owner}{C.RST}")
    print()

    if not target.exists():
        error(f"Path does not exist: {target}")
        return

    if not confirm(f"chown -R {owner} {target}?"):
        warn("Cancelled.")
        return

    cmd = ["sudo", "chown", "-R", owner, str(target)]
    result = subprocess.run(cmd)
    print()
    if result.returncode == 0:
        success(f"Ownership changed to {owner}.")
    else:
        error(f"chown exited with code {result.returncode}")


# ═══════════════════════════════════════════════════════════════════════════════
# 19. SIZE — Disk usage sorted
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_size(args):
    """Show disk usage of items in a directory, sorted by size (uses du)."""

    section("DISK USAGE")

    target = Path(args.path).resolve()
    if not target.is_dir():
        error(f"Not a directory: {target}")
        return

    info(f"Path : {C.BWHITE}{target}{C.RST}")
    print()

    try:
        result = subprocess.run(
            ["du", "--max-depth=1", "-b", str(target)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            error(f"du failed: {result.stderr.strip()}")
            return
    except FileNotFoundError:
        error("'du' command not found.")
        return
    except subprocess.TimeoutExpired:
        error("du timed out (120s). Directory may be too deep or on a slow mount.")
        return

    items = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        try:
            size = int(parts[0])
        except ValueError:
            continue
        entry_path = Path(parts[1])
        if entry_path.resolve() == target:
            continue
        name = entry_path.name
        is_dir = entry_path.is_dir()
        items.append((name, size, is_dir))

    items.sort(key=lambda x: -x[1])
    limit = args.top or len(items)

    total = 0
    for name, size, is_dir in items[:limit]:
        total += size
        gib = size / (1024**3)
        if gib >= 1:
            sz_str = f"{gib:.2f} GiB"
        else:
            sz_str = f"{size / (1024**2):.1f} MiB"
        icon = f"{C.BCYAN}📁{C.RST}" if is_dir else f"{C.BWHITE}📄{C.RST}"
        bar_len = min(int(gib * 2), 40) if gib >= 1 else max(1, int(size / (1024**2) / 100))
        bar = f"{C.BMAGENTA}{'█' * bar_len}{C.RST}"
        print(f"  {icon} {sz_str:>12}  {bar}  {name}")

    print(f"\n  {C.DIM}Total: {fmt_size(total)} ({len(items)} items){C.RST}")


# ═══════════════════════════════════════════════════════════════════════════════
# 22. CLIP — Copy file contents to clipboard (WSL)
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_clip(args):
    """Copy file contents to Windows clipboard via clip.exe (WSL)."""

    section("CLIPBOARD COPY")

    target = Path(args.path).resolve()
    if not target.is_file():
        error(f"Not a file: {target}")
        return

    info(f"File : {C.BWHITE}{target}{C.RST}")
    info(f"Size : {C.BWHITE}{fmt_size(target.stat().st_size)}{C.RST}")
    print()

    try:
        with open(target, "rb") as f:
            result = subprocess.run(["clip.exe"], stdin=f, timeout=30)
        if result.returncode == 0:
            success(f"Copied {target.name} to clipboard.")
        else:
            error(f"clip.exe exited with code {result.returncode}")
    except FileNotFoundError:
        error("clip.exe not found. This command requires WSL (Windows Subsystem for Linux).")
    except Exception as e:
        error(f"Failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE MENU
# ═══════════════════════════════════════════════════════════════════════════════

COMMANDS = [
    ("clean",    "Clean filenames (strip junk, normalize)",       cmd_clean),
    ("dirname",  "Rename files to match parent directory",        cmd_dirname),
    ("restag",   "Add resolution tags (4k–8k) via ffprobe",      cmd_restag),
    ("probe",    "Full video metadata report (anonymized)",       cmd_probe),
    ("hq",       "HQ peer-bitrate analysis + tagging",           cmd_hq),
    ("uhdtag",   "Tag large files (>=40 GiB) with UHD HQ",      cmd_uhdtag),
    ("audio",    "Extract audio tracks from video files",        cmd_audio),
    ("names",    "Find recurring name patterns in filenames",    cmd_names),
    ("dupes",    "Find duplicate/similar filenames",             cmd_dupes),
    ("compare",  "Compare 2+ dirs for cross-duplicates",         cmd_compare),
    ("dedup",    "Interactive duplicate deletion from report",   cmd_dedup),
    ("jclean",   "jdupes scan + delete dupes (single dir)",     cmd_jclean),
    ("jcompare", "jdupes compare two dirs + delete dupes",      cmd_jcompare),
    ("move",     "Move dirs matching a pattern",                cmd_move),
    ("extract",  "Batch audio extract (mp4→mp3, webm→opus)",   cmd_extract),
    ("remux",    "Remux any video → mp4 (copy vid, AAC audio)", cmd_remux),
    ("docker",   "Docker/compose shortcuts",                    cmd_docker),
    ("copy",     "rsync copy with progress",                    cmd_copy),
    ("permit",   "Fix permissions (chmod 755 recursive)",       cmd_permit),
    ("own",      "Change ownership (chown -R)",                 cmd_own),
    ("size",     "Disk usage sorted by size",                   cmd_size),
    ("clip",     "Copy file to clipboard (WSL clip.exe)",      cmd_clip),
]


MENU_PROMPTS = {
    "clean":    {"args": ["path"], "opts": [("-r", "--recursive", "Include subdirectories?")]},
    "dirname":  {"args": ["path"], "opts": []},
    "restag":   {"args": ["path"], "opts": [("--apply", "Apply renames after probe?")]},
    "probe":    {"args": ["path"], "opts": []},
    "hq":       {"args": ["path"], "opts": [("--apply-hq", "Apply saved HQ plan (no reprobe)?")]},
    "uhdtag":   {"args": ["path"], "opts": [("-r", "--recursive", "Include subdirectories?")]},
    "audio":    {"args": ["path"], "opts": [("-k", "--keyword", "Filter by keyword in filename (or Enter for all):")]},
    "names":    {"args": ["path"], "opts": [("-r", "--recursive", "Include subdirectories?")]},
    "dupes":    {"args": ["paths+"], "opts": []},
    "compare":  {"args": ["dirs+"], "opts": []},
    "dedup":    {"args": ["report"], "opts": [("--auto", "Auto-delete smaller duplicates?")]},
    "jclean":   {"args": ["path"], "opts": []},
    "jcompare": {"args": ["path1", "path2"], "opts": []},
    "move":     {"args": ["pattern", "source", "dest"], "opts": []},
    "extract":  {"args": ["path"], "opts": [("-f", "--format", "Filter by format (mp4/webm) or Enter for all:")]},
    "remux":    {"args": ["path"], "opts": [("-f", "--format", "Only remux this format (e.g. mkv, mov) or Enter for all:"), ("--overwrite", "Overwrite existing mp4 files?")]},
    "docker":   {"args": ["action"], "opts": [("-C", "--directory", "Docker compose directory (or Enter to skip):")]},
    "copy":     {"args": ["source", "dest"], "opts": [("--sudo", "Run with sudo?")]},
    "permit":   {"args": ["path"], "opts": []},
    "own":      {"args": ["owner", "path"], "opts": []},
    "size":     {"args": ["path"], "opts": [("-n", "--top", "How many results to show? (Enter for all):")]},
    "clip":     {"args": ["path"], "opts": []},
}


def show_menu():
    """Print the command list."""
    print(f"\n  {C.BWHITE}{C.BOLD}Select a tool:{C.RST}\n")
    for i, (name, desc, _) in enumerate(COMMANDS, 1):
        num_color = C.BMAGENTA if i % 2 == 0 else C.BCYAN
        print(f"  {num_color}{C.BOLD}[{i:2d}]{C.RST}  {C.BWHITE}{name:<10}{C.RST} {C.DIM}{desc}{C.RST}")
    print(f"\n  {C.DIM}[c] Chain    [q] Quit    [h] Help{C.RST}\n")


def run_command(cmd_name, argv_parts):
    """Parse args and dispatch a command. Returns when done."""
    sys.argv = argv_parts
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {nm: fn for nm, _, fn in COMMANDS}
    if args.command in dispatch:
        dispatch[args.command](args)


def _run_chain():
    """Run multiple commands in sequence on a shared or per-command path."""
    print(f"\n  {C.BWHITE}{C.BOLD}COMMAND CHAIN{C.RST}")
    print(f"  {C.DIM}Pick commands to run in order. Type 'done' when finished picking.{C.RST}\n")

    # Show numbered list
    for i, (name, desc, _) in enumerate(COMMANDS, 1):
        num_color = C.BMAGENTA if i % 2 == 0 else C.BCYAN
        print(f"  {num_color}{C.BOLD}[{i:2d}]{C.RST}  {C.BWHITE}{name:<10}{C.RST} {C.DIM}{desc}{C.RST}")
    print()

    chain = []
    while True:
        try:
            pick = input(f"  {C.BYELLOW}+{C.RST} Add command (number/name, or 'done'): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return
        if pick in ("done", "d", ""):
            break
        cmd_name = None
        if pick.isdigit() and 1 <= int(pick) <= len(COMMANDS):
            cmd_name = COMMANDS[int(pick) - 1][0]
        else:
            for nm, _, _ in COMMANDS:
                if pick == nm:
                    cmd_name = nm
                    break
        if cmd_name:
            chain.append(cmd_name)
            print(f"    {C.BGREEN}#{len(chain)}{C.RST} {cmd_name}")
        else:
            error(f"    Unknown: {pick}")

    if not chain:
        warn("  No commands selected.")
        return

    # Show chain summary
    print(f"\n  {C.BCYAN}{C.BOLD}Chain ({len(chain)} commands):{C.RST}")
    for i, cmd in enumerate(chain, 1):
        print(f"    {C.BYELLOW}{i}.{C.RST} {cmd}")
    print()

    # Ask for shared path
    print(f"  {C.DIM}Use a shared path for all commands, or enter per-command.{C.RST}")
    shared = input_path(f"  {C.BCYAN}Shared path{C.RST} (Enter to set per-command): ", show_history=True).strip()
    print()

    # Execute each command in order
    for i, cmd_name in enumerate(chain, 1):
        print(f"  {C.BWHITE}{C.BOLD}[{i}/{len(chain)}] {cmd_name}{C.RST}")
        print(f"  {C.DIM}{'─' * 40}{C.RST}")

        prompts = MENU_PROMPTS.get(cmd_name, {"args": [], "opts": []})
        argv_parts = [sys.argv[0], cmd_name]
        aborted = False

        for arg_name in prompts["args"]:
            is_path = arg_name.rstrip("+") in {"path", "path1", "path2", "source", "dest", "paths", "dirs", "report"}

            if is_path and shared:
                if arg_name.endswith("+"):
                    argv_parts.extend(shared.split())
                else:
                    argv_parts.append(shared)
                print(f"    {C.DIM}Using: {shared}{C.RST}")
            elif arg_name.endswith("+"):
                label = arg_name.rstrip("+")
                val = input_path(f"    {C.BCYAN}{label}{C.RST}: ").strip()
                if not val:
                    val = "."
                argv_parts.extend(val.split())
            else:
                default = "." if arg_name in ("path", "source", "dest") else ""
                hint = f" [{default}]" if default else ""
                if is_path:
                    val = input_path(f"    {C.BCYAN}{arg_name}{C.RST}{hint}: ").strip()
                else:
                    val = input(f"    {C.BCYAN}{arg_name}{C.RST}{hint}: ").strip()
                if not val and default:
                    val = default
                if not val:
                    error(f"    {arg_name} is required — skipping {cmd_name}.")
                    aborted = True
                    break
                argv_parts.append(val)

        if aborted:
            continue

        # Ask options
        for opt_tuple in prompts["opts"]:
            if len(opt_tuple) == 3:
                flag_or_short, flag, label = opt_tuple
                actual_flag = flag if (flag_or_short.startswith("-") and not flag_or_short.startswith("--")) else flag_or_short
            elif len(opt_tuple) == 2:
                flag, label = opt_tuple
                actual_flag = flag
            else:
                actual_flag = opt_tuple[0]
                label = opt_tuple[0]

            is_value_opt = label.endswith(":")
            if is_value_opt:
                pfn = input_path if "directory" in label.lower() else input
                val = pfn(f"    {C.BCYAN}{label}{C.RST} ").strip()
                if val:
                    argv_parts.extend([actual_flag, val])
            else:
                yn = input(f"    {C.BCYAN}{label}{C.RST} [y/N]: ").strip().lower()
                if yn in ("y", "yes"):
                    argv_parts.append(actual_flag)

        print()
        run_command(cmd_name, argv_parts)
        print()

    print(f"\n  {C.BGREEN}{C.BOLD}Chain complete ({len(chain)} commands).{C.RST}\n")


def interactive_menu():
    setup_path_completer()
    banner()
    show_menu()

    while True:
        try:
            choice = input(f"  {C.BMAGENTA}>{C.RST} ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            gg()

        if choice in ("q", "quit", "exit"):
            gg()
        if choice in ("h", "help"):
            print(f"\n  {C.BCYAN}Usage:{C.RST} python3 sweet_life.py <command> [options]")
            print(f"  {C.BCYAN}Help:{C.RST}  python3 sweet_life.py <command> --help\n")
            continue
        if choice == "m":
            show_menu()
            continue
        if choice in ("c", "chain"):
            _run_chain()
            show_menu()
            continue

        selected = None
        if choice.isdigit() and 1 <= int(choice) <= len(COMMANDS):
            selected = COMMANDS[int(choice) - 1][0]
        else:
            for nm, _, _ in COMMANDS:
                if choice == nm:
                    selected = nm
                    break

        if not selected:
            error(f"Invalid choice. Enter a number 1–{len(COMMANDS)}, command name, or 'q'.")
            continue

        print(f"\n  {C.BGREEN}→{C.RST} {C.BOLD}{selected}{C.RST}\n")

        prompts = MENU_PROMPTS.get(selected, {"args": [], "opts": []})
        argv_parts = [sys.argv[0], selected]
        aborted = False

        first_path_shown = False
        for arg_name in prompts["args"]:
            is_path = arg_name.rstrip("+") in {"path", "path1", "path2", "source", "dest", "paths", "dirs", "report"}

            if arg_name.endswith("+"):
                label = arg_name.rstrip("+")
                if is_path and not first_path_shown:
                    first_path_shown = True
                    val = input_path(f"  {C.BCYAN}{label}{C.RST} (space-separated, or . for cwd): ", show_history=True).strip()
                elif is_path:
                    val = input_path(f"  {C.BCYAN}{label}{C.RST} (space-separated, or . for cwd): ").strip()
                else:
                    val = input(f"  {C.BCYAN}{label}{C.RST} (space-separated, or . for cwd): ").strip()
                if not val:
                    val = "."
                argv_parts.extend(val.split())
            else:
                default = "." if arg_name in ("path", "source", "dest") else ""
                hint = f" [{default}]" if default else ""
                if is_path and not first_path_shown:
                    first_path_shown = True
                    val = input_path(f"  {C.BCYAN}{arg_name}{C.RST}{hint}: ", show_history=True).strip()
                elif is_path:
                    val = input_path(f"  {C.BCYAN}{arg_name}{C.RST}{hint}: ").strip()
                else:
                    val = input(f"  {C.BCYAN}{arg_name}{C.RST}{hint}: ").strip()
                if not val and default:
                    val = default
                if not val:
                    error(f"  {arg_name} is required.")
                    aborted = True
                    break
                argv_parts.append(val)

        if aborted:
            print()
            continue

        for opt_tuple in prompts["opts"]:
            if len(opt_tuple) == 3:
                flag_or_short, flag, label = opt_tuple
                if flag_or_short.startswith("-") and not flag_or_short.startswith("--"):
                    actual_flag = flag
                else:
                    actual_flag = flag_or_short
                    flag = flag_or_short
            elif len(opt_tuple) == 2:
                flag, label = opt_tuple
                actual_flag = flag
            else:
                actual_flag = opt_tuple[0]
                label = opt_tuple[0]

            is_value_opt = label.endswith(":")
            if is_value_opt:
                pfn = input_path if "directory" in label.lower() else input
                val = pfn(f"  {C.BCYAN}{label}{C.RST} ").strip()
                if val:
                    argv_parts.extend([actual_flag, val])
            else:
                yn = input(f"  {C.BCYAN}{label}{C.RST} [y/N]: ").strip().lower()
                if yn in ("y", "yes"):
                    argv_parts.append(actual_flag)

        print()

        # Run the command (it has its own internal confirmations)
        run_command(selected, argv_parts)

        # Return to menu
        print(f"\n  {C.DIM}{'─' * 50}{C.RST}")
        print(f"  {C.DIM}Done. Press Enter for menu or 'q' to quit.{C.RST}")
        try:
            back = input(f"  {C.BMAGENTA}>{C.RST} ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            gg()
        if back in ("q", "quit", "exit"):
            gg()
        show_menu()


# ═══════════════════════════════════════════════════════════════════════════════
# ARGPARSE SETUP
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser():
    parser = argparse.ArgumentParser(
        prog="sweet_life",
        description=f"{C.BOLD}Sweet Life{C.RST} — All-in-one system management suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{C.BCYAN}Examples:{C.RST}
  sweet_life.py clean /mnt/pool/videos --dry-run -r
  sweet_life.py dirname /mnt/pool/sorted --dry-run
  sweet_life.py restag /mnt/pool/videos --apply
  sweet_life.py probe /mnt/pool/videos
  sweet_life.py hq /mnt/pool/videos
  sweet_life.py hq /mnt/pool/videos --apply-hq
  sweet_life.py uhdtag /mnt/pool/videos -r
  sweet_life.py audio /mnt/pool/videos --keyword "vacation"
  sweet_life.py names /mnt/pool/videos -r
  sweet_life.py dupes /mnt/disk1/media /mnt/disk2/media
  sweet_life.py compare /mnt/disk1 /mnt/disk2 /mnt/disk3
  sweet_life.py dedup filename_duplicate_report.txt --auto
  sweet_life.py jclean /mnt/pool/media
  sweet_life.py jcompare /mnt/disk1/media /mnt/disk2/media
  sweet_life.py move "vacation" /mnt/pool/dump /mnt/pool/sorted
  sweet_life.py extract /mnt/pool/videos -f mp4
  sweet_life.py remux /mnt/pool/videos
  sweet_life.py remux /mnt/pool/videos -f mkv
  sweet_life.py docker recreate -C /opt/stacks/plex
  sweet_life.py docker restart plex
  sweet_life.py docker ps
  sweet_life.py copy /mnt/disk1/file.mp4 /mnt/disk2/
  sweet_life.py permit /mnt/pool/media
  sweet_life.py own joe:joe /mnt/pool/media
  sweet_life.py size /mnt/pool -n 20
"""
    )
    sub = parser.add_subparsers(dest="command")

    # clean
    p = sub.add_parser("clean", help="Clean filenames (strip junk, normalize spacing)")
    p.add_argument("path", nargs="?", default=".", help="Target directory (default: .)")
    p.add_argument("-d", "--dry-run", action="store_true", help="Preview only, don't rename")
    p.add_argument("-r", "--recursive", action="store_true", help="Process subdirectories")

    # dirname
    p = sub.add_parser("dirname", help="Rename files to match parent directory name")
    p.add_argument("path", nargs="?", default=".", help="Target directory (default: .)")
    p.add_argument("-d", "--dry-run", action="store_true", help="Preview only")

    # restag
    p = sub.add_parser("restag", help="Add resolution tags (4k–8k) via ffprobe")
    p.add_argument("path", help="Video directory to scan")
    p.add_argument("-d", "--dry-run", action="store_true", help="Show counts only, no ffprobe")
    p.add_argument("--apply", action="store_true", help="Actually rename files after probe")

    # probe
    p = sub.add_parser("probe", help="Anonymized video metadata report via ffprobe")
    p.add_argument("path", help="Video directory to scan")
    p.add_argument("-o", "--output", help="Output report path (default: video_probe_report.txt)")
    p.add_argument("-d", "--dry-run", action="store_true", help="Show count only, no ffprobe")

    # hq
    p = sub.add_parser("hq", help="HQ peer-bitrate analysis + tagging (2-stage)")
    p.add_argument("path", help="Video directory to scan")
    p.add_argument("-d", "--dry-run", action="store_true", help="Filename analysis only, no ffprobe")
    p.add_argument("--apply-hq", action="store_true", help="Apply saved HQ_RENAME_PLAN.json (no reprobe)")

    # uhdtag
    p = sub.add_parser("uhdtag", help="Tag files >= 40 GiB with 'UHD HQ'")
    p.add_argument("path", nargs="?", default=".", help="Target path (default: .)")
    p.add_argument("-d", "--dry-run", action="store_true", help="Preview only")
    p.add_argument("-r", "--recursive", action="store_true", help="Include subdirectories")

    # audio
    p = sub.add_parser("audio", help="Extract audio tracks from video files")
    p.add_argument("path", nargs="?", default=".", help="Directory with videos (default: .)")
    p.add_argument("-k", "--keyword", help="Only process files containing this keyword")

    # names
    p = sub.add_parser("names", help="Find recurring name patterns in filenames")
    p.add_argument("path", nargs="?", default=".", help="Directory to scan (default: .)")
    p.add_argument("-r", "--recursive", action="store_true", help="Scan subdirectories")

    # dupes
    p = sub.add_parser("dupes", help="Find duplicate/similar filenames")
    p.add_argument("paths", nargs="+", help="Directories to scan")
    p.add_argument("-o", "--output", default="filename_duplicate_report.txt", help="Report output path")

    # compare
    p = sub.add_parser("compare", help="Compare 2+ directories for cross-duplicates")
    p.add_argument("dirs", nargs="+", help="Directories to compare (need 2+)")
    p.add_argument("-o", "--output", default="filename_duplicate_report.txt", help="Report output path")

    # dedup
    p = sub.add_parser("dedup", help="Smart duplicate deletion (duration + date filtering)")
    p.add_argument("report", nargs="?", default="filename_duplicate_report.txt", help="Report file")
    p.add_argument("--auto", action="store_true", help="Auto-delete smaller dupes (keep largest, filter by duration/date)")
    p.add_argument("--debug", action="store_true", help="Show filtering diagnostics")

    # jclean
    p = sub.add_parser("jclean", help="jdupes scan + delete duplicates (single directory)")
    p.add_argument("path", nargs="?", default=".", help="Directory to scan (default: .)")

    # jcompare
    p = sub.add_parser("jcompare", help="jdupes compare two directories + delete duplicates")
    p.add_argument("path1", help="First directory")
    p.add_argument("path2", help="Second directory")

    # move
    p = sub.add_parser("move", help="Move directories matching a pattern")
    p.add_argument("pattern", help="Search pattern (matches directory names)")
    p.add_argument("source", help="Source directory to search in")
    p.add_argument("dest", help="Destination directory")
    p.add_argument("-d", "--dry-run", action="store_true", help="Preview only")

    # extract
    p = sub.add_parser("extract", help="Batch audio extract (mp4→mp3, webm→opus)")
    p.add_argument("path", nargs="?", default=".", help="Directory with videos (default: .)")
    p.add_argument("-f", "--format", choices=["mp4", "webm"], help="Only process this format")

    # remux
    p = sub.add_parser("remux", help="Remux any video format to mp4 (copy video, AAC audio)")
    p.add_argument("path", nargs="?", default=".", help="Directory with videos (default: .)")
    p.add_argument("-f", "--format", help="Only remux this format (e.g. mkv, mov, avi)")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing mp4 files")

    # docker
    p = sub.add_parser("docker", help="Docker/compose shortcuts")
    p.add_argument("action", choices=["recreate", "update", "stop", "start", "pull", "logs", "ps", "restart"],
                   help="Action: recreate|update|stop|start|pull|logs|ps|restart")
    p.add_argument("container", nargs="?", help="Container name (for restart)")
    p.add_argument("-C", "--directory", help="docker-compose directory")

    # copy
    p = sub.add_parser("copy", help="rsync copy with progress (rsync -aPh)")
    p.add_argument("source", help="Source path")
    p.add_argument("dest", help="Destination path")
    p.add_argument("--sudo", action="store_true", help="Run with sudo")

    # permit
    p = sub.add_parser("permit", help="Fix permissions (chmod 755 recursive)")
    p.add_argument("path", nargs="?", default=".", help="Target path (default: .)")
    p.add_argument("-d", "--dry-run", action="store_true", help="Preview only")

    # own
    p = sub.add_parser("own", help="Change ownership recursively (chown -R)")
    p.add_argument("owner", help="Owner (e.g. joe:joe)")
    p.add_argument("path", nargs="?", default=".", help="Target path (default: .)")

    # size
    p = sub.add_parser("size", help="Disk usage sorted by size")
    p.add_argument("path", nargs="?", default=".", help="Directory to analyze (default: .)")
    p.add_argument("-n", "--top", type=int, help="Show only top N items")

    # clip
    p = sub.add_parser("clip", help="Copy file contents to clipboard (WSL clip.exe)")
    p.add_argument("path", help="File to copy to clipboard")

    return parser


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        interactive_menu()
        return

    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "clean": cmd_clean,
        "dirname": cmd_dirname,
        "restag": cmd_restag,
        "probe": cmd_probe,
        "hq": cmd_hq,
        "uhdtag": cmd_uhdtag,
        "audio": cmd_audio,
        "names": cmd_names,
        "dupes": cmd_dupes,
        "compare": cmd_compare,
        "dedup": cmd_dedup,
        "jclean": cmd_jclean,
        "jcompare": cmd_jcompare,
        "move": cmd_move,
        "extract": cmd_extract,
        "remux": cmd_remux,
        "docker": cmd_docker,
        "copy": cmd_copy,
        "permit": cmd_permit,
        "own": cmd_own,
        "size": cmd_size,
        "clip": cmd_clip,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
