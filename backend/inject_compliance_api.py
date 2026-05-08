"""
inject_compliance_api.py
Appends compliance REST API endpoints to main.py
"""
import sys
MAIN_PY = r"C:\caas-dashboard\backend\main.py"

COMPLIANCE_ENDPOINTS = '''

# ═══════════════════════════════════════════════════════════════════════════
#  COMPLIANCE MODULE  --  REST API Endpoints
#  PostgreSQL-backed, 3-month rolling window
# ═══════════════════════════════════════════════════════════════════════════

_PG_COMP = dict(
    host="127.0.0.1", port=5433, dbname="caas_dashboard",
    user="caas_app", password="CaaS@App2024#", connect_timeout=10,
)

def _pg_comp():
    import psycopg2, psycopg2.extras
    return psycopg2.connect(**_PG_COMP, cursor_factory=psycopg2.extras.RealDictCursor)


@app.get("/api/compliance/summary")
def compliance_summary(u=Depends(require_role("admin","operator","viewer"))):
    """KPI cards + donut data for the compliance dashboard."""
    try:
        with _pg_comp() as conn:
            with conn.cursor() as cur:
                # Latest scan totals
                cur.execute("""
                    SELECT total_assets, compliant, warning, non_compliant,
                           scanned_at, triggered_by, status
                    FROM compliance_scans
                    ORDER BY scanned_at DESC LIMIT 1
                """)
                latest = cur.fetchone()

                # Average score from latest scan results
                cur.execute("""
                    SELECT ROUND(AVG(r.score),1) AS avg_score,
                           MAX(r.scanned_at)     AS last_scan
                    FROM compliance_results r
                    JOIN compliance_scans s ON s.id = r.scan_id
                    WHERE s.scanned_at = (SELECT MAX(scanned_at) FROM compliance_scans WHERE status=\'completed\')
                """)
                score_row = cur.fetchone()

                # Trend last 30 days
                cur.execute("""
                    SELECT trend_date, total_assets, compliant, warning,
                           non_compliant, avg_score
                    FROM compliance_trend
                    ORDER BY trend_date DESC LIMIT 30
                """)
                trend = [dict(r) for r in cur.fetchall()]

                # Top failing checks
                cur.execute("""
                    SELECT check_data->\'name\' AS check_name,
                           COUNT(*) AS fail_count
                    FROM compliance_results r,
                         jsonb_array_elements(r.checks) AS check_data
                    WHERE check_data->>\'status\' = \'non_compliant\'
                      AND r.scanned_at >= NOW() - INTERVAL \'7 days\'
                    GROUP BY check_data->\'name\'
                    ORDER BY fail_count DESC LIMIT 8
                """)
                top_failures = [dict(r) for r in cur.fetchall()]

        if latest:
            total = latest["total_assets"] or 0
            comp  = latest["compliant"]    or 0
            warn  = latest["warning"]      or 0
            bad   = latest["non_compliant"] or 0
        else:
            total = comp = warn = bad = 0

        return {
            "total_assets":   total,
            "compliant":      comp,
            "warning":        warn,
            "non_compliant":  bad,
            "compliant_pct":  round(comp / total * 100, 1) if total else 0,
            "warning_pct":    round(warn / total * 100, 1) if total else 0,
            "non_compliant_pct": round(bad / total * 100, 1) if total else 0,
            "avg_score":      float(score_row["avg_score"] or 0) if score_row else 0,
            "last_scan":      str(latest["scanned_at"]) if latest else None,
            "trend":          list(reversed(trend)),
            "top_failures":   top_failures,
        }
    except Exception as ex:
        import traceback
        log.error(f"compliance_summary error: {ex}\\n{traceback.format_exc()}")
        return {"total_assets":0,"compliant":0,"warning":0,"non_compliant":0,
                "compliant_pct":0,"warning_pct":0,"non_compliant_pct":0,
                "avg_score":0,"last_scan":None,"trend":[],"top_failures":[]}


@app.get("/api/compliance/assets")
def compliance_assets(
    status:    str = None,    # compliant | warning | non_compliant
    asset_type: str = None,   # vm | baremetal
    os_family:  str = None,   # windows | linux | other
    vcenter:    str = None,
    search:     str = None,
    page:       int = 1,
    page_size:  int = 50,
    u=Depends(require_role("admin","operator","viewer"))
):
    """Paginated, filterable asset compliance list."""
    import json as _json
    try:
        filters = []
        params  = []

        if status:
            filters.append("r.status = %s");     params.append(status)
        if asset_type:
            filters.append("a.asset_type = %s"); params.append(asset_type)
        if os_family:
            filters.append("a.os_family = %s");  params.append(os_family)
        if vcenter:
            filters.append("a.vcenter ILIKE %s"); params.append(f"%{vcenter}%")
        if search:
            filters.append("(a.hostname ILIKE %s OR a.ip_address ILIKE %s OR a.os_name ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        offset = (page - 1) * page_size

        with _pg_comp() as conn:
            with conn.cursor() as cur:
                # Latest result per asset
                base_sql = f"""
                    WITH latest AS (
                        SELECT DISTINCT ON (r.asset_id) r.*
                        FROM compliance_results r
                        JOIN compliance_scans s ON s.id = r.scan_id
                        WHERE s.status = \'completed\'
                        ORDER BY r.asset_id, r.scanned_at DESC
                    )
                    SELECT
                        a.id, a.hostname, a.ip_address, a.os_name, a.os_version,
                        a.os_family, a.asset_type, a.vcenter, a.cluster,
                        a.hypervisor_host, a.cpu_count, a.memory_gb, a.disk_gb,
                        a.power_state, a.tools_status, a.hw_version,
                        a.environment, a.owner_team, a.last_seen,
                        r.score, r.status AS compliance_status,
                        r.patch_age_days, r.eol_os, r.missing_patches,
                        r.tools_ok, r.hw_version_ok, r.snapshot_ok,
                        r.scanned_at AS last_scanned
                    FROM compliance_assets a
                    JOIN latest r ON r.asset_id = a.id
                    {where}
                """

                # Total count
                cur.execute(f"SELECT COUNT(*) AS cnt FROM ({base_sql}) AS t", params)
                total_count = cur.fetchone()["cnt"]

                # Paged results
                cur.execute(base_sql + " ORDER BY r.score ASC, a.hostname LIMIT %s OFFSET %s",
                            params + [page_size, offset])
                rows = [dict(r) for r in cur.fetchall()]

        # Serialise dates
        for r in rows:
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    r[k] = v.isoformat()

        return {
            "assets":     rows,
            "total":      total_count,
            "page":       page,
            "page_size":  page_size,
            "pages":      (total_count + page_size - 1) // page_size if page_size else 1,
        }
    except Exception as ex:
        log.error(f"compliance_assets error: {ex}")
        return {"assets": [], "total": 0, "page": 1, "page_size": page_size, "pages": 0}


@app.get("/api/compliance/assets/{asset_id}")
def compliance_asset_detail(
    asset_id: int,
    u=Depends(require_role("admin","operator","viewer"))
):
    """Full detail for a single asset: asset info + check breakdown + history + remediations."""
    import json as _json
    try:
        with _pg_comp() as conn:
            with conn.cursor() as cur:
                # Asset info
                cur.execute("SELECT * FROM compliance_assets WHERE id = %s", (asset_id,))
                asset = cur.fetchone()
                if not asset:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(status_code=404, content={"error": "Asset not found"})

                # Latest compliance result with checks
                cur.execute("""
                    SELECT r.*, s.scanned_at AS scan_time
                    FROM compliance_results r
                    JOIN compliance_scans s ON s.id = r.scan_id
                    WHERE r.asset_id = %s AND s.status = \'completed\'
                    ORDER BY r.scanned_at DESC LIMIT 1
                """, (asset_id,))
                latest = cur.fetchone()

                # 90-day score history
                cur.execute("""
                    SELECT DATE(r.scanned_at) AS scan_date, r.score, r.status
                    FROM compliance_results r
                    JOIN compliance_scans s ON s.id = r.scan_id
                    WHERE r.asset_id = %s AND s.status = \'completed\'
                      AND r.scanned_at >= NOW() - INTERVAL \'90 days\'
                    ORDER BY r.scanned_at ASC
                """, (asset_id,))
                history = [dict(r) for r in cur.fetchall()]

                # Open remediations
                cur.execute("""
                    SELECT * FROM compliance_remediations
                    WHERE asset_id = %s AND status IN (\'open\',\'in_progress\')
                    ORDER BY created_at DESC
                """, (asset_id,))
                remediations = [dict(r) for r in cur.fetchall()]

        def _serial(d):
            if d is None:
                return None
            out = {}
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    out[k] = v.isoformat()
                else:
                    out[k] = v
            return out

        checks = latest["checks"] if latest else []
        if isinstance(checks, str):
            checks = _json.loads(checks)

        return {
            "asset":        _serial(dict(asset)),
            "score":        latest["score"]  if latest else None,
            "status":       latest["status"] if latest else None,
            "last_scanned": str(latest["scanned_at"]) if latest else None,
            "checks":       checks,
            "history":      [_serial(r) for r in history],
            "remediations": [_serial(r) for r in remediations],
        }
    except Exception as ex:
        log.error(f"compliance_asset_detail error: {ex}")
        return {"error": str(ex)}


@app.get("/api/compliance/trend")
def compliance_trend(
    days: int = 90,
    u=Depends(require_role("admin","operator","viewer"))
):
    """Daily trend data for charts — up to 90 days."""
    try:
        with _pg_comp() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT trend_date, total_assets, compliant, warning,
                           non_compliant, avg_score
                    FROM compliance_trend
                    WHERE trend_date >= CURRENT_DATE - %s
                    ORDER BY trend_date ASC
                """, (days,))
                rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if hasattr(r.get("trend_date"), "isoformat"):
                r["trend_date"] = r["trend_date"].isoformat()
        return {"trend": rows, "days": days}
    except Exception as ex:
        log.error(f"compliance_trend error: {ex}")
        return {"trend": [], "days": days}


@app.post("/api/compliance/scan")
def trigger_compliance_scan(u=Depends(require_role("admin","operator"))):
    """Trigger a manual compliance scan in background."""
    import threading
    username = u.get("username","?")
    def _scan():
        try:
            from compliance_collector import run_compliance_scan
            run_compliance_scan(triggered_by=username)
        except Exception as ex:
            log.error(f"Manual compliance scan error: {ex}")
    threading.Thread(target=_scan, daemon=True).start()
    return {"ok": True, "message": "Compliance scan triggered — results available in ~2 minutes"}


@app.post("/api/compliance/remediate/{asset_id}")
def create_remediation(
    asset_id: int,
    req: dict = Body(...),
    u=Depends(require_role("admin","operator"))
):
    """Create a remediation task for an asset."""
    username = u.get("username","?")
    check_name = req.get("check_name","")
    action     = req.get("action","Manual remediation required")
    priority   = req.get("priority","medium")
    notes      = req.get("notes","")
    try:
        with _pg_comp() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO compliance_remediations
                        (asset_id, check_name, action, priority, status, created_by, notes)
                    VALUES (%s, %s, %s, %s, \'open\', %s, %s)
                    RETURNING id
                """, (asset_id, check_name, action, priority, username, notes))
                rid = cur.fetchone()["id"]
            conn.commit()
        return {"ok": True, "remediation_id": rid}
    except Exception as ex:
        log.error(f"create_remediation error: {ex}")
        return {"ok": False, "error": str(ex)}


@app.patch("/api/compliance/remediate/{remediation_id}/status")
def update_remediation_status(
    remediation_id: int,
    req: dict = Body(...),
    u=Depends(require_role("admin","operator"))
):
    """Update remediation status: open | in_progress | resolved | dismissed."""
    username   = u.get("username","?")
    new_status = req.get("status","")
    notes      = req.get("notes","")
    if new_status not in ("open","in_progress","resolved","dismissed"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error":"Invalid status"})
    try:
        with _pg_comp() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE compliance_remediations
                    SET status=%s, updated_at=NOW(), notes=COALESCE(NULLIF(%s,\'\'),notes),
                        resolved_at=CASE WHEN %s=\'resolved\' THEN NOW() ELSE resolved_at END,
                        resolved_by=CASE WHEN %s=\'resolved\' THEN %s ELSE resolved_by END
                    WHERE id=%s
                """, (new_status, notes, new_status, new_status, username, remediation_id))
            conn.commit()
        return {"ok": True}
    except Exception as ex:
        return {"ok": False, "error": str(ex)}
'''

content = open(MAIN_PY, encoding="utf-8-sig").read()
if "/api/compliance/summary" in content:
    print("Already injected — skipping")
    sys.exit(0)

with open(MAIN_PY, "a", encoding="utf-8") as f:
    f.write(COMPLIANCE_ENDPOINTS)

print("Compliance API endpoints appended to main.py")
