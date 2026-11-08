---
name: math-and-numerics-check
description: Check units, boundaries and reproducibility for numeric values, durations and resource budgets.
---

# Numeric checks

State units explicitly. Prefer timezone-aware UTC timestamps and integer duration
units for session expiry. Check before, at and after a boundary using a controlled
clock rather than sleeping. Derive response durations from the same configuration
as persisted expiry. Test invalid limits and avoid unsupported performance claims.
Use deterministic calculations or standard libraries for formulas; record assumptions
and distinguish a measured value from an estimate.
