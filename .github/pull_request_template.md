## Summary
<!-- What does this PR do? 1-3 bullet points -->

## Type of change
- [ ] Bug fix
- [ ] New feature / phase deliverable
- [ ] Refactor
- [ ] Tests / CI
- [ ] Documentation

## Test plan
<!-- How was this tested? -->
- [ ] `uv run pytest tests/ -q` passes
- [ ] `uv run ruff check src/ tests/ scripts/` passes
- [ ] Tested manually: <!-- describe -->

## Domain checklist (if touching estimation logic)
- [ ] Monetary values use `Decimal`, not `float`
- [ ] Scope types use canonical strings (ACT, AWP, FW, SM, WW, Baffles, RPG)
- [ ] No hardcoded file paths — uses `src/config.py` settings
- [ ] No data/ directory files committed

## Notes for reviewer
<!-- Anything specific you want Claude or a human reviewer to focus on? -->
