"""Run one Python script with network, other processes and outside files turned off.

Started as: python -I guard.py POLICY.json SCRIPT

Uses CPython audit hooks, which cannot be removed once added. In strict mode, used for
blind derivations, foreign calls through ctypes, links, and modules that open files from C
are also off. Compiled code the script managed to load could still get around all of it, so
this stops accidents and ordinary model behavior, and it is not a security boundary against
hostile code. Standard library only: this file runs inside the chosen environment, not ours.
"""

import json
import os
import runpy
import sys

NETWORK = {
    "socket.connect",
    "socket.bind",
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.gethostbyaddr",
    "socket.sendto",
    "socket.sendmsg",
    "urllib.Request",
    "http.client.connect",
    "ftplib.connect",
    "smtplib.connect",
}
PROCESS = {
    "subprocess.Popen",
    "os.system",
    "os.exec",
    "os.spawn",
    "os.posix_spawn",
    "os.fork",
    "os.forkpty",
    "os.startfile",
    "os.startfile/2",
    "pty.spawn",
}
LISTING = {"os.listdir", "os.scandir", "glob.glob"}
# First argument is a path that must be inside the work folder.
TOUCHING = {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.truncate", "os.utime", "os.chdir"}
TWO_PATHS = {"os.rename"}
# Ways around the file and network checks. Off for blind derivations.
STRICT_EVENTS = {
    "os.link",
    "os.symlink",
    "ctypes.call_function",
    "ctypes.dlsym",
    "ctypes.dlsym/handle",
    "sqlite3.connect",
    "mmap.__new__",
    "socket.__new__",
    "socket.socketpair",
}
STRICT_PREFIXES = ("_winapi.", "msvcrt.", "ctypes.string_at", "ctypes.wstring_at")
NATIVE_SUFFIXES = (".pyd", ".so", ".dll", ".dylib")
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
# Read-only system facts that numeric libraries look up on Linux and Mac.
SYSTEM_READS = ("/proc/", "/sys/", "/etc/", "/usr/lib/", "/usr/share/", "/System/", "/Library/")


def norm(path):
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def inside(path, roots):
    return any(path == root or path.startswith(root + os.sep) for root in roots)


def _close_side_doors():
    """Remove process-starting functions that have no audit event of their own."""

    def refused(*_args, **_kwargs):
        raise PermissionError("blindrepro guard: process is off in this run")

    for name, attribute in (("_posixsubprocess", "fork_exec"), ("_winapi", "CreateProcess")):
        try:
            module = __import__(name)
        except ImportError:
            continue
        setattr(module, attribute, refused)


def install(policy):
    write_roots = [norm(p) for p in policy["write_roots"]]
    read_roots = write_roots + [norm(p) for p in policy["read_roots"]]
    env_roots = [norm(p) for p in (sys.prefix, sys.base_prefix, sys.exec_prefix)]
    read_roots += env_roots + [norm(__file__)]
    allow_process = policy.get("allow_process", False)
    strict = policy.get("strict", not allow_process)
    devnull = norm(os.devnull)
    log = open(policy["log"], "a", encoding="utf-8")

    # Bound before the hook so the hook itself never triggers an audited lookup.
    write = log.write
    flush = log.flush

    def block(kind, detail):
        write(json.dumps({"blocked": kind, "detail": str(detail)[:300]}) + "\n")
        flush()
        raise PermissionError(f"blindrepro guard: {kind} is off in this run ({detail})")

    def to_path(target):
        return norm(os.fsdecode(target))

    def is_path(target):
        return isinstance(target, (str, bytes, os.PathLike))

    def hook(event, args):
        if event in NETWORK:
            block("network", event)
        if event in PROCESS and not allow_process:
            block("process", event)
        if event == "open":
            target, _mode, flags = args
            if not is_path(target):
                return
            path = to_path(target)
            if path == devnull:
                return
            if flags & WRITE_FLAGS:
                if not inside(path, write_roots):
                    block("file write", path)
            elif not inside(path, read_roots) and not path.startswith(SYSTEM_READS):
                block("file read", path)
        elif event in LISTING and args and is_path(args[0]):
            path = to_path(args[0])
            if not inside(path, read_roots) and not path.startswith(SYSTEM_READS):
                block("file listing", path)
        elif event in TOUCHING and args and is_path(args[0]):
            if not inside(to_path(args[0]), write_roots):
                block("file change", args[0])
        elif event in TWO_PATHS:
            for target in args[:2]:
                if is_path(target) and not inside(to_path(target), write_roots):
                    block("file move", target)
        if not strict:
            return
        if event in STRICT_EVENTS or event.startswith(STRICT_PREFIXES):
            block("low-level access", event)
        if event == "ctypes.dlopen" and args and args[0] is not None:
            name = args[0]
            if not is_path(name) or not inside(to_path(name), env_roots):
                block("low-level access", f"ctypes.dlopen {name}")
        if event == "import" and len(args) > 1 and is_path(args[1]):
            filename = os.fsdecode(args[1])
            if filename.lower().endswith(NATIVE_SUFFIXES) and inside(to_path(filename), write_roots):
                block("low-level access", f"native module {filename}")

    if strict:
        # When a Windows system query is busy, platform falls back to starting a process.
        # Ask now and it keeps the answer, so numeric packages never hit that path.
        import platform

        platform.uname()
        _close_side_doors()
        # Numeric packages import ctypes, whose own setup makes foreign calls. Let it finish
        # first; after this point the hook refuses any new foreign call.
        try:
            import ctypes  # noqa: F401
        except ImportError:
            pass
    sys.addaudithook(hook)


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        policy = json.load(handle)
    script = os.path.abspath(sys.argv[2])
    install(policy)
    sys.path.insert(0, os.path.dirname(script))
    sys.argv = [script]
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
