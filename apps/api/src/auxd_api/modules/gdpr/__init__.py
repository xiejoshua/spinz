"""GDPR module — audit log, export worker, deletion bookkeeping (T154).

Houses every cross-cutting GDPR / compliance surface that isn't already
owned by an existing module (the deletion cascade still lives in
``modules/users/workers.py`` because it predates this namespace).

Public Documents:

* :class:`auxd_api.modules.gdpr.models.GdprAuditLog` — append-only audit
  row for every export-requested / export-completed / deletion-scheduled
  / deletion-completed / deletion-canceled event. Registered in
  :data:`auxd_api.db.ALL_DOCUMENT_MODELS`.
"""
