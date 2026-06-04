"""Domain layer — pure business logic with zero I/O dependencies.

Contains ports (abstract interfaces), models (dataclasses), and the
classifier (i+1 engine). Depends only on itself — never reaches out to
external systems, the web layer, or language-specific packages.
"""
