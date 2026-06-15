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
ENGLISH_WORD_RE = re.compile(r"\b(the|and|you|that|this|with|have|for|not|are|but|what|all|can|was|will|from|they|your|there|one|about|know|when|who|would|could|should|because|just|like|get|got|out|now|here|were|been|going|think|want|need|good|yes|no)\b", re.IGNORECASE)
MIN_CUES = 25
MIN_MULTILINE_RATIO = 0.35
MIN_ENGLISH_WORDS = 80
MIN_ENGLISH_CUE_RATIO = 0.25
MIN_EXTRACTED_CUES = 25
MIN_EXTRACTED_TEXT_CHARS = 200
PRIMARY_COLOR = "#FFFF00"
SECONDARY_COLOR = "#FFFFFF"
SECONDARY_SIZE = "80%"
TARGET_SCRIPT_RE = {
    "zh": re.compile(r"[\u4e00-\u9fff]"),
    "ar": re.compile(r"[\u0600-\u06ff]"),
    "ru": re.compile(r"[\u0400-\u04ff]"),
}
REJECTED_DIR_NAME = "RejectedStandaloneSubs"


def read_entries(path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    entries = []
    lines = [line.strip() for line in text.splitlines()]
    index = 0
    while index < len(lines):
        if not TIME_RE.search(lines[index]):
            index += 1
            continue
        time_line = lines[index]
        index += 1
        body = []
        while index < len(lines):
            if TIME_RE.search(lines[index]):
                break
            if lines[index].isdigit():
                next_index = index + 1
                while next_index < len(lines) and not lines[next_index]:
                    next_index += 1
                if next_index < len(lines) and TIME_RE.search(lines[next_index]):
                    break
            if lines[index]:
                body.append(lines[index])
            index += 1
        if body:
            entries.append({"time": time_line, "body": body})
    return entries


def looks_like_downloaded_dual(path):
    entries = read_entries(path)
    if len(entries) < MIN_CUES:
        return False

    multiline = sum(1 for entry in entries if len(entry["body"]) >= 2)
    english_cues = 0
    english_words = 0
    for entry in entries:
        cue_text = " ".join(entry["body"])
        matches = ENGLISH_WORD_RE.findall(cue_text)
        if matches:
            english_cues += 1
            english_words += len(matches)

    multiline_ratio = multiline / len(entries)
    english_cue_ratio = english_cues / len(entries)
    return multiline_ratio >= MIN_MULTILINE_RATIO and english_cue_ratio >= MIN_ENGLISH_CUE_RATIO and english_words >= MIN_ENGLISH_WORDS


def format_downloaded_dual(path):
    entries = read_entries(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for index, entry in enumerate(entries, 1):
            body = entry["body"]
            primary = body[0]
            secondary = " ".join(body[1:])
            handle.write(f"{index}\r\n")
            handle.write(f"{entry['time']}\r\n")
            if secondary:
                handle.write(f"<font color=\"{PRIMARY_COLOR}\">{primary}</font>\r\n")
                handle.write(f"<font color=\"{SECONDARY_COLOR}\" size=\"{SECONDARY_SIZE}\">{secondary}</font>\r\n\r\n")
            else:
                handle.write(f"<font color=\"{PRIMARY_COLOR}\">{primary}</font>\r\n\r\n")


def strip_tags(text):
    return re.sub(r"<[^>]+>", "", text)


def extract_target_standalone(path, lang):
    script_re = TARGET_SCRIPT_RE.get(lang)
    if not script_re:
        return False

    entries = read_entries(path)
    extracted = []
    for entry in entries:
        target_lines = [strip_tags(line).strip() for line in entry["body"] if script_re.search(strip_tags(line))]
        target_lines = [line for line in target_lines if line]
        if target_lines:
            extracted.append({"time": entry["time"], "body": target_lines})

    text_chars = sum(len(strip_tags(" ".join(entry["body"])).strip()) for entry in extracted)
    if len(extracted) < MIN_EXTRACTED_CUES or text_chars < MIN_EXTRACTED_TEXT_CHARS:
        return False

    with path.open("w", encoding="utf-8", newline="") as handle:
        for index, entry in enumerate(extracted, 1):
            handle.write(f"{index}\r\n")
            handle.write(f"{entry['time']}\r\n")
            handle.write("\r\n".join(entry["body"]))
            handle.write("\r\n\r\n")
    return True


def preserve_rejected_standalone(path, lang, reason):
    if not path.exists():
        return
    rejected_dir = path.parent / REJECTED_DIR_NAME
    rejected_dir.mkdir(exist_ok=True)
    target = rejected_dir / f"{path.stem}.rejected-{lang}.srt"
    counter = 1
    while target.exists():
        target = rejected_dir / f"{path.stem}.rejected-{lang}.{counter}.srt"
        counter += 1
    target.write_bytes(path.read_bytes())
    print(f"[Dual] Debug copy saved for rejected {LANG_NAMES[lang]} standalone ({reason}): {target}")


def extract_standalone_from_existing_duals(folder, name):
    created = 0
    for lang in TARGET_SCRIPT_RE:
        standalone = folder / f"{name}.{lang}.srt"
        if standalone.exists():
            continue
        dual = folder / f"{name}.{lang}-en.srt"
        if not dual.exists():
            continue
        standalone.write_bytes(dual.read_bytes())
        if extract_target_standalone(standalone, lang):
            print(f"[Dual] Extracted standalone {LANG_NAMES[lang]} from existing {LANG_NAMES[lang]}-English dual: {standalone.name}")
            created += 1
        else:
            preserve_rejected_standalone(standalone, lang, "existing dual standalone extraction failed")
            standalone.unlink(missing_ok=True)
            print(f"[Dual] Existing {LANG_NAMES[lang]}-English dual could not produce a safe standalone {LANG_NAMES[lang]} subtitle.")
    return created


def main():
    if len(sys.argv) not in (3, 4):
        print("Usage: python detect_downloaded_dual_subs.py <subtitle_folder> <video_name> [--clean-script-standalone-only|--extract-standalone-from-existing-duals]")
        return 1

    folder = Path(sys.argv[1])
    name = sys.argv[2]
    clean_script_standalone_only = len(sys.argv) == 4 and sys.argv[3] == "--clean-script-standalone-only"
    extract_from_existing_duals = len(sys.argv) == 4 and sys.argv[3] == "--extract-standalone-from-existing-duals"
    detected = 0

    if extract_from_existing_duals:
        extract_standalone_from_existing_duals(folder, name)
        return 0

    for lang in LANGS:
        for path in sorted(folder.glob(f"{name}*.{lang}.srt")):
            dual_path = path.with_name(f"{path.stem}-en{path.suffix}")
            if clean_script_standalone_only:
                if lang in TARGET_SCRIPT_RE and dual_path.exists():
                    if extract_target_standalone(path, lang):
                        print(f"[Dual] Clean standalone {LANG_NAMES[lang]} was preserved alongside existing dual: {path.name}")
                    else:
                        preserve_rejected_standalone(path, lang, "clean extraction failed")
                        path.unlink()
                        print(f"[Dual] Removed separate {LANG_NAMES[lang]} subtitle because clean standalone could not be safely extracted: {path.name}")
                continue
            if dual_path.exists():
                if lang in TARGET_SCRIPT_RE and extract_target_standalone(path, lang):
                    print(f"[Dual] Clean standalone {LANG_NAMES[lang]} was preserved alongside existing dual: {path.name}")
                else:
                    if lang in TARGET_SCRIPT_RE:
                        preserve_rejected_standalone(path, lang, "existing dual cleanup failed")
                    path.unlink()
                    print(f"[Dual] Removed separate {LANG_NAMES[lang]} subtitle because dual {LANG_NAMES[lang]} + English already exists: {dual_path.name}")
                continue
            if looks_like_downloaded_dual(path):
                format_downloaded_dual(path)
                if lang in TARGET_SCRIPT_RE:
                    dual_path.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8", newline="")
                    if extract_target_standalone(path, lang):
                        print(f"[Dual] Downloaded subtitle already contains {LANG_NAMES[lang]} + English; clean standalone {LANG_NAMES[lang]} was preserved: {path.name}")
                    else:
                        preserve_rejected_standalone(path, lang, "dual source extraction failed")
                        path.unlink()
                        print(f"[Dual] Downloaded subtitle already contains {LANG_NAMES[lang]} + English; standalone {LANG_NAMES[lang]} could not be safely extracted.")
                else:
                    path.replace(dual_path)
                print(f"[Dual] Downloaded subtitle already contains {LANG_NAMES[lang]} + English: {dual_path.name}")
                detected += 1
            elif lang in TARGET_SCRIPT_RE and extract_target_standalone(path, lang):
                print(f"[Dual] Clean standalone {LANG_NAMES[lang]} subtitle prepared: {path.name}")

    if detected == 0:
        print("[Dual] No downloaded dual-language subtitles detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
