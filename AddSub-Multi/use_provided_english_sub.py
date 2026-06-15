import re
import sys
from pathlib import Path

TIME_RE = re.compile(r"\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}")
ENGLISH_WORD_RE = re.compile(r"\b(the|and|you|that|have|for|not|with|this|but|are|was|what|your|all|can|there|from|they|will|would|about|get|just|know|like|come|go|see|now|then|here|one|out|who|why|how|yes|yeah|no|right|please|tell|look|think|want|need|time|man|good|bad|sorry)\b", re.IGNORECASE)
LANGS = {
    "en": ("en", "eng", "english"),
    "fr": ("fr", "fre", "fra", "french"),
    "de": ("de", "ger", "deu", "german"),
    "es": ("es", "spa", "spanish"),
    "ru": ("ru", "rus", "russian"),
    "zh": ("zh", "chi", "zho", "chinese"),
    "ar": ("ar", "ara", "arabic"),
    "it": ("it", "ita", "italian"),
}
LANG_NAMES = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "zh": "Chinese",
    "ar": "Arabic",
    "it": "Italian",
}
COMMENTARY_PATTERNS = (
    "subtitle by",
    "subtitles by",
    "translated by",
    "sync by",
    "resync by",
    "captioned by",
    "opensubtitles.org",
    "osdb.link",
    "vip member",
    "official yify movies site",
    "yify",
    "yts.bz",
    "yts.mx",
    "yts.ag",
    "yts.am",
    "get subtitles",
    "iptv",
)
LEADING_AD_PATTERNS = COMMENTARY_PATTERNS + (
    "www.",
    "http://",
    "https://",
)
MIN_FILLED_RATIO = 0.60
MIN_ENGLISH_WORDS = 25
MIN_ENGLISH_WORD_RATIO = 0.04


def read_text(path):
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    if data[:200].count(b"\x00") > 20:
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def strip_leading_ad_blocks(text):
    blocks = re.split(r"(\r?\n\s*\r?\n)", text.strip())
    rebuilt = []
    ad_prefix = True

    for index in range(0, len(blocks), 2):
        block = blocks[index]
        separator = blocks[index + 1] if index + 1 < len(blocks) else "\n\n"
        lowered = block.lower()
        if ad_prefix and any(pattern in lowered for pattern in LEADING_AD_PATTERNS):
            continue
        ad_prefix = False
        rebuilt.append(block)
        rebuilt.append(separator)

    return "".join(rebuilt).strip() + "\n"


def subtitle_score(path):
    text = strip_leading_ad_blocks(read_text(path))
    lowered = text.lower()
    ad_hits = sum(1 for pattern in COMMENTARY_PATTERNS if pattern in lowered)
    blocks = re.split(r"\r?\n\s*\r?\n", text.strip())
    cue_count = 0
    filled_count = 0

    for block in blocks:
        lines = block.splitlines()
        time_index = next((i for i, line in enumerate(lines) if TIME_RE.search(line)), None)
        if time_index is None:
            continue
        cue_count += 1
        body = "\n".join(line.strip() for line in lines[time_index + 1:] if line.strip())
        if body:
            filled_count += 1

    filled_ratio = filled_count / cue_count if cue_count else 0
    usable = cue_count > 0 and filled_ratio >= MIN_FILLED_RATIO
    if ad_hits and filled_count <= 5:
        usable = False
    return usable, cue_count, filled_count, filled_ratio


def looks_like_english(path):
    text = strip_leading_ad_blocks(read_text(path))
    words = re.findall(r"[A-Za-z']+", text)
    english_words = ENGLISH_WORD_RE.findall(text)
    english_ratio = len(english_words) / len(words) if words else 0
    return len(english_words) >= MIN_ENGLISH_WORDS and english_ratio >= MIN_ENGLISH_WORD_RATIO


# Noise tokens that appear in filenames but are not part of the title
NOISE_TOKEN_RE = re.compile(
    r"\b(1080p|720p|480p|2160p|4k|bluray|blu\ ray|bdrip|brrip|webrip|web\ dl|webdl|"
    r"hdtv|dvdrip|dvdscr|hdrip|x264|x265|h264|h265|avc|hevc|xvid|divx|"
    r"sub|subs|extended|theatrical|remastered|repack|proper|limited|internal|"
    r"readnfo|dubbed|multi|retail|unrated|directors\ cut|dc)\b",
    re.IGNORECASE,
)


