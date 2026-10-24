"""In-process and inter-process priority arbitration for Modbus buses."""

import hashlib
import logging
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path


logger = logging.getLogger(__name__)

_registry_lock = threading.Lock()
_registry = {}


def _lock_file(fd, nonblocking=True):
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK if nonblocking else msvcrt.LK_LOCK, 1)
            return True
        except OSError:
            return False
    else:
        import fcntl

        flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
        try:
            fcntl.flock(fd, flags)
            return True
        except BlockingIOError:
            return False


def _unlock_file(fd):
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


class ModbusBusArbiter:
    """Give control requests priority across threads and cooperating processes.

    The OS lock is held for one Modbus transaction. A control operation publishes
    a marker for its full duration, so polling in every process waits until the
    operation finishes. Programs that access the serial device without this
    arbiter cannot be made to cooperate by an advisory file lock.
    """

    def __new__(cls, bus_name: str):
        with _registry_lock:
            arbiter = _registry.get(bus_name)
            if arbiter is None:
                arbiter = super().__new__(cls)
                _registry[bus_name] = arbiter
            return arbiter

    def __init__(self, bus_name: str):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.bus_name = bus_name
        self._condition = threading.Condition()
        self._active_request = False
        self._waiting_control = 0
        self._control_scopes = 0
        self._control_interrupt = threading.Event()
        self._thread_state = threading.local()
        digest = hashlib.sha256(bus_name.encode("utf-8")).hexdigest()[:24]
        self._lock_dir = Path(tempfile.gettempdir()) / "datalogger_modbus_locks"
        self._lock_path = self._lock_dir / f"{digest}.lock"
        self._marker_prefix = f"{digest}.control."
        self._held_lock_fd = threading.local()
        self._marker_path = threading.local()

    @contextmanager
    def operation(self, mode: str):
        previous = getattr(self._thread_state, "mode", "polling")
        self._thread_state.mode = mode
        if mode == "control" and previous != "control":
            marker = self._publish_control_marker()
            with self._condition:
                self._control_scopes += 1
            self._marker_path.value = marker
        else:
            marker = None
        try:
            yield
        finally:
            self._thread_state.mode = previous
            if marker is not None:
                with self._condition:
                    self._control_scopes -= 1
                    self._condition.notify_all()
                for _ in range(3):
                    try:
                        marker.unlink(missing_ok=True)
                        break
                    except OSError:
                        time.sleep(0.01)
                else:
                    try:
                        marker.unlink(missing_ok=True)
                    except OSError:
                        logger.warning("Could not remove control marker %s", marker)
                self._marker_path.value = None

    def current_mode(self) -> str:
        return getattr(self._thread_state, "mode", "polling")

    @property
    def control_pending(self) -> bool:
        return self._waiting_control > 0 or self._control_scopes > 0 or self._has_control_markers()

    def signal_control_interrupt(self):
        self._control_interrupt.set()

    def clear_control_interrupt(self):
        self._control_interrupt.clear()

    def is_interrupted(self) -> bool:
        return self._control_interrupt.is_set() or self._has_control_markers()

    def _publish_control_marker(self):
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        marker_name = f"{self._marker_prefix}{os.getpid()}.{threading.get_ident()}.{time.time_ns()}"
        marker = self._lock_dir / marker_name
        # File tạm có tiền tố riêng biệt bắt đầu bằng '.', tránh bị glob(f"{self._marker_prefix}*") quét trúng
        temporary = self._lock_dir / f".tmp_{marker_name}"
        temporary.write_text(str(os.getpid()), encoding="ascii")
        os.replace(temporary, marker)
        return marker

    @staticmethod
    def _pid_is_alive(pid):
        if pid == os.getpid():
            return True
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except OSError:
            return False

    def _has_control_markers(self):
        if not self._lock_dir.exists():
            return False
        found = False
        now_ns = time.time_ns()
        for marker in self._lock_dir.glob(f"{self._marker_prefix}*"):
            if marker.name.endswith(".tmp") or marker.name.startswith("."):
                continue
            try:
                parts = marker.name[len(self._marker_prefix):].split(".")
                if len(parts) >= 1 and parts[0].isdigit():
                    pid = int(parts[0])
                else:
                    pid = int(marker.read_text(encoding="ascii").strip())

                if len(parts) >= 3 and parts[2].isdigit():
                    age_seconds = (now_ns - int(parts[2])) / 1e9
                else:
                    age_seconds = time.time() - marker.stat().st_mtime

                stale = age_seconds > 24 * 60 * 60
                if not stale and self._pid_is_alive(pid):
                    found = True
                else:
                    marker.unlink(missing_ok=True)
            except (OSError, ValueError):
                try:
                    # Chỉ dọn dẹp file hỏng nếu đã tồn tại lâu (> 60s), tránh xóa nhầm file mới
                    if marker.exists() and (time.time() - marker.stat().st_mtime > 60):
                        marker.unlink(missing_ok=True)
                except OSError:
                    pass
        return found

    def acquire(self):
        mode = self.current_mode()
        with self._condition:
            if mode == "control":
                self._waiting_control += 1
                self._control_interrupt.set()
            try:
                while self._active_request or (
                    mode != "control" and (
                        self._waiting_control > 0
                        or self._control_scopes > 0
                        or self._has_control_markers()
                    )
                ):
                    self._condition.wait(timeout=0.05)
                self._active_request = True
            finally:
                if mode == "control":
                    self._waiting_control -= 1

        try:
            self._lock_dir.mkdir(parents=True, exist_ok=True)
            fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o666)
            if os.name == "nt" and os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
            while True:
                # Nếu là Polling và phát hiện Control đang chờ hoặc đang hoạt động:
                # Lập tức nhả cờ active_request để nhường hoàn toàn cho Control chạy (tránh Deadlock)
                if mode != "control" and (
                    self._waiting_control > 0
                    or self._control_scopes > 0
                    or self._has_control_markers()
                ):
                    with self._condition:
                        self._active_request = False
                        self._condition.notify_all()
                        while mode != "control" and (
                            self._waiting_control > 0
                            or self._control_scopes > 0
                            or self._has_control_markers()
                        ):
                            self._condition.wait(timeout=0.05)
                        while self._active_request:
                            self._condition.wait(timeout=0.05)
                        self._active_request = True
                    continue

                if _lock_file(fd):
                    if mode == "control" or not (
                        self._waiting_control > 0
                        or self._control_scopes > 0
                        or self._has_control_markers()
                    ):
                        self._held_lock_fd.value = fd
                        return
                    _unlock_file(fd)
                time.sleep(0.05)
        except BaseException:
            with self._condition:
                self._active_request = False
                self._condition.notify_all()
            raise

    def release(self):
        fd = getattr(self._held_lock_fd, "value", None)
        try:
            if fd is not None:
                _unlock_file(fd)
                try:
                    os.close(fd)
                except OSError:
                    pass
                self._held_lock_fd.value = None
        finally:
            with self._condition:
                self._active_request = False
                if self._waiting_control == 0 and self._control_scopes == 0:
                    self._control_interrupt.clear()
                self._condition.notify_all()
