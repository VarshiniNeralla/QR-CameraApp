
# import os
# import uuid
# import io
# import base64
# from datetime import datetime
# from flask import Flask, render_template, request, url_for, send_from_directory, jsonify
# from flask_socketio import SocketIO, join_room
# import qrcode

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# app = Flask(__name__, static_folder="static", template_folder="templates")
# app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")


# def generate_qr_datauri(url):
#     qr = qrcode.QRCode(box_size=6, border=2)
#     qr.add_data(url)
#     qr.make(fit=True)
#     img = qr.make_image(fill_color="black", back_color="white")
#     buf = io.BytesIO()
#     img.save(buf, format="PNG")
#     data = base64.b64encode(buf.getvalue()).decode()
#     return f"data:image/png;base64,{data}"


# @app.route("/")
# def index():
#     """Desktop page that shows QR and listens for live images."""
#     session_id = str(uuid.uuid4())
#     upload_url = url_for("upload_page", session_id=session_id, _external=True)
#     qr_datauri = generate_qr_datauri(upload_url)
#     return render_template("index.html", session_id=session_id, qr_datauri=qr_datauri)


# @app.route("/upload/<session_id>", methods=["GET", "POST"])
# def upload_page(session_id):
#     """Mobile upload page. GET -> camera UI, POST -> save image + notify desktop."""
#     if request.method == "GET":
#         return render_template("upload.html", session_id=session_id)

#     # POST: handle uploaded image
#     if "photo" not in request.files:
#         return jsonify({"error": "no file part"}), 400

#     file = request.files["photo"]
#     if file.filename == "":
#         return jsonify({"error": "no selected file"}), 400

#     # Save with timestamp instead of overwriting
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
#     filename = f"{session_id}_{timestamp}.jpg"
#     save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#     file.save(save_path)

#     image_url = url_for("uploaded_file", filename=filename, _external=True)

#     # Notify all connected desktop clients in this session
#     socketio.emit("new_image", {"image_url": image_url}, room=session_id)

#     return jsonify({"status": "ok", "image_url": image_url}), 200


# @app.route("/uploads/<filename>")
# def uploaded_file(filename):
#     return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# @socketio.on("join")
# def handle_join(data):
#     room = data.get("room")
#     if room:
#         join_room(room)


# if __name__ == "__main__":
#     socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)


# backend/app.py
import os
import uuid
import io
import base64
import shutil
from datetime import datetime
from flask import (
    Flask, render_template, request, url_for, send_from_directory,
    jsonify, send_file, abort
)
from flask_socketio import SocketIO, join_room
import qrcode
import tempfile
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")


def generate_qr_datauri(url):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{data}"


@app.route("/")
def index():
    """Desktop page that shows QR and listens for live images."""
    session_id = str(uuid.uuid4())
    upload_url = url_for("upload_page", session_id=session_id, _external=True)
    qr_datauri = generate_qr_datauri(upload_url)
    return render_template("index.html", session_id=session_id, qr_datauri=qr_datauri)


@app.route("/upload/<session_id>", methods=["GET", "POST"])
def upload_page(session_id):
    """Mobile upload page. GET -> camera UI, POST -> save image + notify desktop."""
    if request.method == "GET":
        return render_template("upload.html", session_id=session_id)

    # POST: handle uploaded image
    if "photo" not in request.files:
        return jsonify({"error": "no file part"}), 400

    file = request.files["photo"]
    if file.filename == "":
        return jsonify({"error": "no selected file"}), 400

    # Save with timestamp instead of overwriting
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    # secure filename not needed here if session_id is trusted, but you may add werkzeug.utils.secure_filename
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"{session_id}_{timestamp}{ext}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    image_url = url_for("uploaded_file", filename=filename, _external=True)

    # Notify all connected desktop clients in this session
    socketio.emit("new_image", {"image_url": image_url}, room=session_id)

    return jsonify({"status": "ok", "image_url": image_url}), 200


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/list_images/<session_id>")
def list_images(session_id):
    """Return JSON list of image URLs for a session, newest first."""
    pattern = os.path.join(app.config["UPLOAD_FOLDER"], f"{session_id}_*")
    files = glob.glob(pattern)
    # sort newest first
    files.sort(reverse=True)
    base = request.url_root.rstrip("/")
    urls = [url_for("uploaded_file", filename=os.path.basename(p), _external=True) for p in files]
    return jsonify({"images": urls})


@app.route("/download/<session_id>")
def download_session_zip(session_id):
    """Create a zip of all images for the session and return it."""
    pattern = os.path.join(app.config["UPLOAD_FOLDER"], f"{session_id}_*")
    files = glob.glob(pattern)
    if not files:
        return abort(404, description="No images for this session")

    # create temp directory to hold zip
    tmpdir = tempfile.mkdtemp()
    zip_basename = os.path.join(tmpdir, f"{session_id}_images")
    shutil.make_archive(zip_basename, 'zip', root_dir=app.config["UPLOAD_FOLDER"],
                        base_dir=".", verbose=0, logger=None)
    # above makes a zip of the entire uploads folder so we instead create zip manually with only session files
    import zipfile
    zip_path = os.path.join(tmpdir, f"{session_id}_images.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for f in files:
            zf.write(f, arcname=os.path.basename(f))

    return send_file(zip_path, as_attachment=True, download_name=f"{session_id}_images.zip")


@socketio.on("join")
def handle_join(data):
    room = data.get("room")
    if room:
        join_room(room)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
