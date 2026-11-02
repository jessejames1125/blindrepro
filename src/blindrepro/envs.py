"""Build and reuse small Python environments for agent scripts and authors' code."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# What a blind derivation may import. The agent cannot widen this list, because a package
# on the list could be the authors' own code. A researcher can, with --allow-package.
BLIND_PACKAGES = ["numpy", "scipy", "sympy", "mpmath"]
PYTHON_VERSION = "3.12"


def cache_root() -> Path:
    override = os.environ.get("BLINDREPRO_CACHE")
    if override:
        return Path(override)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "blindrepro"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "blindrepro"


def python_in(env: Path) -> Path:
    return env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


# A package name with optional extras and version limits. No options, links, paths or markers,
# because the list can come from a model or from someone else's run folder.
REQUIREMENT = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
    r"(?:\[[A-Za-z0-9._,-]+\])?"
    r"(?:\s*(?:==|>=|<=|~=|!=|<|>)\s*[A-Za-z0-9.*+!_-]+(?:\s*,\s*(?:==|>=|<=|~=|!=|<|>)\s*[A-Za-z0-9.*+!_-]+)*)?"
)
SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH", "COOKIE", "SESSION")
# A package with no wheel for this system builds from source, which can run for an hour or hang.
INSTALL_SECONDS = 900


class BadRequirement(ValueError):
    pass


class InstallFailed(RuntimeError):
    pass


def check_requirements(packages: list[str]) -> None:
    bad = [p for p in packages if not REQUIREMENT.fullmatch(p.strip())]
    if bad:
        raise BadRequirement("Refused to install these lines, which are not plain package names: " + "; ".join(bad))


def install_env() -> dict[str, str]:
    """The installer runs package build code, so it gets no keys or tokens from your environment."""
    return {k: v for k, v in os.environ.items() if not any(word in k.upper() for word in SECRET_WORDS)}


def _install(env: Path, args: list[str]) -> None:
    clean = install_env()
    uv = shutil.which("uv")
    if uv:
        subprocess.run([uv, "venv", "--quiet", "--python", PYTHON_VERSION, str(env)], check=True, env=clean)
        command = [uv, "pip", "install", "--quiet", "--python", str(python_in(env)), "--", *args]
    else:
        subprocess.run([sys.executable, "-m", "venv", str(env)], check=True, env=clean)
        command = [str(python_in(env)), "-m", "pip", "install", "--quiet", "--", *args]
    from .sandbox import run_tree

    result = run_tree(command, env=clean, seconds=INSTALL_SECONDS)
    if result.timed_out:
        raise InstallFailed(
            f"Installing the packages took more than {INSTALL_SECONDS // 60} minutes, so it was stopped. "
            "A package may be building from source; pin a version that has a wheel for this system."
        )
    if result.returncode != 0:
        raise InstallFailed("Installing the packages failed: " + (result.stderr or result.stdout)[-1500:].strip())


def ensure_env(packages: list[str]) -> Path:
    """Return the python of an environment holding exactly these packages, building it once."""
    check_requirements(packages)
    key = hashlib.sha256("\n".join(sorted(packages)).encode()).hexdigest()[:16]
    env = cache_root() / "envs" / key
    marker = env / "ready"
    if not marker.exists():
        shutil.rmtree(env, ignore_errors=True)
        env.parent.mkdir(parents=True, exist_ok=True)
        try:
            _install(env, list(packages))
        except InstallFailed:
            shutil.rmtree(env, ignore_errors=True)
            raise
        marker.write_text("\n".join(packages), encoding="utf-8")
    return python_in(env)


def env_for_requirements(requirements: Path) -> Path:
    """Environment for authors' code, from the requirements file the adapter step wrote."""
    lines = [
        line.strip()
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return ensure_env(lines)


def installed_packages(python: Path) -> list[str]:
    """The exact versions in an environment, for the record."""
    code = (
        "import importlib.metadata as m, sys, json;"
        "print(json.dumps(sorted(f\"{d.metadata['Name']}=={d.version}\" for d in m.distributions())));"
    )
    done = subprocess.run([str(python), "-I", "-c", code], capture_output=True, text=True, check=True)
    import json

    return [p for p in json.loads(done.stdout) if not p.startswith(("pip==", "setuptools=="))]


def python_version(python: Path) -> str:
    done = subprocess.run(
        [str(python), "-I", "-c", "import platform;print(platform.python_version())"],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()
