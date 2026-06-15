import subprocess
import sys
from pathlib import Path


def ffmpeg_can_read(path):
    test_output = path.with_suffix(path.suffix + ".test.mkv")
    if test_output.exists():
        test_output.unlink()
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-map", "0:s:0", "-c:s", "srt", str(test_output)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    readable = result.returncode == 0 and test_output.exists()
    if test_output.exists():
        test_output.unlink()
    return readable, result.stderr.strip()


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python validate_subs_ffmpeg.py <subtitle_folder> [exclude_filename]")
        return 1

    folder = Path(sys.argv[1])
    excluded = sys.argv[2].lower() if len(sys.argv) == 3 else ""
    removed = 0
    checked = 0

    for path in folder.glob("*.srt"):
        if excluded and path.name.lower() == excluded:
            print(f"[Validate] Skipped protected subtitle: {path.name}")
            continue
        checked += 1
        readable, error = ffmpeg_can_read(path)
        if not readable:
            path.unlink()
            removed += 1
            print(f"[Validate] Removed FFmpeg-unreadable subtitle: {path.name}")
            if error:
                print(f"[Validate] FFmpeg reason: {error.splitlines()[-1]}")

    print(f"[Validate] FFmpeg-readable subtitle files: {checked - removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
