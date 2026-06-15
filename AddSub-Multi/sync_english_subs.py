import shutil
import subprocess
import sys
from pathlib import Path


def find_english_subtitles(folder, name):
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.name.lower().startswith(name.lower())
        and path.name.lower().endswith(".en.srt")
    )


def has_readable_srt_cues(path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return "-->" in text and any(line.strip() for line in text.splitlines() if "-->" not in line)


def main():
    if len(sys.argv) != 4:
        print("Usage: python sync_english_subs.py <video_file> <subtitle_folder> <video_name>")
        return 1

    if not shutil.which("ffsubsync"):
        print("[Sync] ffsubsync not found. Install with: pip install ffsubsync")
        return 0

    video_file = Path(sys.argv[1])
    folder = Path(sys.argv[2])
    name = sys.argv[3]

    english_subtitles = find_english_subtitles(folder, name)
    if not english_subtitles:
        print("[Sync] English subtitle not found. Skipping English sync.")
        return 0

    synced = 0
    for subtitle in english_subtitles:
        synced_path = subtitle.with_name(f"{subtitle.stem}.synced{subtitle.suffix}")
        command = [
            "ffsubsync",
            str(video_file),
            "-i",
            str(subtitle),
            "-o",
            str(synced_path),
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode == 0 and synced_path.exists() and synced_path.stat().st_size > 0 and has_readable_srt_cues(synced_path):
            synced_path.replace(subtitle)
            print(f"[Sync] English subtitle synced: {subtitle.name}")
            synced += 1
        else:
            if synced_path.exists():
                synced_path.unlink()
            print(f"[Sync] English sync failed, keeping original: {subtitle.name}")

    print(f"[Sync] English subtitles synced: {synced}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
