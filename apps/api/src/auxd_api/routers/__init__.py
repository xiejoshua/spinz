"""HTTP routers for the auxd API.

The versioned API surface is assembled by :mod:`auxd_api.routers.v1`
into a single :class:`fastapi.APIRouter` mounted at ``/api/v1`` by
:mod:`auxd_api.main`. Feature module routers attach to that aggregator
as they land (T031+).
"""
