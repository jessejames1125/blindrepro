# Security

Report a problem through a private GitHub security advisory on this repository.

Two things to know before you run this:

- `blindrepro run` runs the authors' code on your machine. The guard turns off network and writes outside the work folder, but native code, or a script that rewrites Python's own modules, can get around it. Use a container for code you do not trust.
- `blindrepro verify` runs the scripts in the folder you give it and installs the packages that folder lists. Treat a run folder from someone else like any code from them.
- Package installs get your environment minus anything named like a key, token, secret or password.
- The tool never reads, stores or forwards login tokens. The `claude` judge calls the `claude` command you signed in to yourself. The `api` judge reads `ANTHROPIC_API_KEY` from your environment and sends it only to the Anthropic API.
