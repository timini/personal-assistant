# Configuring Hermes Agent for the PA

A step-by-step guide to getting Hermes Agent from "installed" to "running and useful", written for
someone who has not configured an agent runtime before.

This is a setup guide, not a migration plan. For the capability-by-capability porting work, see
issue #12.

## Provenance

Written 12 September 2026 against **Hermes Agent v0.21.2 (2026.9.11)** on the Mac mini.

Commands are marked as follows:

- **[verified]** the syntax was read from `--help` or the command was run on that host
- **[docs]** taken from the Hermes documentation and not yet run here

Nothing in this guide has been applied. At the time of writing the install is unconfigured: no
gateway, no cron jobs, no memories, no sessions.

---

## 1. What Hermes gives you that the current setup does not

Two things, and they are the two things missing today.

**A listener.** Telegram today is one-way. `pa_telegram.client.get_messages()` is a single
`getUpdates` call, run only when `pa-core checkin` or `pa-core context` runs, which means a human
has to be at a terminal. The 06:30 message asks for a reply and then nothing reads it. Hermes runs a
gateway process that stays connected, so a reply becomes a real turn.

**A model in the scheduled loop.** `scripts/wellness_prompt.py` renders an f-string. Its own
docstring says "Deterministic: no model in the loop, per ADR 0001". The same headings and the same
closing line go out every day. Hermes agent cron runs an actual model turn on a schedule, so the
message responds to the day rather than restating a template.

Two things worth knowing before you worry about the size of the job:

- The bundled `google-workspace` skill drives **the same `gws` binary** this repo already wraps,
  using the same OAuth. Nothing needs re-authorising.
- Hermes can shell out to the existing `pa-*` CLIs. You do not have to rewrite packages as MCP
  servers to get value.

---

## 2. Before you start

```bash
hermes --version     # expect: Hermes Agent v0.21.2 (2026.9.11)   [verified]
hermes status        # environment, API keys, messaging platforms  [verified]
hermes doctor        # flags missing dependencies and known issues [verified]
```

`hermes status` is the one to read carefully. On the mini it currently reports:

| Item | State |
|---|---|
| Model | `z-ai/glm-5.2` |
| Provider | OpenRouter |
| OpenRouter key | Set, in `~/.hermes/.env` |
| Anthropic key | Not set |
| Nous Portal | Not logged in |
| Telegram | Not configured |
| Memory | Built-in only, no external provider |

Check the backends the PA depends on are on PATH:

```bash
which gws wacli ntn
```

