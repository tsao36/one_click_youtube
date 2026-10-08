"""YouTube Data API v3 uploader and OAuth manager for local-first video generation.

Supports one-click uploads to user's YouTube channel (e.g. @tsao36),
automatic chapter timestamp generation, OAuth credentials flow, and progress tracking.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from core.config import DATA_DIR, YOUTUBE_DIR, load_settings
from core.logging_setup import log
from core.project_manager import Project

# Standard scopes for uploading videos, setting thumbnails, and reading channel info
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CLIENT_SECRETS_FILE = YOUTUBE_DIR / "client_secrets.json"
TOKEN_FILE = YOUTUBE_DIR / "token.json"

# In-memory tracking for OAuth flow and active uploads
_auth_lock = threading.Lock()
_auth_state: dict[str, Any] = {
    "status": "idle",  # idle | in_progress | success | error
    "message": "",
    "started_at": None,
    "completed_at": None,
}

_upload_lock = threading.Lock()
active_uploads: dict[str, dict[str, Any]] = {}


def ensure_youtube_dir() -> Path:
    """Ensure directory for youtube credentials exists."""
    YOUTUBE_DIR.mkdir(parents=True, exist_ok=True)
    return YOUTUBE_DIR


def get_client_secrets_path() -> Optional[Path]:
    """Return path to client_secrets.json if it exists."""
    if CLIENT_SECRETS_FILE.exists() and CLIENT_SECRETS_FILE.stat().st_size > 10:
        return CLIENT_SECRETS_FILE
    # Also check ROOT directory for client_secrets.json
    root_secrets = DATA_DIR.parent / "client_secrets.json"
    if root_secrets.exists() and root_secrets.stat().st_size > 10:
        return root_secrets
    return None


def save_client_secrets_data(data: dict | str) -> bool:
    """Save client secrets JSON to data/youtube/client_secrets.json."""
    ensure_youtube_dir()
    if isinstance(data, str):
        parsed = json.loads(data)
    else:
        parsed = data

    # Verify standard Google OAuth client structure
    if "installed" not in parsed and "web" not in parsed:
        raise ValueError("Invalid client secrets JSON: missing 'installed' or 'web' client configuration.")

    CLIENT_SECRETS_FILE.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    log.info("Saved YouTube client_secrets.json to %s", CLIENT_SECRETS_FILE)
    return True


def get_credentials() -> Optional[Credentials]:
    """Load valid credentials or refresh them if expired."""
    ensure_youtube_dir()
    if not TOKEN_FILE.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            log.info("YouTube token expired. Refreshing token...")
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            log.info("YouTube token refreshed successfully.")
        return creds if creds and creds.valid else None
    except Exception as e:
        log.warning("Failed to load or refresh YouTube credentials: %s", e)
        return None


def disconnect_youtube() -> bool:
    """Remove stored token.json to disconnect channel."""
    if TOKEN_FILE.exists():
        try:
            TOKEN_FILE.unlink()
            log.info("Disconnected YouTube credentials (removed %s)", TOKEN_FILE)
            return True
        except Exception as e:
            log.error("Failed to remove token file: %s", e)
            return False
    return True


def get_youtube_service() -> Optional[Resource]:
    """Build and return an authorized YouTube Resource object."""
    creds = get_credentials()
    if not creds:
        return None
    try:
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        log.error("Failed to build YouTube service: %s", e)
        return None


_last_channel_error: Optional[dict[str, Any]] = None


def get_channel_info() -> Optional[dict[str, Any]]:
    """Retrieve authenticated channel profile (title, handle, avatar, subscriber count)."""
    global _last_channel_error
    service = get_youtube_service()
    if not service:
        return None

    try:
        response = service.channels().list(
            part="snippet,statistics,contentDetails",
            mine=True
        ).execute()

        _last_channel_error = None
        items = response.get("items", [])
        if not items:
            return None

        ch = items[0]
        snippet = ch.get("snippet", {})
        stats = ch.get("statistics", {})

        handle = snippet.get("customUrl", "")
        if handle and not handle.startswith("@"):
            handle = f"@{handle}"

        return {
            "channel_id": ch.get("id"),
            "title": snippet.get("title", ""),
            "handle": handle,
            "description": snippet.get("description", ""),
            "avatar_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            "subscriber_count": stats.get("subscriberCount", "0"),
            "video_count": stats.get("videoCount", "0"),
            "view_count": stats.get("viewCount", "0"),
        }
    except HttpError as e:
        err_str = str(e)
        log.warning("HttpError fetching YouTube channel info: %s", err_str)
        import re
        m = re.search(r"https://console\.developers\.google\.com/apis/api/youtube\.googleapis\.com/overview\?project=\d+", err_str)
        enable_url = m.group(0) if m else "https://console.cloud.google.com/apis/library/youtube.googleapis.com"
        _last_channel_error = {
            "type": "api_not_enabled" if ("accessNotConfigured" in err_str or "has not been used in project" in err_str or "is disabled" in err_str) else "http_error",
            "message": "YouTube Data API v3 has not been enabled in your Google Cloud Project." if ("accessNotConfigured" in err_str or "has not been used in project" in err_str or "is disabled" in err_str) else err_str,
            "enable_url": enable_url,
            "status_code": getattr(e.resp, 'status', 403),
            "details": err_str,
        }
        return None
    except Exception as e:
        log.warning("Failed to fetch YouTube channel info: %s", e)
        _last_channel_error = {
            "type": "general_error",
            "message": str(e),
            "enable_url": None,
        }
        return None


def get_youtube_status() -> dict[str, Any]:
    """Get the aggregate YouTube connection status."""
    settings = load_settings().get("youtube", {})
    target_channel = settings.get("channel_handle", "@tsao36")
    target_url = settings.get("channel_url", "https://www.youtube.com/@tsao36")

    secrets_path = get_client_secrets_path()
    has_secrets = secrets_path is not None

    channel_info = None
    is_authenticated = False

    creds = get_credentials()
    if creds and creds.valid:
        is_authenticated = True
        channel_info = get_channel_info()

    with _auth_lock:
        auth_status = dict(_auth_state)

    is_matched_target = False
    if channel_info and channel_info.get("handle"):
        is_matched_target = channel_info["handle"].lower() == target_channel.lower()

    cfg = load_settings().get("youtube", {})
    return {
        "is_configured": has_secrets,
        "is_authenticated": is_authenticated,
        "channel": channel_info,
        "channel_error": _last_channel_error,
        "target_channel": target_channel,
        "target_channel_url": target_url,
        "is_matched_target": is_matched_target,
        "auth_state": auth_status,
        "token_file_exists": TOKEN_FILE.exists(),
        "client_secrets_path": str(secrets_path) if secrets_path else None,
        "default_privacy": cfg.get("default_privacy", "public"),
        "default_category_id": cfg.get("default_category_id", "28"),
    }


_active_flow: Optional[InstalledAppFlow] = None
_auth_server: Optional[HTTPServer] = None
_auth_redirect_uri: str = ""


def get_free_port(preferred: int = 8090) -> int:
    """Find an open TCP port on localhost for OAuth redirect."""
    for p in [preferred, 8091, 8092, 8095, 8888]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", p))
                return s.getsockname()[1]
        except Exception:
            continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to receive Google OAuth 2.0 authorization code redirect."""

    def log_message(self, format, *args):
        # Suppress standard noisy access logs
        pass

    def do_GET(self):
        global _auth_state, _active_flow
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        qs = urllib.parse.parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        error = qs.get("error", [None])[0]

        if error:
            with _auth_lock:
                _auth_state = {
                    "status": "error",
                    "message": f"Google authorization error: {error}",
                    "completed_at": datetime.now().isoformat(),
                }
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h1>Authorization Failed</h1><p>{error}</p>".encode("utf-8"))
            return

        if code and _active_flow:
            try:
                _active_flow.fetch_token(code=code)
                TOKEN_FILE.write_text(_active_flow.credentials.to_json(), encoding="utf-8")
                ch_info = get_channel_info()
                ch_handle = ch_info.get("handle", "@tsao36") if ch_info else "@tsao36"
                ch_title = ch_info.get("title", "tsao36") if ch_info else "tsao36"

                with _auth_lock:
                    _auth_state = {
                        "status": "success",
                        "message": f"Successfully authorized with channel: {ch_title} ({ch_handle})",
                        "completed_at": datetime.now().isoformat(),
                    }

                success_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>YouTube Connected</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #080d16; color: #fff; text-align: center; padding: 60px 20px; }}
    .box {{ background: #0f172a; border: 1px solid #1e3a8a; border-radius: 12px; max-width: 500px; margin: 0 auto; padding: 36px 24px; box-shadow: 0 10px 40px rgba(0,0,0,0.8); }}
    h1 {{ color: #34d399; margin-bottom: 8px; font-size: 24px; }}
    p {{ color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 8px 0; }}
    .badge {{ display: inline-block; background: #064e3b; color: #34d399; font-weight: 700; padding: 6px 14px; border-radius: 6px; margin: 16px 0; border: 1px solid #059669; }}
  </style>
</head>
<body>
  <div class="box">
    <div style="font-size: 52px; margin-bottom: 12px;">🎉</div>
    <h1>Authorization Successful!</h1>
    <div class="badge">Connected: {ch_title} ({ch_handle})</div>
    <p>Your Google YouTube credentials have been safely verified and stored.</p>
    <p style="color: #60a5fa; font-weight: 600; margin-top: 18px;">You can now close this tab and return to the AI Video Creator dashboard.</p>
  </div>
</body>
</html>"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(success_html.encode("utf-8"))
                log.info("YouTube OAuth callback successful for channel %s (%s)", ch_title, ch_handle)
            except Exception as e:
                log.error("Failed to exchange OAuth token: %s", e)
                with _auth_lock:
                    _auth_state = {
                        "status": "error",
                        "message": f"Token exchange failed: {str(e)}",
                        "completed_at": datetime.now().isoformat(),
                    }
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<h1>Authorization Error</h1><p>{str(e)}</p>".encode("utf-8"))
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>No authorization code received</h1>")


def start_oauth_flow() -> dict[str, Any]:
    """Trigger the local OAuth login flow, start callback server, and return the auth URL."""
    global _active_flow, _auth_server, _auth_redirect_uri, _auth_state
    secrets_path = get_client_secrets_path()
    if not secrets_path:
        return {"status": "error", "message": "Missing client_secrets.json. Upload credentials first."}

    # If there's an existing listener running, close it
    if _auth_server:
        try:
            _auth_server.server_close()
        except Exception:
            pass

    port = get_free_port(8090)
    _auth_redirect_uri = f"http://localhost:{port}/"

    try:
        ensure_youtube_dir()
        flow = InstalledAppFlow.from_client_secrets_file(
            str(secrets_path),
            SCOPES,
            redirect_uri=_auth_redirect_uri
        )
        _active_flow = flow

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )

        with _auth_lock:
            _auth_state = {
                "status": "in_progress",
                "message": "Waiting for Google login...",
                "auth_url": auth_url,
                "port": port,
                "started_at": datetime.now().isoformat(),
                "completed_at": None,
            }

        server = HTTPServer(("localhost", port), OAuthCallbackHandler)
        _auth_server = server

        def _serve_worker():
            try:
                server.timeout = 300  # 5 minutes
                server.handle_request()
            except Exception as ex:
                log.warning("OAuth server listener error: %s", ex)
            finally:
                try:
                    server.server_close()
                except Exception:
                    pass

        thread = threading.Thread(target=_serve_worker, daemon=True)
        thread.start()

        # Attempt standard OS browser open
        try:
            webbrowser.open(auth_url, new=1)
        except Exception as e:
            log.warning("Could not auto-open browser via python: %s", e)

        return {
            "status": "started",
            "auth_url": auth_url,
            "port": port,
            "message": "Authorization started. Open the Google Sign-in URL to complete connection.",
        }

    except Exception as e:
        log.error("Failed to start OAuth flow: %s", e)
        with _auth_lock:
            _auth_state = {
                "status": "error",
                "message": f"Failed to start OAuth: {str(e)}",
                "completed_at": datetime.now().isoformat(),
            }
        return {"status": "error", "message": str(e)}


def submit_auth_code(code_or_url: str) -> dict[str, Any]:
    """Allow manually pasting redirected URL or authorization code if localhost callback is blocked."""
    global _active_flow, _auth_redirect_uri
    secrets_path = get_client_secrets_path()
    if not secrets_path:
        raise ValueError("Missing client_secrets.json")

    code = code_or_url.strip()
    if "code=" in code:
        parsed = urllib.parse.urlparse(code)
        qs = urllib.parse.parse_qs(parsed.query)
        code = qs.get("code", [code])[0]

    code = code.strip()
    if not code:
        raise ValueError("No valid authorization code provided.")

    flow = _active_flow
    if not flow:
        redirect_uri = _auth_redirect_uri or "http://localhost:8090/"
        flow = InstalledAppFlow.from_client_secrets_file(
            str(secrets_path), SCOPES, redirect_uri=redirect_uri
        )

    flow.fetch_token(code=code)
    TOKEN_FILE.write_text(flow.credentials.to_json(), encoding="utf-8")
    ch_info = get_channel_info()
    ch_handle = ch_info.get("handle", "@tsao36") if ch_info else "@tsao36"
    ch_title = ch_info.get("title", "tsao36") if ch_info else "tsao36"

    with _auth_lock:
        _auth_state = {
            "status": "success",
            "message": f"Successfully authorized with channel: {ch_title} ({ch_handle})",
            "completed_at": datetime.now().isoformat(),
        }

    return {"status": "success", "channel": ch_info}


def generate_youtube_metadata(project: Project) -> dict[str, Any]:
    """Generate professional, ready-to-upload YouTube metadata from project scenes and script."""
    settings = load_settings().get("youtube", {})
    pdata = project.data

    # 1. Clean Title (max 100 chars for YouTube)
    raw_title = pdata.title.strip() if pdata.title else pdata.topic.strip()
    # Strip any enclosing quotes or formatting
    raw_title = raw_title.strip('"\'#*')
    if len(raw_title) > 95:
        title = raw_title[:92] + "..."
    else:
        title = raw_title or f"Video: {project.id}"

    # 2. Build Chapter Markers
    # YouTube requires chapters to start at 00:00 and have at least 3 chapters
    chapters = []
    current_time_sec = 0.0

    scenes = project.active_scenes()
    for idx, sc in enumerate(scenes):
        m = int(current_time_sec // 60)
        s = int(current_time_sec % 60)
        timestamp = f"{m:02d}:{s:02d}"

        # Clean title for chapter
        ch_label = sc.visual_description[:45].strip() if sc.visual_description else ""
        if not ch_label and sc.prompt:
            ch_label = sc.prompt[:45].strip()
        if not ch_label:
            ch_label = f"Part {sc.scene_id}"

        # Remove line breaks
        ch_label = ch_label.replace("\n", " ").strip()
        chapters.append(f"{timestamp} - Scene {sc.scene_id}: {ch_label}")

        duration = sc.audio_duration or sc.estimated_duration or 8.0
        current_time_sec += duration

    # 3. Read Script Content if available
    script_text = ""
    script_file = project.path("script", "script.txt")
    if script_file.exists():
        try:
            script_text = script_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    # 4. Generate Tags
    tags = []
    # Add keywords from topic
    topic_words = [w for w in pdata.topic.replace(",", " ").split() if len(w) > 2]
    tags.extend(topic_words[:6])
    tags.extend(["AI Video", "Tutorial", "Tech", "Documentary"])
    # De-duplicate
    seen = set()
    cleaned_tags = []
    for t in tags:
        t_clean = t.strip("#.,!").strip()
        if t_clean.lower() not in seen and len(t_clean) > 1:
            seen.add(t_clean.lower())
            cleaned_tags.append(t_clean)

    # 5. Build Comprehensive Description
    desc_lines = []
    desc_lines.append(f"{raw_title}")
    desc_lines.append("")
    desc_lines.append("📌 Overview:")
    if script_text:
        # First 300 characters of script as summary
        summary = script_text[:350].replace("\n", " ").strip()
        desc_lines.append(f"{summary}...")
    else:
        desc_lines.append(f"In this video, we explore {pdata.topic}.")

    desc_lines.append("")
    if len(chapters) >= 3 and settings.get("auto_generate_chapters", True):
        desc_lines.append("⏱️ Timestamps & Chapters:")
        desc_lines.extend(chapters)
        desc_lines.append("")

    channel_handle = settings.get("channel_handle", "@tsao36")
    channel_url = settings.get("channel_url", "https://www.youtube.com/@tsao36")
    desc_lines.append(f"🔔 Subscribe to the channel: {channel_url}")
    desc_lines.append(f"Created for {channel_handle}")
    desc_lines.append("")

    # Add hashtags
    hashtags = " ".join([f"#{t.replace(' ', '')}" for t in cleaned_tags[:5]])
    if hashtags:
        desc_lines.append(hashtags)

    full_description = "\n".join(desc_lines)

    # 6. Locate Final MP4 Video
    final_rel = pdata.outputs.get("final") or f"final/{project.id}.mp4"
    final_abs = project.abs(final_rel)
    has_video = final_abs is not None and final_abs.exists()
    file_size_mb = 0.0
    if has_video:
        file_size_mb = round(final_abs.stat().st_size / (1024 * 1024), 2)

    # 7. Locate Potential Thumbnail
    thumbnail_path = None
    # Check scene 1 image
    if scenes:
        sc1 = scenes[0]
        if sc1.image and sc1.image.path:
            p_img = project.abs(sc1.image.path)
            if p_img and p_img.exists():
                thumbnail_path = str(p_img)

    return {
        "project_id": project.id,
        "title": title,
        "description": full_description,
        "tags": cleaned_tags,
        "privacy_status": settings.get("default_privacy", "public"),
        "category_id": settings.get("default_category_id", "28"),
        "video_path": str(final_abs) if has_video else None,
        "video_exists": has_video,
        "file_size_mb": file_size_mb,
        "total_duration_seconds": round(current_time_sec, 1),
        "thumbnail_path": thumbnail_path,
        "target_channel": channel_handle,
        "target_channel_url": channel_url,
        "chapters_count": len(chapters),
    }


def _upload_video_worker(
    project_id: str,
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str,
    category_id: str,
    upload_thumbnail: bool,
    thumbnail_path: Optional[str],
) -> None:
    """Background worker that performs the resumable video upload to YouTube."""
    global active_uploads
    service = get_youtube_service()
    if not service:
        with _upload_lock:
            active_uploads[project_id] = {
                "status": "failed",
                "progress_percent": 0,
                "error": "YouTube service not authorized. Please connect your YouTube account first.",
                "completed_at": datetime.now().isoformat(),
            }
        return

    project = Project(project_id)
    final_rel = project.data.outputs.get("final") or f"final/{project_id}.mp4"
    video_abs = project.abs(final_rel)

    if not video_abs or not video_abs.exists():
        with _upload_lock:
            active_uploads[project_id] = {
                "status": "failed",
                "progress_percent": 0,
                "error": f"Final video file not found at {video_abs}",
                "completed_at": datetime.now().isoformat(),
            }
        return

    file_size = video_abs.stat().st_size
    channel_info = get_channel_info() or {}

    with _upload_lock:
        active_uploads[project_id] = {
            "status": "uploading",
            "progress_percent": 0,
            "bytes_uploaded": 0,
            "total_bytes": file_size,
            "video_id": None,
            "video_url": None,
            "channel_title": channel_info.get("title", ""),
            "channel_handle": channel_info.get("handle", ""),
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "error": None,
        }

    log.info(
        "Starting YouTube upload for project '%s' (size: %.2f MB) to channel '%s'...",
        project_id, file_size / (1024 * 1024), channel_info.get("handle", "Unknown")
    )

    try:
        request_body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:30],
                "categoryId": str(category_id),
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # 4 MB chunk size for resilient, fast streaming
        chunk_size = 4 * 1024 * 1024
        media = MediaFileUpload(
            str(video_abs),
            mimetype="video/mp4",
            chunksize=chunk_size,
            resumable=True
        )

        insert_request = service.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media
        )

        response = None
        while response is None:
            upload_status, response = insert_request.next_chunk()
            if upload_status:
                bytes_uploaded = upload_status.resumable_progress
                progress = int((bytes_uploaded / file_size) * 100)
                with _upload_lock:
                    if project_id in active_uploads:
                        active_uploads[project_id]["progress_percent"] = min(99, progress)
                        active_uploads[project_id]["bytes_uploaded"] = bytes_uploaded

        # Video upload completed!
        video_id = response.get("id")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        log.info("YouTube upload completed! Video ID: %s | URL: %s", video_id, video_url)

        # Upload thumbnail if requested
        if upload_thumbnail and thumbnail_path and Path(thumbnail_path).exists():
            try:
                log.info("Setting custom thumbnail for video %s from %s...", video_id, thumbnail_path)
                thumb_media = MediaFileUpload(thumbnail_path, mimetype="image/png")
                service.thumbnails().set(videoId=video_id, media_body=thumb_media).execute()
                log.info("Thumbnail updated successfully.")
            except Exception as e:
                log.warning("Could not set thumbnail (channel may lack custom thumbnail verification): %s", e)

        # Record in project outputs
        project.data.outputs["youtube_video_id"] = video_id
        project.data.outputs["youtube_url"] = video_url
        project.data.outputs["youtube_privacy"] = privacy_status
        project.data.outputs["youtube_uploaded_at"] = datetime.now().isoformat()
        project.save()

        with _upload_lock:
            active_uploads[project_id] = {
                "status": "completed",
                "progress_percent": 100,
                "bytes_uploaded": file_size,
                "total_bytes": file_size,
                "video_id": video_id,
                "video_url": video_url,
                "channel_title": channel_info.get("title", ""),
                "channel_handle": channel_info.get("handle", ""),
                "completed_at": datetime.now().isoformat(),
                "error": None,
            }

    except HttpError as he:
        error_msg = f"YouTube API Error ({he.resp.status}): {he.error_details if hasattr(he, 'error_details') else str(he)}"
        log.error("YouTube upload failed for project %s: %s", project_id, error_msg)
        with _upload_lock:
            active_uploads[project_id] = {
                "status": "failed",
                "progress_percent": 0,
                "error": error_msg,
                "completed_at": datetime.now().isoformat(),
            }
    except Exception as e:
        error_msg = f"Upload error: {str(e)}"
        log.error("YouTube upload failed for project %s: %s", project_id, error_msg)
        with _upload_lock:
            active_uploads[project_id] = {
                "status": "failed",
                "progress_percent": 0,
                "error": error_msg,
                "completed_at": datetime.now().isoformat(),
            }


def start_video_upload(
    project_id: str,
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str = "public",
    category_id: str = "28",
    upload_thumbnail: bool = True,
    thumbnail_path: Optional[str] = None,
) -> dict[str, Any]:
    """Start asynchronous upload of final video to YouTube."""
    with _upload_lock:
        current = active_uploads.get(project_id)
        if current and current.get("status") == "uploading":
            return {"status": "already_uploading", "details": current}

    thread = threading.Thread(
        target=_upload_video_worker,
        args=(
            project_id,
            title,
            description,
            tags,
            privacy_status,
            category_id,
            upload_thumbnail,
            thumbnail_path,
        ),
        daemon=True,
    )
    thread.start()

    return {"status": "started", "project_id": project_id}


def get_upload_status(project_id: str) -> dict[str, Any]:
    """Get real-time upload progress for a project."""
    with _upload_lock:
        if project_id in active_uploads:
            return dict(active_uploads[project_id])

    # Check if project already has a youtube_url saved
    try:
        project = Project(project_id)
        yt_url = project.data.outputs.get("youtube_url")
        yt_id = project.data.outputs.get("youtube_video_id")
        if yt_url:
            return {
                "status": "completed",
                "progress_percent": 100,
                "video_id": yt_id,
                "video_url": yt_url,
                "uploaded_at": project.data.outputs.get("youtube_uploaded_at"),
            }
    except Exception:
        pass

    return {"status": "idle", "progress_percent": 0}
