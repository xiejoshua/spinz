"""Operator-run scripts for the auxd API package.

Marker file that makes ``scripts`` an importable package so the
catalog-seed generators can be invoked either directly
(``python scripts/generate_seed_csvs.py``) or via the module flag
(``python -m scripts.generate_seed_csvs``) without PYTHONPATH
gymnastics. Individual entry-point scripts add ``apps/api/`` to
:data:`sys.path` at the top of the file as belt-and-suspenders.
"""
