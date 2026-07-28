import argparse
import time
from pathlib import Path


def clean_generated(directory: Path, *, older_than_days: int, dry_run: bool = True) -> list[Path]:
    cutoff = time.time() - older_than_days * 86_400
    removed: list[Path] = []
    if not directory.exists():
        return removed
    for path in directory.glob("*.docx"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            removed.append(path)
            if not dry_run:
                path.unlink()
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean generated JobPilot artifacts.")
    parser.add_argument("--directory", type=Path, default=Path("data/generated"))
    parser.add_argument("--older-than-days", type=int, default=30)
    parser.add_argument("--apply", action="store_true", help="Delete files; default is a dry run.")
    args = parser.parse_args()
    if args.older_than_days < 0:
        parser.error("--older-than-days must be non-negative")
    removed = clean_generated(
        args.directory,
        older_than_days=args.older_than_days,
        dry_run=not args.apply,
    )
    action = "removed" if args.apply else "would remove"
    print(f"{action} {len(removed)} generated artifact(s)")
    for path in removed:
        print(path)


if __name__ == "__main__":
    main()
