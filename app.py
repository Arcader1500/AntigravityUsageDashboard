"""Antigravity Telemetry Control — FastAPI Entry Point.

Run: python app.py (or run.ps1 / uvicorn app:app --port 8501)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Annotated

import pandas as pd
import uvicorn
from fastapi import FastAPI, Form, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agy_dash import config as cfgmod
from agy_dash import snapshots
from agy_dash.source import SourceError
from agy_dash.ui import common, state, views

APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "agy_dash" / "ui" / "templates"
STATIC_DIR = APP_DIR / "agy_dash" / "ui" / "static"

app = FastAPI(title="Antigravity Telemetry Control", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Register template filters
templates.env.filters["fmt_tokens"] = common.fmt_tokens
templates.env.filters["fmt_money"] = common.fmt_money
templates.env.filters["fmt_pct"] = common.fmt_pct


def _check_csrf(hx_request: str | None) -> None:
    if not hx_request:
        raise HTTPException(status_code=400, detail="Missing required HX-Request header")


def _get_context_and_filters(request: Request):
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    entries = state.load_catalog()
    model_ids = [e.model_id for e in entries]
    query_params = dict(request.query_params)
    raw_views = request.query_params.getlist("view")
    if raw_views:
        query_params["view"] = raw_views[0]
    if request.cookies.get("agy_theme"):
        query_params.setdefault("theme", request.cookies.get("agy_theme"))
    filters = state.parse_filters(query_params, cfg, usage, model_ids)
    ctx = state.build_context(cfg, usage, entries, filters, runner=state.get_runner(cfg))
    return cfg, usage, entries, model_ids, query_params, filters, ctx


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    cfg = cfgmod.get_config()
    try:
        usage = state.load_usage(cfg)
    except SourceError as exc:
        return templates.TemplateResponse(request, "error.html", {
            "request": request, "message": str(exc),
            "hint": f"Verify brain_root ({cfg.brain_root}) and extractor_script ({cfg.extractor_script}) in config/config.json.",
        }, status_code=500)

    entries = state.load_catalog()
    model_ids = [e.model_id for e in entries]
    query_params = dict(request.query_params)
    raw_views = request.query_params.getlist("view")
    if raw_views:
        query_params["view"] = raw_views[0]
    if request.cookies.get("agy_theme"):
        query_params.setdefault("theme", request.cookies.get("agy_theme"))
    filters = state.parse_filters(query_params, cfg, usage, model_ids)

    try:
        ctx = state.build_context(cfg, usage, entries, filters, runner=state.get_runner(cfg))
    except state.PricingError as exc:
        return templates.TemplateResponse(request, "error.html", {"request": request, "message": str(exc)}, status_code=400)

    deep_data = state.load_deep(str(cfg.brain_root))

    if filters.view == "command":
        vm = views.build_command_view(ctx, deep_data)
    elif filters.view == "sessions":
        kind_param = query_params.get("kind")
        kind_list = [kind_param] if kind_param else None
        try:
            top_n = int(query_params.get("top", 25))
        except (ValueError, TypeError):
            top_n = 25
        vm = views.build_sessions_view(
            ctx, deep_data, kind_sel=kind_list,
            top_n=top_n,
            search=query_params.get("search"),
        )
    else:
        lab_params = dict(query_params)
        if "chosen_models" in request.query_params:
            lab_params["chosen_models"] = request.query_params.getlist("chosen_models")
        vm = views.build_economics_view(ctx, query_params, lab_params)

    runner_state = ctx.runner.state if ctx.runner else None
    sync_data = views.build_sync_drawer(ctx)

    return templates.TemplateResponse(request, "base.html", {
        "request": request, "ctx": ctx, "filters": filters,
        "model_ids": model_ids, "vm": vm, "runner_state": runner_state,
        "sync_data": sync_data,
    })


@app.get("/partials/forecast-stage", response_class=HTMLResponse)
def forecast_stage(request: Request):
    cfg, usage, entries, model_ids, query_params, filters, ctx = _get_context_and_filters(request)
    vm = views.build_economics_view(ctx, query_params, query_params)
    return templates.TemplateResponse(request, "partials/forecast_stage.html", {"request": request, "ctx": ctx, "vm": vm})


@app.get("/partials/lab-stage", response_class=HTMLResponse)
def lab_stage(request: Request):
    cfg, usage, entries, model_ids, query_params, filters, ctx = _get_context_and_filters(request)
    lab_params = dict(query_params)
    if "chosen_models" in request.query_params:
        lab_params["chosen_models"] = request.query_params.getlist("chosen_models")
    vm = views.build_economics_view(ctx, query_params, lab_params)
    return templates.TemplateResponse(request, "partials/lab_stage.html", {"request": request, "ctx": ctx, "vm": vm})


@app.get("/partials/session-detail/{session_id}", response_class=HTMLResponse)
def session_detail(request: Request, session_id: str):
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    entries = state.load_catalog()
    query_params = dict(request.query_params)
    if request.cookies.get("agy_theme"):
        query_params.setdefault("theme", request.cookies.get("agy_theme"))
    filters = state.parse_filters(query_params, cfg, usage, [e.model_id for e in entries])
    ctx = state.build_context(cfg, usage, entries, filters, runner=None)
    deep_data = state.load_deep(str(cfg.brain_root))
    detail = views.build_session_detail(ctx, deep_data, session_id)
    if not detail:
        return HTMLResponse("<p style='color:var(--signal-rose); padding:1rem;'>Session not found.</p>", status_code=404)
    return templates.TemplateResponse(request, "partials/session_detail.html", {"request": request, "detail": detail})


@app.post("/api/refresh", response_class=HTMLResponse)
def refresh_scan(request: Request, scope: str | None = None, hx_request: Annotated[str | None, Header()] = None):
    _check_csrf(hx_request)
    if scope == "deep":
        state.DEEP_CACHE.clear()
    else:
        state.clear_all_caches()
    return index(request)


@app.post("/api/snapshots/ingest", response_class=HTMLResponse)
def save_snapshot(request: Request, hx_request: Annotated[str | None, Header()] = None):
    _check_csrf(hx_request)
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    try:
        conn = snapshots.connect(cfg.db_path)
        try:
            info = snapshots.ingest(conn, usage)
            cnt = snapshots.counts(conn)
        finally:
            conn.close()
        return HTMLResponse(f"<span style='color:var(--signal-emerald);'>Snapshot recorded: {info['sessions']} sessions ({cnt['runs']} total runs).</span>")
    except Exception as exc:
        return HTMLResponse(f"<span style='color:var(--signal-rose);'>Snapshot failed: {exc}</span>", status_code=500)


@app.post("/api/jobs/start", response_class=HTMLResponse)
def start_job(request: Request, report: Annotated[str, Form()] = "all", hx_request: Annotated[str | None, Header()] = None):
    _check_csrf(hx_request)
    cfg = cfgmod.get_config()
    runner = state.get_runner(cfg)
    runner.start(report)
    return templates.TemplateResponse(request, "partials/job_status.html", {"request": request, "runner_state": runner.state})


@app.get("/api/jobs/status", response_class=HTMLResponse)
def job_status(request: Request):
    cfg = cfgmod.get_config()
    runner = state.get_runner(cfg)
    runner.poll()
    return templates.TemplateResponse(request, "partials/job_status.html", {"request": request, "runner_state": runner.state})


@app.get("/api/export/daily.csv")
def export_daily():
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    buf = io.StringIO()
    usage.daily.to_csv(buf, index=False)
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=antigravity_daily.csv"})


@app.get("/api/export/sessions.csv")
def export_sessions():
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    buf = io.StringIO()
    usage.sessions.to_csv(buf, index=False)
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=antigravity_sessions.csv"})


@app.get("/api/export/forecast.csv")
def export_forecast():
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    values = usage.daily["total"].to_numpy(dtype=float) if not usage.daily.empty else []
    fc = views.stats.run_forecast("Bootstrap resampling", values, 30, last_date=usage.daily["date"].max() if not usage.daily.empty else None)
    buf = io.StringIO()
    fc.to_frame().to_csv(buf, index=False)
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=antigravity_forecast.csv"})


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8501, reload=True)
