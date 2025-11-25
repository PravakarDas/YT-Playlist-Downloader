import os
import time
import shutil
import zipfile

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_from_directory,
    make_response,
    abort,
)

from download import (
    start_download_job,
    get_job_progress,
    get_download_root,
    clear_client_jobs,
    get_playlist_info,
    get_job_files,
)

# templates/ + static/ structure
app = Flask(__name__, template_folder="templates", static_folder="static")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_ROOT = get_download_root()
CLIENT_TTL_SECONDS = 3 * 60 * 60  # 3 hours


def delete_client_data(client_id: str) -> None:
    if not client_id:
        return
    client_dir = os.path.join(DOWNLOAD_ROOT, client_id)
    if os.path.isdir(client_dir):
        shutil.rmtree(client_dir, ignore_errors=True)
    clear_client_jobs(client_id)


def cleanup_old_clients() -> None:
    now = time.time()
    if not os.path.isdir(DOWNLOAD_ROOT):
        return

    for name in os.listdir(DOWNLOAD_ROOT):
        client_dir = os.path.join(DOWNLOAD_ROOT, name)
        if not os.path.isdir(client_dir):
            continue
        age = now - os.path.getmtime(client_dir)
        if age > CLIENT_TTL_SECONDS:
            delete_client_data(name)


@app.route("/")
def index():
    cleanup_old_clients()

    old_client_id = request.cookies.get("client_id")
    if old_client_id:
        delete_client_data(old_client_id)

    new_client_id = os.urandom(16).hex()
    resp = make_response(render_template("index.html"))
    resp.set_cookie(
        "client_id",
        new_client_id,
        max_age=CLIENT_TTL_SECONDS,
        httponly=True,
        samesite="Lax",
    )
    return resp


@app.route("/api/playlist-info", methods=["POST"])
def api_playlist_info():
    cleanup_old_clients()

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "No URL provided"}), 400

    try:
        info = get_playlist_info(url)
        return jsonify(
            {
                "ok": True,
                "playlist_title": info["title"],
                "videos": info["videos"],
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/download", methods=["POST"])
def download():
    cleanup_old_clients()

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    file_type = (data.get("format") or "mp4").lower()
    quality = (data.get("quality") or "high").lower()
    indices = data.get("indices") or []

    client_id = request.cookies.get("client_id")
    if not client_id:
        return (
            jsonify({"ok": False, "error": "Missing client id (refresh the page)."}),
            400,
        )

    if not url:
        return jsonify({"ok": False, "error": "No playlist URL provided"}), 400

    if not isinstance(indices, list) or not indices:
        return jsonify({"ok": False, "error": "No videos selected"}), 400

    try:
        indices_int = sorted({int(i) for i in indices if int(i) > 0})
        if not indices_int:
            return jsonify({"ok": False, "error": "No valid video indices"}), 400
    except Exception:
        return jsonify({"ok": False, "error": "Invalid video indices"}), 400

    try:
        job_id = start_download_job(
            playlist_url=url,
            client_id=client_id,
            file_type=file_type,
            quality=quality,
            indices=indices_int,
        )
        return jsonify({"ok": True, "job_id": job_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/progress/<job_id>", methods=["GET"])
def progress(job_id):
    client_id = request.cookies.get("client_id")
    if not client_id:
        return jsonify({"ok": False, "error": "Missing client id"}), 400

    info = get_job_progress(job_id, client_id)
    if not info:
        return jsonify({"ok": False, "error": "Invalid job id"}), 404

    return jsonify({"ok": True, **info})


@app.route("/download-archive/<job_id>", methods=["GET"])
def download_archive(job_id):
    """
    Create a ZIP archive of all files in a job and send it as a download.
    """
    client_id = request.cookies.get("client_id")
    if not client_id:
        abort(403)

    files = get_job_files(job_id, client_id)
    if files is None or not files:
        abort(404)

    client_dir = os.path.join(DOWNLOAD_ROOT, client_id)
    os.makedirs(client_dir, exist_ok=True)

    archive_name = f"{job_id}.zip"
    archive_path = os.path.join(client_dir, archive_name)

    # Create / overwrite zip
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            full = os.path.join(DOWNLOAD_ROOT, rel)
            if os.path.isfile(full):
                # Inside the zip, remove the client_id prefix for cleanliness
                parts = rel.split("/", 1)
                arcname = parts[1] if len(parts) > 1 else rel
                zf.write(full, arcname)

    return send_from_directory(client_dir, archive_name, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
