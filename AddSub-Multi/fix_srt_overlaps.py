import re
import sys
from pathlib import Path

TIME_RE = re.compile(r"^(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})(.*)$")
MIN_DURATION_MS = 250
MAX_OVERLAP_FALLBACK_MS = 15 * 1000
AD_PATTERNS = (
    "opensubtitles.org",
    "osdb.link",
    "vip member",
    "official yify movies site",
    "yts.bz",
    "yify",
    "yts.mx",
    "yts.ag",
    "yts.am",
    "download yify",
    "get subtitles",
    "iptv",
    "www.",
    "http://",
    "https://",
)


def read_text(path):
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    if data[:200].count(b"\x00") > 20:
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def to_ms(value):
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return ((int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000) + int(millis)


def from_ms(value):
    value = max(0, value)
    millis = value % 1000
    value //= 1000
    seconds = value % 60
    value //= 60
    minutes = value % 60
    hours = value // 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def fix_file(path):
    lines = read_text(path).splitlines()
    blocks = re.split(r"\r?\n\s*\r?\n", "\n".join(lines).strip())
    kept_blocks = []
    removed_ads = 0

    for block in blocks:
        block_text = block.lower()
        if any(pattern in block_text for pattern in AD_PATTERNS):
            removed_ads += 1
        else:
            kept_blocks.append(block)

    if removed_ads:
        if not kept_blocks:
            path.unlink()
            print(f"[Fix] Removed ad-only subtitle: {path.name}")
            return
        lines = "\n\n".join(kept_blocks).splitlines()

    timing_indexes = []
    timings = {}

    for index, line in enumerate(lines):
        match = TIME_RE.match(line.strip())
        if match:
            timing_indexes.append(index)
            timings[index] = [to_ms(match.group(1)), to_ms(match.group(2)), match.group(3)]

    changed = removed_ads > 0
    for position, index in enumerate(timing_indexes[:-1]):
        start, end, suffix = timings[index]
        next_start = timings[timing_indexes[position + 1]][0]
        if end > next_start:
            if next_start > start + MIN_DURATION_MS:
                timings[index][1] = next_start - 1
            else:
                timings[index][1] = start + MAX_OVERLAP_FALLBACK_MS
            changed = True
        elif end <= start:
            timings[index][1] = start + MIN_DURATION_MS
            changed = True

    if timing_indexes:
        last_index = timing_indexes[-1]
        start, end, suffix = timings[last_index]
        if end <= start:
            timings[last_index][1] = start + MIN_DURATION_MS
            changed = True

    if not changed:
        return

    for index, (start, end, suffix) in timings.items():
        lines[index] = f"{from_ms(start)} --> {from_ms(end)}{suffix}"

    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    print(f"[Fix] Subtitle overlaps fixed: {path.name}")


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python fix_srt_overlaps.py <subtitle_folder> [exclude_filename]")
        return 1

    folder = Path(sys.argv[1])
    excluded = sys.argv[2].lower() if len(sys.argv) == 3 else ""
    for path in folder.glob("*.srt"):
        if excluded and path.name.lower() == excluded:
            print(f"[Fix] Skipped protected subtitle: {path.name}")
            continue
        fix_file(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
