"""Web layer — Flask API + Svelte frontend for the LangMine curation UI.

Sits at the outermost edge. Routes talk to domain ports (never directly
to adapters). Domain code never depends on this module.

app.py:     Flask factory with dependency injection (only file allowed to import adapters)
server.py:  CLI entry point (argparse → create_production_app → app.run)
routes.py:  All REST endpoints and SSE streaming
"""
