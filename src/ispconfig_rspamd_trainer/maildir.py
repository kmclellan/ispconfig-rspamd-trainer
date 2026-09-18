import os
from pathlib import Path


class UnsafeMaildirPath(ValueError):
    pass


def _under(base, path):
    base = os.path.realpath(str(base))
    path = os.path.realpath(str(path))
    return os.path.commonpath([base, path]) == base


def queue_files(maildir, relative_dirs, limit=None):
    base = Path(maildir)
    result = []
    for relative in relative_dirs:
        directory = base / relative
        if not _under(base, directory):
            raise UnsafeMaildirPath("queue path escapes Maildir")
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir(), key=lambda p: p.name):
            # Ignore symlinks and non-regular files. Maildir messages are files.
            if entry.is_symlink() or not entry.is_file():
                continue
            if not _under(base, entry):
                raise UnsafeMaildirPath("message path escapes Maildir")
            result.append(entry)
            if limit is not None and len(result) >= limit:
                return result
    return result


def archive_message(maildir, source, archive_relative):
    base = Path(maildir)
    source = Path(source)
    target_dir = base / archive_relative
    if not _under(base, source) or not _under(base, target_dir):
        raise UnsafeMaildirPath("archive path escapes Maildir")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists():
        raise FileExistsError("archive destination already exists")
    os.replace(str(source), str(target))
    return target
