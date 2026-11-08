from pathlib import Path

api_path = Path("api_server.py")
content = api_path.read_text(encoding="utf-8")

old_code = '''    try:
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)
        return {"status": "ok", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load fact check report: {e}")'''

new_code = '''    try:
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)
        return {"status": "ok", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load fact check report: {e}")


@app.post("/api/projects/{project_id}/script/fact-check")
async def run_script_fact_check_endpoint(project_id: str, auto_patch: bool = True):
    """Run an on-demand fact & numerical consistency check on the script."""
    p = get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    from core.fact_checker import verify_script_facts
    try:
        report = verify_script_facts(p, auto_patch=auto_patch)
        return {"status": "ok", "report": report}
    except Exception as e:
        log.exception("Script fact check failed for project %s", project_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/script/fact-check")
async def get_script_fact_check_endpoint(project_id: str):
    """Get the latest script fact check report for the project."""
    p = get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    report_file = p.path("script", "script_fact_check_report.json")
    if not report_file.exists():
        scr_file = p.path("script", "script.json")
        if scr_file.exists():
            try:
                from core.fact_checker import verify_script_facts
                report = verify_script_facts(p, client=False, auto_patch=False)
                return {"status": "ok", "report": report}
            except Exception:
                pass
        return {"status": "not_found", "report": None}

    try:
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)
        return {"status": "ok", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load script fact check report: {e}")'''

assert old_code in content, "old_code not found in api_server.py"
content = content.replace(old_code, new_code)
api_path.write_text(content, encoding="utf-8")
print("Successfully added script fact-check endpoints to api_server.py!")