On the mini: `gws` 0.22.5 and `wacli` are present, `ntn` (Notion's official CLI) is not installed.
`ntn` is optional; the bundled `notion` skill falls back to plain HTTP with the same integration
token.

`hermes doctor` will list warnings for optional plugins you do not use (Spotify, Home Assistant,
image generation, and so on). Those are safe to ignore. Read the numbered "issues to address" at the
bottom instead.

---

## 3. Choose a model, and choose it deliberately

This matters more than it looks, because a gateway plus cron runs whether or not anyone reads the
output. The cost is now a standing cost rather than something you incur by opening a terminal.

```bash
hermes model         # interactive provider and model picker   [verified: command exists]
hermes portal        # Nous Portal login, if you want that route [verified: command exists]
hermes auth add openrouter                                    # [verified: syntax]
hermes auth list     # show pooled credentials                 # [verified]
```

Two traps here.

**The stock config default is out of date.** `~/.hermes/config.yaml` ships with
`model.default: "anthropic/claude-opus-4.6"`. That is not a current model. The effective model is
whatever `hermes status` reports, which on the mini is `z-ai/glm-5.2` via OpenRouter, so the stale
default is not currently biting. Set it explicitly rather than leaving it to chance:

```bash
hermes config set model.default <provider/model>              # [docs]
```

**Match the model to the job.** GLM-5.2 is fine for a scheduled nudge or a deterministic summary.
The PA's actual value is concentrated in judgement work: email triage decisions, coaching tone,
deciding what to surface and what to leave alone. Running that on the cheapest available model is
where quality regressions will show up first and be hardest to notice. `hermes cron create` accepts
`--model` and `--provider` per job, so use a cheap model as the default and override upward on the
jobs that think.

---

## 4. Prove the model path works

Before adding a gateway, a schedule, or any skills:

```bash
hermes chat          # [verified: command exists]
```

Ask it something trivial. If this fails, nothing downstream will work, and you want to find that out
now rather than while debugging a cron job that silently delivers nothing.

---

## 5. Connect Telegram

### Read this first: two consumers on one bot destroys messages

Telegram's `getUpdates` hands each update to exactly one reader and advances an offset. Once the
offset moves past a message, it is gone. If the Hermes gateway starts polling while the existing PA
code is still polling the same bot, they will eat each other's messages, unpredictably, and you will
lose some entirely.

The existing consumers are:

- `~/Library/LaunchAgents/com.pa.wellness-morning.plist` and `com.pa.wellness-evening.plist`
- `pa_core/context.py`, which calls `get_messages()` as part of building context
- `pa_core/cli.py` `cmd_checkin`, which calls `acknowledge_messages()` and advances the offset

**Turn them off before Hermes starts.** In this order:

```bash
launchctl unload -w ~/Library/LaunchAgents/com.pa.wellness-morning.plist
launchctl unload -w ~/Library/LaunchAgents/com.pa.wellness-evening.plist
```

Leave the plist files in place so rollback is a single `launchctl load -w`. Then remove the Telegram
fetch and acknowledge calls from the context and checkin paths. Keep
`activity/telegram_inbox.jsonl`: it is a durable append-only archive written before the offset can
advance, and it is your safety net if anything goes wrong.

The alternative, if you would rather not touch the existing code yet, is to create a **second bot**
with BotFather and point Hermes at that one. Two bots, two offsets, no collision. It is the safer
way to trial the gateway alongside the current setup.

### Set it up

```bash
hermes gateway setup      # interactive platform configuration   [verified: command exists]
hermes gateway status     # [verified]
hermes gateway install    # install as a launchd user service     [verified: command exists]
hermes gateway run        # run in the foreground, for debugging  [verified: command exists]
```

Start with `hermes gateway run` in a terminal so you can watch it. Only `install` it as a service
once you have seen it work.

During setup:

- **Restrict to a single allowed user.** Your own Telegram user ID, nobody else.
- **Do not expose the gateway to the network.** Keep it on localhost. This class of tool has a live
  remote-code-execution history: CVE-2026-25253 in OpenClaw, with roughly 135,000 instances found
  exposed on the public internet in January 2026. Hermes is a different project, but the shape of
  the risk is the same, and an agent with shell access on a machine holding your Google and Notion
  credentials is not something to leave listening on a public port.

### Verify

Send it, from your phone, with no terminal open:

1. Plain text.
2. A photo.
3. A forwarded appointment email, and check the event actually lands on the right calendar.
4. A free-text reply to a question it asked.

Item 3 is the real test. On 26 August a forwarded GP appointment sat in the bot until someone opened
a terminal hours later. If it now lands unattended, the gateway is doing its job.

---

## 6. Give it the PA's tools

Hermes loads skills from several places. The two that matter here:

**Bundled skills**, already on disk at `~/.hermes/skills/`:

| Skill | Path | Use |
|---|---|---|
| google-workspace | `productivity/google-workspace` | Gmail, Calendar, Drive via `gws` |
| notion | `productivity/notion` | Notion API, `ntn` CLI or plain HTTP |
| email-inbox-triage | `email/email-inbox-triage` | Triage procedure, adapt to the four-bucket rule |
| weekly-review-planning | `productivity/weekly-review-planning` | Sunday hygiene pass |

**Repo-local skills.** Hermes loads `./.hermes/skills` or `./.agents/skills` from a project once you
trust it. This repo already has `.agents/skills/`.

```bash
hermes skills trust /path/to/PA   # [verified: subcommand exists]
hermes skills list                                                              # [verified]
hermes skills inspect <name>    # preview without installing                    # [verified]
```

Keeping skills in the repo rather than under `~/.hermes` means they are versioned, reviewable, and
survive a Hermes reinstall.

### Anchor every command to an absolute path

The agent's working directory is not guaranteed. Write every PA command as:

```bash
uv run --directory /path/to/PA pa-notion tasks list --json
uv run --directory /path/to/PA pa-google calendar --json
```

A skill that assumes it is already in the repo will work when you test it by hand and fail from
cron, which is the worst combination.

### Adding MCP servers

```bash
hermes mcp add       # discovery-first install   [verified: subcommand exists]
hermes mcp list                                # [verified]
hermes mcp test      # test a server connection # [verified]
hermes mcp login <server>                      # [verified: subcommand exists]
```

Tool discovery succeeding is not proof of functional access. Always do one real read and one real
write with a read-back before trusting a server.

---

## 7. Schedule something

Hermes cron has two modes, and picking the right one is most of the skill.

**Agent cron.** The model runs. Use it for anything needing judgement: the morning plan, triage, the
weekly review.

**Script-only cron** (`--no-agent`). The script runs, its stdout is delivered verbatim, no model is
involved and no tokens are spent. Use it for everything deterministic: the weekly flow email, the
Drive backup, the task snapshot.

All flags below are **[verified]**, read from `hermes cron create --help`.

```bash
hermes cron create "0 6 * * *" "Build today's plan and send it to me" \
  --name morning-plan \
  --deliver telegram \
  --model <a-model-that-can-think> \
  --skill pa-morning
```

```bash
hermes cron create "0 8 * * 1" \
  --name weekly-flow-email \
  --script weekly_flow_email.sh \
  --no-agent \
  --deliver telegram
```

Scripts must live under `~/.hermes/scripts/`. Keep the real implementation in the repo and put a
one-line launcher there:

```bash
#!/bin/bash
exec uv run --directory /path/to/PA \
  python scripts/weekly_flow_email.py
```

`.sh` and `.bash` files run via bash, everything else via Python.

Flags worth knowing:

| Flag | What it does |
|---|---|
| `--deliver` | `origin`, `local`, `telegram`, `platform:chat_id` |
| `--failure-deliver` | Separate target for failure notices. `local` suppresses them |
| `--no-agent` | Script only, no model. Empty stdout means silence |
| `--monitor-script` | Runs a cheap script first; identical output suppresses the agent run entirely |
| `--reasoning-effort` | Turn effort down on routine jobs |
| `--continuity` | Carry context between runs of the same job |
| `--paused` | Create it disabled, so you can inspect before it fires |

`--monitor-script` is the one people miss. It turns "check the inbox every hour" from an hourly model
call into a model call only when something actually changed. Output must be byte-stable, so no
timestamps.

Managing jobs:

```bash
hermes cron list        # [verified]
hermes cron runs        # durable execution attempts    [verified]
hermes cron incidents   # failures needing acknowledgement [verified]
hermes cron doctor      # health-check the jobs         [verified]
hermes cron notepad     # persistent KV across runs of a job [verified]
hermes cron tick        # run due jobs once and exit, for testing [verified]
```

Create new jobs `--paused`, then `hermes cron tick` to test, then `hermes cron resume`.

### Move one schedule at a time

Disable the old job at the same moment you enable the new one. Duplicate delivery is what trains you
to ignore the channel, which is the problem you are trying to fix.

---

## 8. Memory, and why the handbook does not go in it

Hermes has built-in memory in `~/.hermes/memories/` as `MEMORY.md` and `USER.md`. It is deliberately
small and curated, and it is injected at session start.

The PA's handbook is roughly 35KB in `CLAUDE.md` alone, plus a gitignored `user-instructions.md`.
That does not belong in memory. Put conventions in **skills**, which load on demand, and keep memory
for short durable facts and preferences.

Enforce standing safety rules through an always-loaded instruction file, not through optional skill
discovery. A rule that only applies when the agent happens to load the right skill is not a rule.

```bash
hermes memory status    # [verified: subcommand exists]
hermes memory setup     # external providers: honcho, mem0, and others [verified]
hermes memory off       # built-in only                                [verified]
```

---

## 9. Safety controls

```bash
hermes pause                        # emergency stop: halts cron and new gateway turns [verified]
hermes resume                       # lift it                                          [verified]
hermes approvals test '<command>'   # dry-run the approval verdict, never executes     [verified]
hermes approvals suggest            # propose allowlist entries from past decisions    [verified]
```

`hermes pause` is the panic button. Learn it before you need it.

Map the PA's existing standing rules onto this:

- Anything that sends to a real person is draft-and-confirm. Do not add send commands to the
  allowlist.
- Funds are tight, so spend tasks stay parked. Money never moves unattended.
- Act freely on safe and reversible work (research, drafts for review, task hygiene) and report it.

`hermes approvals suggest` is convenient and will quietly erode those boundaries if you accept its
proposals without reading them. Read each one.

---

## 10. Check it survives a reboot

```bash
hermes gateway status
hermes cron list
hermes cron runs
```

Reboot the mini and run all three again.

**Known limitation.** The mini runs FileVault with automatic login disabled. `pmset` is set to never
sleep and to restart after a power failure, but FileVault means an unattended boot stops at the
unlock screen. A power cut leaves the PA down until someone is physically at the machine. This is
acceptable for an assistant, but do not let anything load-bearing depend on it.

---

## 11. Troubleshooting

**A CLI works in your terminal but fails from the gateway.**

This is the most likely problem you will hit, and it is not obvious. Credentials in the macOS login
keychain are readable only by processes in the GUI (Aqua) security session. This is why
`com.pa.claude-tmux.plist` exists: it starts a long-lived tmux session inside the GUI login session
so that attaching over SSH inherits keychain access. A tmux server started over SSH cannot read those
credentials and reports "Not logged in".

A launchd-installed gateway may hit the same wall for Google, Notion or Garmin. Test it early:

```bash
uv run --directory /path/to/PA pa-notion tasks list --json
```

Run that from inside the gateway's own context, not from your shell. If it fails, run the gateway
inside the existing `claude` tmux session with `hermes gateway run` instead of installing it as a
launchd service.

**Gateway will not start.** Check `~/.hermes/logs/errors.log` and `~/.hermes/logs/agent.log`, then
`hermes logs`. Run `hermes gateway run` in the foreground to see the failure directly.

**A cron job runs but delivers nothing.** With `--no-agent`, empty stdout is silence by design. Check
`hermes cron runs` for the exit status and `hermes cron incidents` for recorded failures. Confirm
`--deliver` is set: the default is not Telegram.

**Duplicate Telegram messages.** Two consumers on one bot. Confirm the wellness LaunchAgents are
unloaded and that nothing still calls `acknowledge_messages()`.

**Model or provider auth failures.** `hermes status` shows which keys and OAuth sessions are live.
Keys go in `~/.hermes/.env`. `hermes auth list` shows pooled credentials, which are separate from
env-var keys, so check both.

**Where things live.**

| Path | Contents |
|---|---|
| `~/.hermes/config.yaml` | Model, provider, database, runtime settings |
| `~/.hermes/.env` | API keys |
| `~/.hermes/cron/jobs.json` | Scheduled jobs |
| `~/.hermes/scripts/` | Scripts callable from cron |
| `~/.hermes/skills/` | Bundled and installed skills |
| `~/.hermes/memories/` | `MEMORY.md`, `USER.md` |
| `~/.hermes/sessions/` | Conversation history |
| `~/.hermes/logs/` | `agent.log`, `errors.log` |
| `~/.hermes/SOUL.md` | Base system prompt |

---

## 12. Suggested order

1. Sections 2 to 4. Confirm Hermes can talk to a model at all.
2. Section 5, using a **second Telegram bot** so nothing existing breaks. This alone fixes the
   one-way-channel problem and is where most of the value is.
3. Section 7, one scheduled job, `--paused`, tested with `hermes cron tick`.
4. Only then move the 06:30 and 21:00 jobs across, one at a time, disabling each old one as you go.
5. Section 6 and issue #12 for the porting work.

Do not start at step 5.

## Rollback

Stop Hermes first so there is only ever one consumer of the bot:

```bash
hermes pause
hermes gateway stop
launchctl load -w ~/Library/LaunchAgents/com.pa.wellness-morning.plist
launchctl load -w ~/Library/LaunchAgents/com.pa.wellness-evening.plist
```

Then revert the Telegram changes in `pa_core/context.py` and `pa_core/cli.py`. Never run two writers
against the same cursor state, or two consumers against the same bot.
