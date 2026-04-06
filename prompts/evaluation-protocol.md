# Evaluation Protocol

Before reporting your results, you MUST run this self-evaluation. This is mandatory — no exceptions.

## Self-Evaluation Checklist

After completing your work but BEFORE writing your output_data or printing your summary, evaluate your own output:

### 1. Task Alignment Check

Ask yourself:
- Did I address the actual task, or did I drift to a related topic?
- Does my output match what the task description requested?
- If the task specified a format, did I follow it?

Score: **aligned** / **partially_aligned** / **misaligned**

If misaligned, STOP and redo the work before reporting.

### 2. Completeness Check

Ask yourself:
- Did I address every requirement in the task description?
- Are there any parts I skipped or left incomplete?
- If I created subtasks, do they cover the full scope?

Score: **complete** / **partial** / **incomplete**

If incomplete, either finish the work or explicitly document what's missing and why in your output.

### 3. Accuracy Check

Ask yourself:
- Are the facts in my output correct (to the best of my knowledge)?
- Did I verify any claims I'm making?
- Are the data values, names, and references accurate?
- Did I distinguish between facts and assumptions?

Score: **verified** / **likely_correct** / **uncertain**

If uncertain, flag specific uncertain items in your output with confidence scores.

### 4. Quality Check

Ask yourself:
- Is my output well-organized and easy to understand?
- Is the level of detail appropriate (not too sparse, not too verbose)?
- Would another agent be able to act on my output without confusion?
- Did I follow the Output Format specified in my agent prompt?

Score: **high** / **acceptable** / **low**

If low, restructure your output before reporting.

### 5. Side Effects Check

Ask yourself:
- Did I create any unexpected subtasks or data?
- Did I modify anything outside my task scope?
- Are there any unintended consequences of my work?
- Did I leave any temporary data that should be cleaned up?

Score: **clean** / **minor_side_effects** / **significant_side_effects**

If significant side effects, document them in your output.

## Evaluation Summary

Include this evaluation in your output_data under the `_evaluation` key:

```json
{
  "type": "agent_output",
  "agent": "{your_agent_id}",
  "task_id": "{task_id}",
  "payload": {
    "...your actual output..."
  },
  "_evaluation": {
    "task_alignment": "aligned",
    "completeness": "complete",
    "accuracy": "verified",
    "quality": "high",
    "side_effects": "clean",
    "notes": "Optional notes about the evaluation"
  }
}
```

## When to Flag for Review

If ANY of these conditions are true, set your task status to `review` instead of `completed`:
- Completeness is `partial` or `incomplete`
- Accuracy is `uncertain`
- Quality is `low`
- Side effects are `significant_side_effects`
- Task alignment is `partially_aligned` or `misaligned`

Tasks in `review` status will be picked up by the Auditor for deeper inspection.

## Rules

1. **Never skip evaluation** — Even if you're confident, run through the checklist
2. **Be honest** — Inflating your scores helps no one; the Auditor will catch discrepancies
3. **Fix what you can** — If evaluation reveals fixable issues, fix them before reporting
4. **Document what you can't fix** — If evaluation reveals issues you can't resolve, document them clearly
5. **The _evaluation key is mandatory** — Every output_data MUST include it
