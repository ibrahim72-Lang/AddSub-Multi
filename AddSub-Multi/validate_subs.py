import re
import subprocess
import sys
from pathlib import Path

TIME_RE = re.compile(r"\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}")
TIME_CAPTURE_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2}),(\d{3})")
AD_PATTERNS = (
    "opensubtitles.org",
    "opensubtitles.com",
    "open subtitles",
    "osdb.link",
    "downloaded from",
    "download subtitles",
    "subtitle downloaded",
    "subtitles downloaded",
    "subtitles by",
    "provided by",
    "uploaded by",
    "synced by",
    "sync by",
    "corrected by",
    "official yify movies site",
    "yify",
    "yts.bz",
    "yify subtitles",
    "yts.mx",
    "yts.am",
    "psarips.com",
    "vip member",
    "get subtitles",
    "iptv",
    "http://",
    "https://",
)
STARTUP_AD_WINDOW_MS = 5 * 60 * 1000
MAX_STARTUP_AD_CUES = 5
MAX_STARTUP_AD_RATIO = 0.05
MIN_REAL_CUES = 5
MIN_MOVIE_CUES = 100
MIN_VALID_BLOCK_RATIO = 0.60
MIN_VIDEO_COVERAGE_RATIO = 0.40
MAX_VIDEO_COVERAGE_RATIO = 1.20


def read_text(path):
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    if data[:200].count(b"\x00") > 20:
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def parse_srt_blocks(text):
    parsed = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = block.splitlines()
        time_index = next((i for i, line in enumerate(lines) if TIME_RE.search(line)), None)
        if time_index is None:
            continue
        match = TIME_CAPTURE_RE.search(lines[time_index])
        if not match:
            continue
        start_ms = parse_time_ms(match.groups()[:4])
        body_lines = lines[time_index + 1:]
        parsed.append((start_ms, lines[time_index], body_lines))
    return parsed


def is_startup_ad_text(text):
    lowered = re.sub(r"\s+", " ", text.lower()).strip()
    if any(pattern in lowered for pattern in AD_PATTERNS):
        return True
    if "www." in lowered and any(source in lowered for source in ("subtitle", "yify", "yts", "rarbg", "psa", "rip")):
        return True
    return False


def rebuild_srt(blocks):
    rebuilt = []
    for index, (_, time_line, body_lines) in enumerate(blocks, 1):
        body = [line.rstrip() for line in body_lines if line.strip()]
        if body:
            rebuilt.append("\n".join([str(index), time_line, *body]))
    return "\n\n".join(rebuilt)


def strip_startup_ad_blocks(text):
    blocks = parse_srt_blocks(text)
    if not blocks:
        return text, 0
    max_remove = min(MAX_STARTUP_AD_CUES, max(1, int(len(blocks) * MAX_STARTUP_AD_RATIO)))
    kept = []
    removed_ads = 0
    for block in blocks:
        start_ms, _, body_lines = block
        if start_ms > STARTUP_AD_WINDOW_MS:
            kept.append(block)
            continue
        body = "\n".join(body_lines)
        if removed_ads < max_remove and is_startup_ad_text(body):
            removed_ads += 1
            continue
        kept.append(block)
    if not removed_ads:
        return text, 0
    return rebuild_srt(kept), removed_ads


def clean_blocks(text):
    blocks = re.split(r"\r?\n\s*\r?\n", text.strip())
    cue_count = 0
    valid_count = 0
    kept_blocks = []

    for block in blocks:
        lines = block.splitlines()
        time_index = next((i for i, line in enumerate(lines) if TIME_RE.search(line)), None)
        if time_index is None:
            continue
        cue_count += 1
        body = "\n".join(line.strip() for line in lines[time_index + 1:] if line.strip())
        if body:
            valid_count += 1
            kept_blocks.append(block)

    return cue_count, valid_count, "\n\n".join(kept_blocks)


def parse_time_ms(parts):
    hours, minutes, seconds, millis = (int(part) for part in parts)
    return ((hours * 3600 + minutes * 60 + seconds) * 1000) + millis


def subtitle_span_ms(text):
    starts = []
    ends = []
    for match in TIME_CAPTURE_RE.finditer(text):
        starts.append(parse_time_ms(match.groups()[:4]))
        ends.append(parse_time_ms(match.groups()[4:]))
    if not starts or not ends:
        return 0
    return max(ends) - min(starts)


def video_duration_ms(video_path):
    if not video_path:
        return 0
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        return int(float(result.stdout.strip()) * 1000)
    except ValueError:
        return 0


def remove_provided_manifest_entry(path):
    manifest = path.parent / "provided_sources.txt"
    if not manifest.exists():
        return
    lines = manifest.read_text(encoding="utf-8", errors="replace").splitlines()
    kept = []
    for line in lines:
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[1] == path.name:
            continue
        kept.append(line)
    manifest.write_text("\n".join(kept), encoding="utf-8")


def remove_subtitle(path):
    path.unlink()
    remove_provided_manifest_entry(path)


def has_runtime_mismatch(path, text, duration_ms):
    if duration_ms <= 0:
        return False
    span = subtitle_span_ms(text)
    if span <= 0:
        return False
    coverage = span / duration_ms
    if coverage < MIN_VIDEO_COVERAGE_RATIO or coverage > MAX_VIDEO_COVERAGE_RATIO:
        print(f"[Validate] Removed unreadable subtitle: {path.name} (runtime coverage {coverage:.0%})")
        return True
    return False


def validate_file(path, duration_ms=0):
    text = read_text(path)
    text, removed_ads = strip_startup_ad_blocks(text)
    cue_count, valid_count, cleaned_text = clean_blocks(text)

    if removed_ads and cue_count <= MIN_REAL_CUES:
        remove_subtitle(path)
        print(f"[Validate] Removed ad/bad subtitle: {path.name}")
        return False

    if cue_count == 0:
        remove_subtitle(path)
        print(f"[Validate] Removed unreadable subtitle: {path.name}")
        return False

    if duration_ms >= 30 * 60 * 1000 and cue_count < MIN_MOVIE_CUES:
        remove_subtitle(path)
        print(f"[Validate] Removed incomplete subtitle: {path.name} ({cue_count} cues)")
        return False

    valid_ratio = valid_count / cue_count
    if valid_ratio < MIN_VALID_BLOCK_RATIO:
        remove_subtitle(path)
        print(f"[Validate] Removed malformed subtitle: {path.name}")
        return False

    if cleaned_text and (removed_ads or valid_count != cue_count):
        path.write_text(cleaned_text.strip() + "\n", encoding="utf-8")
        text = cleaned_text
        if removed_ads:
            print(f"[Clean] Removed startup ad cues from {path.name}: {removed_ads}")

    if has_runtime_mismatch(path, text, duration_ms):
        remove_subtitle(path)
        return False
    return True


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python validate_subs.py <subtitle_folder> [video_path]")
        return 1

    folder = Path(sys.argv[1])
    duration_ms = video_duration_ms(Path(sys.argv[2])) if len(sys.argv) == 3 else 0
    valid = 0
    for path in folder.glob("*.srt"):
        if validate_file(path, duration_ms):
            valid += 1
    print(f"[Validate] Valid subtitle files: {valid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
