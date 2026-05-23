"""Performance smoke tests.

Tests in this package guard against order-of-magnitude regressions in
hot read paths. Budgets are deliberately generous (in-process Mongo via
mongomock can't model real Atlas latency) so the goal is catching
accidental N+1 queries / missing indexes / sync provider calls landing
on the read path, not micro-benchmarks.
"""
