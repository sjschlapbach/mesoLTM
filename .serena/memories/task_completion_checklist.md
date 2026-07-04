# Task Completion Checklist

When finishing a coding task:

1. **Tests:** `pytest` (add/adjust tests for new behaviour).
2. **Lint + format:** `pylint src/mesoltm examples` and `black --check src examples`.
3. **Types:** `mypy src`.
4. **Update tracking:**
   - Update the relevant **serena memory** if reference facts changed: `mem:codebase_structure` (structure), `mem:code_style_and_conventions` (style/tooling), `mem:suggested_commands` (commands).
   - Append a dated entry to `.ai/PROGRESS.md` — **always**.
   - Add to `.ai/DECISIONS.md` if you made a systematic/non-obvious choice.

See `mem:ai_tracking_system` for how knowledge is split. A `Stop` hook reminds you if work changed but tracking (`.ai/` or `.serena/memories/`) wasn't updated.
