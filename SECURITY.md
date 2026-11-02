# Security

Report a problem through a private GitHub security advisory on this repository.

Things to know before you run this:

- `blindrepro run` runs the authors' code on your machine. The guard turns off network and writes outside the work folder, but native code, or a script that rewrites Python's own modules, can get around it. Use a container for code you do not trust.
- `blindrepro verify` runs the scripts in the folder you give it and installs the packages that folder lists. Treat a run folder from someone else like any code from them.
- Package installs get your environment minus anything named like a key, token, secret or password.
- Scripts, installs and agent sessions run under a clock, and a stop ends everything they started (a job object on Windows, a process group on Linux and Mac). Known gaps: a process started in the first milliseconds, before it joins the job, is outside it; on Windows a stopped job's files can be left in the temp folder for a moment, and a cleanup that fails is skipped, so a session's raw output can stay there.
- `verify --expect` pins the freeze hash, which covers the blind side. The authors' side is covered by the seal, which anyone holding the folder can recompute; `verify --skip-authors` trusts it. Rerun the authors' code (the default) when that matters. The bundled demo pins both hashes.
- The tool never reads, stores or forwards login tokens. The `claude` judge calls the `claude` command you signed in to yourself. The `api` judge reads `ANTHROPIC_API_KEY` from your environment and sends it only to the Anthropic API.
