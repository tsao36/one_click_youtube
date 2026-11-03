from pathlib import Path

server_file = Path("api_server.py")
content = server_file.read_text(encoding="utf-8")

target = '    raise HTTPException(status_code=404, detail="Music track not found")'
if target not in content:
    print("ERROR: target string not found")
    exit(1)

code_to_insert = """


# ---------------- OpenOpus Classical Music Endpoints ----------------
import generators.openopus as openopus_module


class OpenOpusImportRequest(BaseModel):
    composer: str
    work: str
    audio_url: str
    epoch: Optional[str] = ""
    genre: Optional[str] = ""
    openopus_id: Optional[str] = ""


@app.get("/api/music/openopus/composers")
def get_openopus_composers(epoch: Optional[str] = None):
    try:
        if epoch and epoch.strip().lower() not in ("all", "popular", ""):
            comps = openopus_module.get_composers_by_epoch(epoch)
        else:
            comps = openopus_module.get_popular_composers()
        return {"composers": comps}
    except Exception as e:
        log.error("Failed to fetch OpenOpus composers: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/openopus/composers/search")
def search_openopus_composers(q: str = Query("")):
    try:
        comps = openopus_module.search_composers(q)
        return {"composers": comps}
    except Exception as e:
        log.error("Failed to search OpenOpus composers: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/openopus/works")
def get_openopus_works(composer_id: str = Query(...), genre: Optional[str] = None):
    try:
        works = openopus_module.get_composer_works(composer_id, genre)
        return {"works": works}
    except Exception as e:
        log.error("Failed to fetch OpenOpus works: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/openopus/works/search")
def search_openopus_works(q: str = Query("")):
    try:
        works = openopus_module.search_works(q)
        return {"works": works}
    except Exception as e:
        log.error("Failed to search OpenOpus works: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/openopus/resolve-audio")
def resolve_openopus_audio(composer: str = Query(...), work: str = Query(...)):
    try:
        candidates = openopus_module.resolve_public_domain_audio(composer, work)
        return {"candidates": candidates}
    except Exception as e:
        log.error("Failed to resolve public domain audio: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/music/openopus/import-work")
def import_openopus_work(req: OpenOpusImportRequest):
    try:
        entry = openopus_module.download_and_ingest_classical_track(
            composer_name=req.composer,
            work_title=req.work,
            audio_url=req.audio_url,
            epoch=req.epoch or "",
            genre=req.genre or "",
            openopus_id=req.openopus_id or "",
        )
        return {"status": "imported", "track": entry}
    except Exception as e:
        log.error("Failed to import OpenOpus work: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/music/openopus/upload-work")
async def upload_openopus_work(
    file: UploadFile = File(...),
    composer: str = Form(...),
    work: str = Form(...),
    epoch: str = Form(""),
    genre: str = Form(""),
    openopus_id: str = Form(""),
):
    try:
        comp_slug = openopus_module.slugify(composer) or "classical"
        work_slug = openopus_module.slugify(work) or "opus"
        target_dir = ROOT / "data" / "music" / "classical" / comp_slug
        target_dir.mkdir(parents=True, exist_ok=True)
        final_mp3 = target_dir / f"{work_slug}.mp3"
        tmp_raw = target_dir / f"upload_tmp_{work_slug}_{file.filename}"

        content = await file.read()
        tmp_raw.write_bytes(content)

        # Convert / normalize to mp3
        try:
            cmd = [
                "ffmpeg", "-y", "-i", str(tmp_raw),
                "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                str(final_mp3)
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except Exception as conv_e:
            log.warning("FFmpeg convert uploaded track fallback: %s", conv_e)
            if tmp_raw.exists():
                tmp_raw.rename(final_mp3)
        finally:
            if tmp_raw.exists():
                try:
                    tmp_raw.unlink()
                except Exception:
                    pass

        # Ingest metadata and duration
        duration = 0.0
        try:
            probe_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(final_mp3)
            ]
            duration = float(subprocess.check_output(probe_cmd, stderr=subprocess.STDOUT).decode("utf-8").strip())
        except Exception:
            pass

        vibe_info = openopus_module.map_classical_to_vibe(epoch, genre, work)
        cat = vibe_info["category"]
        rel_path = final_mp3.relative_to(ROOT / "data" / "music").as_posix()
        size_mb = round(final_mp3.stat().st_size / (1024 * 1024), 2)

        entry = {
            "id": rel_path,
            "name": f"{composer}: {work}",
            "category": cat,
            "category_label": cat.replace("_", " ").title(),
            "filename": rel_path,
            "basename": final_mp3.name,
            "size_mb": size_mb,
            "duration": round(duration, 1),
            "mood": f"Classical {epoch.title()} ({genre.title()})",
            "description": f"Composed by {composer} ({epoch.title()}). Sourced via User Audio Upload & OpenOpus.",
            "energy_level": vibe_info["energy_level"],
            "movement_roles": vibe_info["movement_roles"],
            "tags": ["classical", openopus_module.slugify(composer), openopus_module.slugify(epoch), openopus_module.slugify(genre)],
            "source": "openopus",
            "composer": composer,
            "work": work,
            "epoch": epoch,
            "genre": genre,
            "openopus_id": openopus_id,
            "url": f"/api/music/audio/{rel_path}",
        }

        cat_file = ROOT / "data" / "music" / "catalog.json"
        catalog_data = {"categories": {}, "tracks": []}
        if cat_file.exists():
            try:
                catalog_data = json.loads(cat_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        tracks = [t for t in catalog_data.get("tracks", []) if t.get("filename") != rel_path]
        tracks.append(entry)
        catalog_data["tracks"] = tracks
        cat_file.write_text(json.dumps(catalog_data, indent=2, ensure_ascii=False), encoding="utf-8")

        return {"status": "uploaded", "track": entry}
    except Exception as e:
        log.error("Failed to upload classical work: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
"""

new_content = content.replace(target, target + code_to_insert, 1)
server_file.write_text(new_content, encoding="utf-8")
print("SUCCESS: api_server.py updated with OpenOpus endpoints!")
