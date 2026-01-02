#!/usr/bin/env python3
"""
Standalone script to clean up old log files.

This script removes old log files to prevent unlimited growth.
Can be run manually or scheduled via cron.

Usage:
    python3 cleanup_logs.py                          # Use defaults (50MB, 10 files)
    python3 cleanup_logs.py --max-size 100           # Max 100MB total
    python3 cleanup_logs.py --max-files 20           # Keep max 20 files
    python3 cleanup_logs.py --max-size 100 --max-files 20
    python3 cleanup_logs.py --dry-run                # See what would be deleted

Scheduling with cron (daily at 3am):
    crontab -e
    # Add this line:
    0 3 * * * cd /home/ubuntu/GoldArb && python3 cleanup_logs.py >> logs/cleanup.log 2>&1
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime


def cleanup_old_logs(log_dir: str = "logs", max_total_size_mb: int = 50, max_files: int = 10, dry_run: bool = False):
    """
    Clean up old log files to prevent unlimited growth.

    Args:
        log_dir: Directory containing log files
        max_total_size_mb: Maximum total size in MB
        max_files: Maximum number of log files to keep
        dry_run: If True, only show what would be deleted without deleting
    """
    log_path = Path(log_dir)

    if not log_path.exists():
        print(f"ERROR: Log directory '{log_dir}' does not exist")
        return

    # Get all .json log files
    log_files = sorted(log_path.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

    if not log_files:
        print("No log files found")
        return

    # Calculate total size
    total_size = sum(f.stat().st_size for f in log_files)
    total_size_mb = total_size / (1024 * 1024)
    file_count = len(log_files)

    print("=" * 80)
    print(f"Log Cleanup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print(f"Directory: {log_path.absolute()}")
    print(f"Found {file_count} log files, total size: {total_size_mb:.2f}MB")
    print(f"Limits: max {max_total_size_mb}MB, max {max_files} files")
    if dry_run:
        print("DRY RUN MODE - No files will be deleted")
    print("=" * 80)
    print()

    # Determine which files to delete
    files_to_delete = []

    # Keep newest files up to max_files
    if file_count > max_files:
        files_to_delete.extend(log_files[max_files:])
        print(f"File count ({file_count}) exceeds limit ({max_files})")
        print(f"Will delete {len(log_files[max_files:])} old files")

    # If total size exceeds limit, delete oldest files until under limit
    if total_size_mb > max_total_size_mb:
        print(f"Total size ({total_size_mb:.2f}MB) exceeds limit ({max_total_size_mb}MB)")

        kept_files = log_files[:max_files] if file_count > max_files else log_files
        kept_size = sum(f.stat().st_size for f in kept_files) / (1024 * 1024)

        if kept_size > max_total_size_mb:
            # Even after keeping max_files, still over limit - delete more
            current_size = 0
            files_to_keep = []

            for f in log_files:
                file_size_mb = f.stat().st_size / (1024 * 1024)
                if current_size + file_size_mb <= max_total_size_mb:
                    files_to_keep.append(f)
                    current_size += file_size_mb
                else:
                    if f not in files_to_delete:
                        files_to_delete.append(f)

            print(f"Will delete {len(files_to_delete)} additional files to meet size limit")

    if not files_to_delete:
        print("✓ No cleanup needed - all limits met")
        print("=" * 80)
        return

    # Show what will be deleted
    print()
    print(f"Files to delete: {len(files_to_delete)}")
    print("-" * 80)

    delete_size_total = 0
    for f in files_to_delete:
        file_size_mb = f.stat().st_size / (1024 * 1024)
        delete_size_total += file_size_mb
        age_days = (datetime.now().timestamp() - f.stat().st_mtime) / 86400
        print(f"  {f.name:50s} {file_size_mb:>8.2f}MB (age: {age_days:>5.1f} days)")

    print("-" * 80)
    print(f"Total to delete: {delete_size_total:.2f}MB")
    print()

    if dry_run:
        print("DRY RUN - No files were deleted")
        print("=" * 80)
        return

    # Delete files
    deleted_count = 0
    deleted_size = 0

    for f in files_to_delete:
        try:
            file_size = f.stat().st_size
            f.unlink()
            deleted_count += 1
            deleted_size += file_size
        except Exception as e:
            print(f"ERROR: Failed to delete {f.name}: {e}")

    if deleted_count > 0:
        deleted_size_mb = deleted_size / (1024 * 1024)
        remaining_files = file_count - deleted_count
        remaining_size_mb = (total_size - deleted_size) / (1024 * 1024)

        print("=" * 80)
        print(f"✓ Deleted {deleted_count} files ({deleted_size_mb:.2f}MB)")
        print(f"✓ Remaining: {remaining_files} files ({remaining_size_mb:.2f}MB)")
        print("=" * 80)
    else:
        print("WARNING: No files were deleted")
        print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up old log files to prevent unlimited growth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 cleanup_logs.py                          # Use defaults (50MB, 10 files)
  python3 cleanup_logs.py --max-size 100           # Max 100MB total
  python3 cleanup_logs.py --max-files 20           # Keep max 20 files
  python3 cleanup_logs.py --dry-run                # See what would be deleted

Scheduling with cron (daily at 3am):
  crontab -e
  # Add this line:
  0 3 * * * cd /home/ubuntu/GoldArb && python3 cleanup_logs.py >> logs/cleanup.log 2>&1
        """
    )

    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs",
        help="Directory containing log files (default: logs)"
    )

    parser.add_argument(
        "--max-size",
        type=int,
        default=50,
        help="Maximum total size in MB (default: 50)"
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=10,
        help="Maximum number of log files to keep (default: 10)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )

    args = parser.parse_args()

    cleanup_old_logs(
        log_dir=args.log_dir,
        max_total_size_mb=args.max_size,
        max_files=args.max_files,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