def normalize_name(name):
    """Lowercase, replace separators with spaces, strip noise tokens."""
    n = re.sub(r"[._\-]", " ", name.lower())
    n = NOISE_TOKEN_RE.sub(" ", n)
    n = re.sub(r"[\[\]()]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def extract_core(name):
    """Return (title_words, year) from a normalized filename."""
    n = normalize_name(name)
    year_match = re.search(r"\b(19|20)\d{2}\b", n)
    year = year_match.group() if year_match else None
    title = re.sub(r"\b(19|20)\d{2}\b.*", "", n).strip() if year else n
    return set(title.split()), year


def fuzzy_matches_video(sub_base, video_name):
    """Return True if sub_base is a plausible match for video_name.

    Uses title-word overlap + year check instead of exact substring matching,
    so subtitles named differently (e.g. Twisted_2004_1080p vs Twisted [2004])
    are correctly identified as the same film.
    """
    v_words, v_year = extract_core(video_name)
    s_words, s_year = extract_core(sub_base)
    # Year mismatch is a hard disqualifier when both are present
    if v_year and s_year and v_year != s_year:
        return False
    if not v_words or not s_words:
        return False
    overlap = v_words & s_words
    v_coverage = len(overlap) / len(v_words)
    s_coverage = len(overlap) / len(s_words)
    return v_coverage >= 0.8 or s_coverage >= 0.8


def strip_lang_tokens(base):
    result = base
    for aliases in LANGS.values():
        for alias in aliases:
            result = re.sub(rf"(^|[._\-\s]){re.escape(alias)}($|[._\-\s])", " ", result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result.replace(".", " ").replace("_", " ").replace("-", " ")).strip()


def has_lang_token(path, lang):
    value = path.stem.lower()
    return any(re.search(rf"(^|[._\-\s]){re.escape(alias)}($|[._\-\s])", value) for alias in LANGS[lang])


def has_dual_lang_tokens(path, lang):
    return lang != "en" and has_lang_token(path, lang) and has_lang_token(path, "en")


def subtitle_matches_video(path, name):
    return fuzzy_matches_video(strip_lang_tokens(path.stem), name)


def add_subtitle_path(paths, path, name):
    if path.suffix.lower() == ".srt" and subtitle_matches_video(path, name) and path not in paths:
        paths.append(path)


def subtitle_paths(folder, input_list, name):
    paths = []
    for path in folder.glob("*.srt"):
        add_subtitle_path(paths, path, name)
    if input_list and input_list.exists():
        for line in input_list.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            path = Path(line.strip())
            if path.is_file():
                add_subtitle_path(paths, path, name)
            elif path.is_dir():
                for sub_path in path.glob("*.srt"):
                    add_subtitle_path(paths, sub_path, name)
    return paths


def candidate_paths(paths, name, lang):
    candidates = []
    for path in paths:
        base = path.stem
        base_without_lang = strip_lang_tokens(base)
        matches_video = fuzzy_matches_video(base_without_lang, name)
        explicitly_lang = has_lang_token(path, lang)
        plain_match = matches_video and normalize_name(base_without_lang) == normalize_name(name)
        english_same_title = lang == "en" and matches_video and looks_like_english(path)
        if matches_video and (explicitly_lang or (plain_match and lang == "en" and looks_like_english(path)) or english_same_title) and not has_dual_lang_tokens(path, lang):
            candidates.append(path)
    return sorted(candidates)


def dual_candidate_paths(paths, name, lang):
    candidates = []
    for path in paths:
        base = path.stem
        base_without_lang = strip_lang_tokens(base)
        matches_video = fuzzy_matches_video(base_without_lang, name)
        if matches_video and has_dual_lang_tokens(path, lang):
            candidates.append(path)
    return sorted(candidates)


def main():
    if len(sys.argv) not in (4, 5):
        print("Usage: python use_provided_english_sub.py <video_folder> <output_folder> <video_name> [input_list]")
        return 1

    folder = Path(sys.argv[1])
    output = Path(sys.argv[2])
    name = sys.argv[3]
    input_list = Path(sys.argv[4]) if len(sys.argv) == 5 else None
    paths = subtitle_paths(folder, input_list, name)
    output.mkdir(parents=True, exist_ok=True)
    provided = []
    provided_dual = []
    provided_sources = []
    if paths:
        shown = ", ".join(path.name for path in paths[:10])
        if len(paths) > 10:
            shown += f", ... ({len(paths)} matching candidates total)"
        print("[Provided] Matching subtitle candidates found: " + shown)
    else:
        print("[Provided] No .srt subtitle candidates found in video folder or input list.")

    for lang in LANGS:
        best = None
        best_score = None
        for path in candidate_paths(paths, name, lang):
            usable, cues, filled_cues, filled_ratio = subtitle_score(path)
            if usable:
                score = (filled_ratio, filled_cues, cues)
                if best is None or score > best_score:
                    best = path
                    best_score = score
            else:
                print(f"[Provided] Rejected incomplete {LANG_NAMES[lang]} subtitle: {path.name} ({filled_ratio:.0%} timestamps filled)")

        if best:
            target = output / f"{name}.{lang}.srt"
            target.write_text(strip_leading_ad_blocks(read_text(best)), encoding="utf-8")
            provided.append(lang)
            provided_sources.append(f"{best.resolve()}\t{target.name}")
            print(f"[Provided] Using complete provided {LANG_NAMES[lang]} subtitle: {best.name}")

    for lang in LANGS:
        if lang == "en":
            continue
        best = None
        best_score = None
        for path in dual_candidate_paths(paths, name, lang):
            usable, cues, filled_cues, filled_ratio = subtitle_score(path)
            if usable:
                score = (filled_ratio, filled_cues, cues)
                if best is None or score > best_score:
                    best = path
                    best_score = score
            else:
                print(f"[Provided] Rejected incomplete {LANG_NAMES[lang]} + English subtitle: {path.name} ({filled_ratio:.0%} timestamps filled)")

        if best:
            target = output / f"{name}.{lang}-en.srt"
            target.write_text(strip_leading_ad_blocks(read_text(best)), encoding="utf-8")
            provided_dual.append(f"{lang}-en")
            provided_sources.append(f"{best.resolve()}\t{target.name}")
            print(f"[Provided] Using complete provided {LANG_NAMES[lang]} + English subtitle: {best.name}")

    (output / "provided_langs.txt").write_text(" ".join(provided), encoding="utf-8")
    (output / "provided_dual_langs.txt").write_text(" ".join(provided_dual), encoding="utf-8")
    (output / "provided_sources.txt").write_text("\n".join(provided_sources), encoding="utf-8")
    if not provided and not provided_dual:
        print("[Provided] No complete provided subtitles found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
