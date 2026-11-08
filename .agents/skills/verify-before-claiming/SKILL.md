---
name: verify-before-claiming
description: Verify changed behavior with fresh commands before reporting implementation or test success.
---

# Verification

1. Identify the behavior changed and a check that would detect a broken implementation.
2. Run targeted tests after the final edit, then the repository's applicable checks.
3. Inspect exit codes and test counts. Distinguish failures, skips and unrun checks.
4. For database isolation, test against PostgreSQL with a role that cannot bypass RLS.
   SQLite and mocked SQL are not evidence that PostgreSQL policies work.
5. Inspect the final diff for secrets, generated files and unrelated changes.
6. Report exact commands, observed results, limitations and remaining work. Do not
   equate local success with deployed behavior, a merged PR or published configuration.
