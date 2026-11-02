# Judges: which model runs the agents

| Judge | Flag | Needs | Sends |
|---|---|---|---|
| Recorded | `--judge recorded:<folder>` | nothing | nothing. It replays a past run's files through the real freeze, guard and comparison. |
| Claude Code | `--judge claude` (default) | `claude` installed and signed in by you | whatever that command sends: the paper text, the prompts, tool results |
| API key | `--judge api` | `ANTHROPIC_API_KEY` | the same, to `api.anthropic.com` |

`blindrepro demo` uses no judge at all. It checks the hashes and reruns the frozen scripts.

## The `claude` judge

It starts the `claude` command you already have, with these limits:

```
claude -p --restricted --strict-mcp-config --mcp-config <our run tool only>
       --tools Read,Write,Edit,Grep,Glob --permission-mode dontAsk
       --system-prompt <fixed text> --no-session-persistence
```

and with `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` and `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`, so your CLAUDE.md files and saved memory stay out of the agent's context. API keys in your environment are removed from this call, so a subscription login is never billed to a key by accident. Choose a model with `--model` and effort with `--effort`.

## The `api` judge

It reads `ANTHROPIC_API_KEY` and runs the same steps through the Messages API. It offers three file tools and `run`, all confined to the work folder. Every request and reply is in the transcript. Default model: `claude-opus-5-5`. As of 0.1.0 this judge is tested against a local fake server and has not been run against the real API.

## What Anthropic's terms say

Read on 2026-11-02. This is a reading of public pages, not legal advice. Check the pages yourself.

**[Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance):**

> Anthropic does not permit third-party developers to offer Claude.ai login into their own applications, or to route requests through Free, Pro, Max, or Ultra plan credentials on behalf of their users. Moreover, developers may not collect, store, or intermediate Claude.ai credentials or session tokens

> Nor does it prevent an end user from signing in to the unmodified Claude Code binary with their own Claude subscription

> Advertised usage limits for Pro, Max, and Ultra plans assume ordinary, individual usage of Claude Code and the Agent SDK.

**[Consumer Terms](https://www.anthropic.com/legal/consumer-terms), section 3, lists among things you may not do:**

> Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it, to access the Services through automated or non-human means, whether through a bot, script, or otherwise.

**[Headless docs](https://code.claude.com/docs/en/headless)** document `claude -p` for non-interactive and scripted use.

**[Commercial Terms](https://www.anthropic.com/legal/commercial-terms)** govern API keys and allow using the services "to power products and services Customer makes available to its own customers and end users".

What this tool does with that:

- It never asks for, reads, stores or forwards a login token. It starts the unmodified binary on your machine, under your own sign-in, for your own research.
- No page speaks directly to a local open source tool that starts the user's own `claude` command. The documented `claude -p` path looks to us like the explicit permission the Consumer Terms mention, but that is our reading.
- Running many papers on a subscription may go beyond "ordinary, individual usage". For a lab service, a shared machine, a batch of papers, or anything done for other people, use `--judge api`.
- Do not use outputs to train a model. The [Usage Policy](https://www.anthropic.com/legal/aup) restricts that.
