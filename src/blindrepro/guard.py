"""Run one Python script with network, other processes and outside files turned off.

Started as: python -I guard.py POLICY.json SCRIPT

Uses CPython audit hooks, which cannot be removed once added. A script that loads
native code can still get around them, so this stops accidents and ordinary model
behavior. It is not a security boundary against hostile code. Standard library only:
this file runs inside the researcher's chosen environment, not ours.
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
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
# Read-only system facts that numeric libraries look up on Linux and Mac.
SYSTEM_READS = ("/proc/", "/sys/", "/etc/", "/usr/lib/", "/usr/share/", "/System/", "/Library/")


def norm(path):
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def inside(path, roots):
    return any(path == root or path.startswith(root + os.sep) for root in roots)


def install(policy):
    write_roots = [norm(p) for p in policy["write_roots"]]
    read_roots = write_roots + [norm(p) for p in policy["read_roots"]]
    read_roots += [norm(p) for p in (sys.prefix, sys.base_prefix, sys.exec_prefix)]
    allow_process = policy.get("allow_process", False)
    log = open(policy["log"], "a", encoding="utf-8")

    # Imported before the hook so the hook itself never triggers an audited import.
    write = log.write
    flush = log.flush

    def block(kind, detail):
        write(json.dumps({"blocked": kind, "detail": str(detail)[:300]}) + "\n")
        flush()
        raise PermissionError(f"blindrepro guard: {kind} is off in this run ({detail})")

    def hook(event, args):
        if event in NETWORK:
            block("network", event)
        if event in PROCESS and not allow_process:
            block("process", event)
        if event == "open":
            target, _mode, flags = args
            if not isinstance(target, (str, bytes, os.PathLike)):
                return
            path = norm(os.fsdecode(target))
            if flags & WRITE_FLAGS:
                if not inside(path, write_roots):
                    block("file write", path)
            elif not inside(path, read_roots) and not path.startswith(SYSTEM_READS):
                block("file read", path)
        elif event in LISTING and args and args[0] is not None:
            target = args[0]
            if isinstance(target, (str, bytes, os.PathLike)):
                path = norm(os.fsdecode(target))
                if not inside(path, read_roots) and not path.startswith(SYSTEM_READS):
                    block("file listing", path)

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
