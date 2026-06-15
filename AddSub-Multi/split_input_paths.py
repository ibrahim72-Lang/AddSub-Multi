import re
import sys
from pathlib import Path

EXTENSIONS = (
    "mp4", "mkv", "avi", "m4v", "mov", "wmv", "flv", "webm", "mpg", "mpeg", "ts", "m2ts",
    "srt", "ass", "ssa", "vtt", "sub", "idx", "smi", "sami", "sbv", "dfxp", "ttml", "stl", "sup", "usf", "txt",
)
EXT_PATTERN = "|".join(re.escape(ext) for ext in EXTENSIONS)
PATH_RE = re.compile(
    rf'''(?ix)
    (?:(?:"(?P<quoted>[^"]+\.(?:{EXT_PATTERN}))")|(?P<plain>.*?\.(?:{EXT_PATTERN})))
    (?=\s+(?:[A-Za-z]:\\|\\\\)|$)
    '''
)


def split_paths(raw):
    raw = raw.strip()
    if not raw:
        return []
    quoted_paths = [part.strip() for part in re.findall(r'"([^"]+)"', raw) if part.strip()]
    if len(quoted_paths) > 1:
        return quoted_paths
    separated_paths = [part.strip().strip('"') for part in re.split(r'\s+(?=(?:[A-Za-z]:\\|\\\\))', raw) if part.strip()]
    if len(separated_paths) > 1:
        return separated_paths
    if Path(raw.strip(' "')).exists():
        return [raw.strip(' "')]
    paths = []
    for match in PATH_RE.finditer(raw):
        value = match.group("quoted") or match.group("plain")
        value = value.strip().strip('"')
        if value:
            paths.append(value)
    return paths or [raw.strip(' "')]


def main():
    if len(sys.argv) < 2:
        return 0
    for path in split_paths(" ".join(sys.argv[1:])):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
