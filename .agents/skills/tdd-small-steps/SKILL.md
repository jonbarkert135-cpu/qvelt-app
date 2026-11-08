---
name: tdd-small-steps
description: Develop behavior in small increments using failing tests before implementation and focused review.
---

# Small steps

1. Select one milestone and write its observable acceptance criteria.
2. Write a focused failing test before implementing behavior. For security features,
   include malicious inputs and unauthorized access attempts before the happy path.
3. Run the test and inspect why it fails; unrelated setup failures do not prove the
   test exercises the missing behavior. Resolve prerequisites before continuing.
4. Implement the smallest coherent change, rerun the test and inspect the result.
5. Refactor only while the relevant tests pass; add regression tests for defects.
6. Finish with the applicable full suite, documentation and an ADR for decisions
   that affect the architecture. Do not expand into an unrelated milestone.
