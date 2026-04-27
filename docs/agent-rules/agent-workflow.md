# Agent Workflow Rule

## Goal

Optimize for fast, safe progress with minimal interruption.

## Operating Principles

1. Prefer action over interruption.
2. Use the most reasonable default when the choice is low risk and reversible.
3. Ask the user only when a decision is high risk, materially ambiguous, or would change the direction of the task.
4. When asking, ask all blocking questions at once.
5. During execution, avoid repeated stop-and-go confirmations.
6. At the end, summarize what was done, which defaults were used, and which risks remain.

## Risk Tiers

### Low Risk
Proceed automatically for tasks like:
- Reading, searching, and analyzing files
- Local refactoring, renaming, formatting
- Adding tests, comments, and docs
- Implementing small reversible changes
- Running tests and fixing clear failures

**Behavior**: Use sensible defaults, keep moving, do not interrupt the user.

### Medium Risk
Prefer to resolve these in a single upfront batch before execution:
- Multi-file or multi-module changes
- Design choices with multiple reasonable options
- Style, naming, structure, or output-format preferences
- Changes that affect behavior but remain reversible

**Behavior**: Ask one grouped set of questions, include recommended defaults, continue once the user answers.

### High Risk
Stop and confirm before proceeding with:
- Deleting files, directories, or data
- Overwriting important files or making broad irreversible changes
- Changing production configs, secrets, credentials, databases, or remote deployments
- Pushing, releasing, or performing externally visible operations
- Any action with high cost or difficult recovery if wrong

**Behavior**: Explain the risk clearly, propose the safest option, wait for explicit confirmation.

## Batch Question Policy

When confirmation is needed:
- Do not ask one question at a time
- Collect all blocking issues first
- Present them in a single list
- Provide clear options for each question
- Include a recommended default for each item
- If a question does not block the main flow, choose the default and note it instead of asking

**Suggested question format**:
- Decision needed
- Recommended default
- Available options
- What happens if the user does not choose

## Planning and Execution Flow

### Before Execution
- Assess the risk level
- Produce a short plan
- If there are medium-risk decisions, ask them in one batch
- If there are no high-risk blockers, begin execution

### During Execution
- Keep the work moving continuously
- Use defaults for low-risk uncertainty
- Stop only for high-risk blockers
- If blocked, try 1-2 sensible self-resolution attempts before asking the user

### After Execution
- Report what was completed
- List assumptions and defaults used
- Call out any remaining risks or follow-up decisions
- Avoid repeated interim summaries

## Default-Value Policy

When the choice does not affect safety, correctness, or the user's stated goal, prefer common defaults for:
- Naming style
- File structure
- Testing approach
- Documentation updates
- Implementation details

If a default would materially alter the result, move it into the batch question phase.

## Interaction Style

- Fewer interruptions, more progress
- Batch all necessary questions
- Plan first, execute continuously
- Interrupt only for high-risk decisions
- Summarize once at the end

## Short Version

Default to progress. Auto-handle low-risk work. Batch medium-risk questions before execution. Stop only for high-risk actions. Keep execution continuous and report at the end.
