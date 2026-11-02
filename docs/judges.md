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

It reads `ANTHROPIC_API_KEY` and runs the same steps through the Messages API with the official SDK. The SDK is an optional extra, so the base install stays free of dependencies: `uvx --from "blindrepro[api]" blindrepro run ... --judge api`. It offers three file tools and `run`, all confined to the work folder. Every reply is in the transcript. Default model: `claude-opus-5-5`.

If the model declines a step, or a reply is cut off at the token limit, the run stops with an error and no tool from that reply runs. Anthropic's automatic switch to another model after a refusal stays off on purpose, because a verdict has to name the one model that did the work.

As of 0.1.0 this judge is tested against a local fake server that speaks the real event format. It has not been run against the real API.

## Your login

blindrepro never asks for, reads, stores or forwards a login token. It starts the unmodified `claude` program on your machine, which uses your own Claude plan. Set `--judge api` to bill an API key instead.
