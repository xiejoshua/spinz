"""Discover surface — feature 003 / Discover-rehaul.

Two endpoints power the sectioned editorial homepage at ``/discover``:

* ``GET /api/v1/discover/popular-this-week`` — top albums by log count
  in the trailing 7 days, excluding the viewer's already-logged albums.
* ``GET /api/v1/discover/from-follows`` — albums logged or reviewed by
  the viewer's follow graph, deduped and annotated with the most
  recent activity from a followee.

Both are cached in Redis (fail-open) and rate-limited per-user.
"""
