"""Host-local advisory lock shared by study preparation and memory operations."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def research_lock(root):
    folder = Path(root) / '.cache'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'research-state.lock'
    if path.is_symlink():
        raise ValueError('Research lock must not be a symlink')
    with path.open('a+b') as handle:
        try:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0)
                if not handle.read(1):
                    handle.write(b'0'); handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('Another research or memory operation holds this checkout lock; wait for it to finish. Never delete reservations to retry.') from exc
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
