import re
import sys
from pathlib import Path

LANGS = ["fr", "de", "es", "ru", "zh", "ar", "it"]
LANG_NAMES = {
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "zh": "Chinese",
    "ar": "Arabic",
    "it": "Italian",
}
TIME_RE = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})")
PRIMARY_COLOR = "#FFFF00"
SECONDARY_COLOR = "#FFFFFF"
SECONDARY_SIZE = "80%"
MIN_MATCH_RATIO = 0.60
MAX_MIDPOINT_DISTANCE_MS = 1250
MAX_DURATION_DIFF_RATIO = 0.02
MAX_DURATION_DIFF_MS = 120000
MIN_CUE_COUNT = 10
MIN_FILLED_RATIO = 0.70
MIN_TEXT_CHARS = 100
MAX_COLLISION_SCORE = 0.60
TARGET_SCRIPT_RE = {
    "zh": re.compile(r"[\u4e00-\u9fff]"),
    "ar": re.compile(r"[\u0600-\u06ff]"),
    "ru": re.compile(r"[\u0400-\u04ff]"),
}
COMMON_SHORT_LINES = {
    "ok",
    "okay",
    "yes",
    "no",
    "yeah",
    "hey",
    "hi",
    "hello",
    "bye",
    "thanks",
    "thank you",
}


def parse_time(value):
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return ((int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000) + int(millis)


def clean_text(lines):
    return "\n".join(line.strip() for line in lines if line.strip())


def read_text(path):
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    if data[:200].count(b"\x00") > 20:
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def read_srt(path):
    text = read_text(path)
    blocks = re.split(r"\r?\n\s*\r?\n", text.strip())
    entries = []
    for block in blocks:
        lines = block.splitlines()
        time_index = next((i for i, line in enumerate(lines) if TIME_RE.search(line)), None)
        if time_index is None:
            continue
        match = TIME_RE.search(lines[time_index])
        start = parse_time(match.group(1))
        end = parse_time(match.group(2))
        body = clean_text(lines[time_index + 1:])
        if body:
            entries.append({"start": start, "end": end, "time": lines[time_index].strip(), "text": body})
    return entries


def overlap(a, b):
    return max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))


def best_english_match(entry, english_entries):
    best = None
    best_score = 0
    midpoint = (entry["start"] + entry["end"]) // 2
    for candidate in english_entries:
        score = overlap(entry, candidate)
        candidate_midpoint = (candidate["start"] + candidate["end"]) // 2
        if score == 0 and abs(midpoint - candidate_midpoint) <= MAX_MIDPOINT_DISTANCE_MS:
            score = 1
        if score > best_score:
            best = candidate
            best_score = score
    return best


def find_subtitle(folder, name, lang):
    exact = folder / f"{name}.{lang}.srt"
    if exact.exists():
        return exact

    pattern = re.compile(rf"^{re.escape(name)}\.{re.escape(lang)}\.\d+\.srt$", re.IGNORECASE)
    matches = sorted(
        path
        for path in folder.iterdir()
        if path.is_file()
        and pattern.match(path.name)
    )
    return matches[0] if matches else None


def write_srt(path, entries):
    with path.open("w", encoding="utf-8", newline="") as handle:
        for index, entry in enumerate(entries, 1):
            # Normalise any embedded newlines in text to \r\n before writing
            text = entry["text"].replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
            handle.write(f"{index}\r\n")
            handle.write(f"{entry['time']}\r\n")
            handle.write(f"{text}\r\n\r\n")


def strip_tags(value):
    return re.sub(r"<[^>]+>", " ", value)


