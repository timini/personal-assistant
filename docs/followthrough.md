# Drive obligations to completion

This is the canonical operating workflow for PA sessions and the configured scheduled
check-ins. It supersedes capture-only/Inbox Zero workflows.

## Session and scheduled review

1. Get local time. Reuse today's wellbeing answer; do not repeatedly ask when the user
   already said he is ill or wants triage only.
2. Read `uv run pa-core followthrough --json` (`--energy unwell` when appropriate).
   This command is read-only. Include In Progress and Waiting, and inspect the
   bounded reconciliation queue and parked deadline conflicts. Source failure
   means NOT CHECKED, not no work/no reply. Do not dump the backlog.
3. Before nudging, read relevant source threads including archive, check receipts,
   acknowledgements and existing authorisations. Prepare useful work yourself.
4. Recommend ONE concrete next step, with the draft/form/evidence ready. Ask only
   for the decision or small action that needs the user. Respect current task scope.
   When sick, protect his energy; continue safe assistant-owned preparation.
5. Keep the chosen task in focus. After two stalled delivered check-ins, change
   approach: reduce the step, prepare more, or ask one blocker question. Never
   interpret silence as approval, completion, or permission to drop a task.
6. After delivering a prompt, record it using `pa-core followthrough
   --record-task <id> --slot <date-am|date-pm> --progress <last-progress>`.
   Add `--select` only when the user actually chooses it. Use `--snooze-until` only for
   an explicit deferral. Do not record a prompt that was not delivered.
   `already_prompted` suppresses another prompt in that slot unless new material
   deadline risk appears. Do not replay missed slots after a late wakeup.

Scheduled reviews follow the user’s configured schedule and delivery channel. Weekends focus on family
and personal work unless a genuine work deadline is at risk. After a live review,
record the equivalent slot so the scheduled review will not duplicate it. Do not
send to third parties without applicable explicit approval; prepare the exact
chase first. Prior approval for that action persists. No automatic payments,
orders, HR decisions, or new commitments.

## Every captured obligation needs a next step

Before archiving actionable mail: cross-reference existing tasks, update the
outcome, next action, next owner and next review. Save the source/evidence link.
A title plus copied email is not sufficient. Calendar checks still apply.
Informational newsletters do not need invented obligations.

Use `pa_notion.tasks.update_task` with `outcome`, `next_action`, `owner`,
`next_review`, `blocker`, `deadline_basis`, `external_deadline`, `last_progress`.
Owners are Assistant, the user, External. Dates use ISO dates/timestamps. Next owner
means the person doing the NEXT action: checking for an external reply belongs to
Assistant even though the underlying dependency is external.

Keep a verified External Deadline separate from the existing Due Date, which may
be a personal preparation target. Preserve uncertain old dates and reconcile
rather than silently moving them. Last Progress is only for substantive progress
(e.g. verified submission, received response, completed preparation), not reading
or editing notes. Never fabricate historical progress/closure dates.

For a new waiting thread, default review after 3 business days for service/admin
chases or 5 business days for professional outreach, shortened when necessary to
protect a verified deadline. These are internal review dates, not promises from
the other party. When metadata is uncertain, schedule an assistant evidence
review; do not bounce a large questionnaire to the user. Parked/Someday stays parked.
Read relevant unchecked child/checklist blocks before calling a parent complete.

## Completion, disposition and metrics

Sent is not necessarily submitted; submitted is not accepted; accepted is not
necessarily paid. Define completion for the actual obligation. Ask for a short
batch confirmation when evidence shows completed admin. Explicit user completion
is sufficient; don't ask twice. Use Done/Completed for confirmed completion;
Discarded with Cancelled, Superseded or Migrated for work dropped or moved.
“Close” after a list of expired tasks is closure authorisation, not proof that
past medical treatment, approvals or payments occurred. Record that distinction.

Use update_task(status=..., closure_reason=...) so closure timestamps are applied. Record log events with details.task_id.
Captured, archived, prepared, submitted, waiting, completed and discarded are
separate outcomes. Legacy batch logs without task IDs are not exact task counts.
Never manufacture improved throughput by archiving email or deleting obligations.

## Failure handling

If authentication or a source is unavailable, identify exactly what was not
checked, keep the obligation open, prepare independent work, and surface the
smallest unblock action. Don't repeatedly request the same login or re-send after
an uncertain result: verify Sent/receipt first. A scheduler registration is not
evidence of a successful scheduled run; inspect its run history when checking
coverage. Keep sensitive evidence in its original private source.
