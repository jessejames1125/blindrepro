# Changelog

## 0.1.0 (not released)

First version.

- `demo`, `run`, `verify` and `doctor` commands.
- Blind derivation in a folder without the authors' code, a freeze with SHA-256 hashes, then the authors' code, then a comparison done by code.
- Three judges: recorded runs, the `claude` command, and an API key through the official SDK.

### Found while building it

- A live model broke out of the first guard. Asked to try, it read both test secrets through `kernel32` calls in `ctypes` and through an `os.link` hard link, and it wrote outside the folder through `CreateFileW`. Foreign calls, links, sqlite, memory maps and native modules from the work folder are now off for blind derivations. The rerun leaked neither secret: see `evals/escape-test.json`. That result means the known doors are shut. It does not make the guard a security boundary.
- The first Lawson run used the blind agent's reading of the paper's settings for the authors' code too. The adapter prompt now asks for the settings that produced the published result, and asks the agent to list any differences.
- An independent review found more, all fixed before release: a plain Python script could rewrite the guard's rules through the call stack; `verify` trusted the authors' side of a record, which no hash covered (now `seal.json` covers the whole run, and `--expect` checks a published hash); package lines from a record went to the installer unchecked; a derivation that failed to rerun still passed `verify`; the leak check missed negative values and thousands separators; finishing a paused run with another tolerance changed the verdict; the account name could reach records through lower-cased paths.
- The first Lawson rerun on this version asked both sides for two significant figures, so rounding set the error (3.45%). The scoping prompt now asks for full precision.
- On Windows, a busy system query made `platform` start a process, and the guard logged it as a blocked attempt. System facts are now read before the guard starts.
- A live run asked for a package with no Windows wheel, and its source build ran for over 20 minutes with no limit. Installs now stop after 15 minutes, child processes included, and the reason reaches the agent.
- When an agent session hit its time limit, the `claude` judge crashed on Windows and left the tool server's install and `cmake` running. The judge now runs under the same job object or process group as scripts. An adapter agent that stops no longer throws away the frozen blind result: the verdict says why the authors' side is missing.
- On Windows a closed job's processes exit a moment later, so deleting their output files at once crashed a run. That cleanup error is now ignored.
- The leak and typed-number checks flagged any number within 0.5% or 0.1% of a target, which caught a QAOA paper's optimal angles. A number now counts only when the target, rounded to that number's printed digits, gives it.
- An adapter script named the account name outside any path, and the record kept it. Records now swap the bare account name for `<user>`.
- A second independent review of these fixes found more, fixed here: on Linux and Mac, scripts and installs started by a timed-out `claude` session's tool server sat in their own process groups and kept running; they now stay in the session's group. A copied number printed with more digits than the paper's value slipped past the leak check; numbers now match at the coarser of the two precisions. Whole numbers were counted with one digit too many, a literal like `1e999` crashed the check, a common account name such as `user` would have been swapped inside JSON keys and code, install errors reached records without local paths swapped, a Ctrl+C left process trees running, an old `stopped.txt` could be sealed into a finished run, the demo pinned only the freeze hash, and creating an environment had no clock.
- The authors' Lawson code takes about 4.5 minutes, so `demo` takes the authors' values from the sealed record by default; `demo --full` reruns their code too.