def normalize_line(value):
    value = strip_tags(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def meaningful_lines(entries):
    lines = set()
    for entry in entries:
        for line in entry["text"].splitlines():
            normalized = normalize_line(line)
            if len(normalized) < 12:
                continue
            if normalized in COMMON_SHORT_LINES:
                continue
            if not re.search(r"[a-z]", normalized):
                continue
            lines.add(normalized)
    return lines


def subtitle_stats(entries):
    cue_count = len(entries)
    filled_entries = [entry for entry in entries if entry["text"].strip()]
    filled_count = len(filled_entries)
    text_chars = sum(len(strip_tags(entry["text"]).strip()) for entry in filled_entries)
    if entries:
        first_start = min(entry["start"] for entry in entries)
        last_end = max(entry["end"] for entry in entries)
    else:
        first_start = 0
        last_end = 0
    return {
        "cue_count": cue_count,
        "filled_count": filled_count,
        "filled_ratio": filled_count / cue_count if cue_count else 0,
        "text_chars": text_chars,
        "duration_ms": max(0, last_end - first_start),
    }


def passes_density(stats):
    return (
        stats["cue_count"] >= MIN_CUE_COUNT
        and stats["filled_ratio"] >= MIN_FILLED_RATIO
        and stats["text_chars"] >= MIN_TEXT_CHARS
    )


def duration_incompatible(base_stats, target_stats):
    base_duration = base_stats["duration_ms"]
    target_duration = target_stats["duration_ms"]
    if base_duration <= 0 or target_duration <= 0:
        return True, 1.0, abs(base_duration - target_duration)
    diff = abs(base_duration - target_duration)
    ratio = diff / base_duration
    return ratio > MAX_DURATION_DIFF_RATIO and diff > MAX_DURATION_DIFF_MS, ratio, diff


def content_collision_score(english_entries, target_entries):
    english_lines = meaningful_lines(english_entries)
    if not english_lines:
        return 0
    target_lines = meaningful_lines(target_entries)
    collisions = english_lines & target_lines
    return len(collisions) / len(english_lines)


def validate_pair(english_entries, target_entries, lang_name):
    english_stats = subtitle_stats(english_entries)
    target_stats = subtitle_stats(target_entries)
    if not passes_density(english_stats):
        return False, "English subtitle appears empty or malformed"
    if not passes_density(target_stats):
        return False, f"{lang_name} subtitle appears empty or malformed"
    incompatible, ratio, diff = duration_incompatible(english_stats, target_stats)
    if incompatible:
        return False, f"incompatible timing: difference {ratio:.1%} ({diff / 1000:.0f}s)"
    collision = content_collision_score(english_entries, target_entries)
    if collision > MAX_COLLISION_SCORE:
        return False, f"target already overlaps heavily with English ({collision:.0%})"
    return True, "OK"


def target_language_entries(entries, lang):
    script_re = TARGET_SCRIPT_RE.get(lang)
    if not script_re:
        return entries
    return [entry for entry in entries if script_re.search(strip_tags(entry["text"]))]


def main():
    if len(sys.argv) != 3:
        print("Usage: python combine_dual_subs.py <subtitle_folder> <video_name>")
        return 1

    folder = Path(sys.argv[1])
    name = sys.argv[2]
    english_path = find_subtitle(folder, name, "en")
    if not english_path:
        print("[Warning] English subtitle not found. Dual subtitles skipped.")
        return 0

    english_entries = read_srt(english_path)
    if not english_entries:
        print("[Warning] English subtitle could not be read. Dual subtitles skipped.")
        return 0

    created = 0
    for lang in LANGS:
        output_path = folder / f"{name}.{lang}-en.srt"
        if output_path.exists():
            print(f"[Dual] Using provided {LANG_NAMES[lang]} + English")
            created += 1
            continue

        source_path = find_subtitle(folder, name, lang)
        if not source_path:
            continue

        source_entries = target_language_entries(read_srt(source_path), lang)
        valid_pair, reason = validate_pair(english_entries, source_entries, LANG_NAMES[lang])
        if not valid_pair:
            print(f"[Dual] Skipped {LANG_NAMES[lang]} + English. {reason}.")
            continue

        combined_entries = []
        matched_entries = 0
        for entry in source_entries:
            english = best_english_match(entry, english_entries)
            text = entry["text"]
            if english:
                matched_entries += 1
                text = f"<font color=\"{PRIMARY_COLOR}\">{entry['text']}</font>\n<font color=\"{SECONDARY_COLOR}\" size=\"{SECONDARY_SIZE}\">{english['text']}</font>"
            combined_entries.append({"time": entry["time"], "text": text})

        match_ratio = matched_entries / len(source_entries) if source_entries else 0
        if match_ratio < MIN_MATCH_RATIO:
            print(f"[Dual] Skipped {LANG_NAMES[lang]} + English. English timing match too low: {match_ratio:.0%}")
            continue

        if combined_entries:
            write_srt(output_path, combined_entries)
            print(f"[Dual] Created {LANG_NAMES[lang]} + English")
            created += 1

    if created == 0:
        print("[Dual] No dual subtitles created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
