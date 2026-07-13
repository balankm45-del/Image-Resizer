import http.server
import socketserver
import json
import traceback
import base64
import cgi
import os
from processor import process_image

PORT = 3000


def load_environment():
    for env_file in (".env.local", ".env"):
        if not os.path.exists(env_file):
            continue
        with open(env_file, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)


load_environment()

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class ImageResizerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Print logs to standard output
        print(f"[Python Server] {format % args}")

    def do_GET(self):
        # Route static index.html or health check
        if self.path == "/" or self.path == "/index.html":
            try:
                with open("index.html", "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                err_msg = f"Error loading index.html: {e}".encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(err_msg)))
                self.end_headers()
                self.wfile.write(err_msg)
        elif self.path == "/api/health":
            resp_bytes = json.dumps({"status": "ok", "language": "python"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
        elif self.path.startswith("/assets/"):
            import os
            safe_path = os.path.normpath(self.path.lstrip("/"))
            if safe_path.startswith("assets/") and os.path.isfile(safe_path):
                try:
                    with open(safe_path, "rb") as f:
                        content = f.read()
                    
                    content_type = "application/octet-stream"
                    if safe_path.endswith(".jpg") or safe_path.endswith(".jpeg"):
                        content_type = "image/jpeg"
                    elif safe_path.endswith(".png"):
                        content_type = "image/png"
                    elif safe_path.endswith(".svg"):
                        content_type = "image/svg+xml"
                    elif safe_path.endswith(".gif"):
                        content_type = "image/gif"
                    
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except Exception as e:
                    err_msg = f"Error loading asset: {e}".encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(err_msg)))
                    self.end_headers()
                    self.wfile.write(err_msg)
            else:
                msg = b"404 Not Found"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
        else:
            msg = b"404 Not Found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_POST(self):
        # Wrap the entire routing inside try-except to prevent unhandled exceptions yielding HTML fallback
        try:
            if self.path == "/api/resize":
                # Parse multipart form data cleanly with cgi.FieldStorage
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        'REQUEST_METHOD': 'POST',
                        'CONTENT_TYPE': self.headers.get('Content-Type')
                    }
                )

                if "image" not in form:
                    resp_bytes = json.dumps({"error": "No image file uploaded."}).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(resp_bytes)))
                    self.end_headers()
                    self.wfile.write(resp_bytes)
                    return

                file_item = form["image"]
                if not file_item.file or not file_item.filename:
                    resp_bytes = json.dumps({"error": "Invalid or empty image uploaded."}).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(resp_bytes)))
                    self.end_headers()
                    self.wfile.write(resp_bytes)
                    return

                # Read raw binary content of the file
                input_bytes = file_item.file.read()
                filename = file_item.filename

                # Parse and default other parameters
                resize_mode = form.getfirst("resizeMode", "dimensions")
                width = form.getfirst("width", "")
                height = form.getfirst("height", "")
                percentage = form.getfirst("percentage", "100")
                keep_aspect = form.getfirst("maintainAspectRatio", "true") == "true"
                format_ext = form.getfirst("format", "png")
                quality = form.getfirst("quality", "80")

                # Call ImageMagick processor
                output_bytes, download_filename, out_w, out_h, out_size = process_image(
                    input_bytes=input_bytes,
                    filename=filename,
                    resize_mode=resize_mode,
                    width=width,
                    height=height,
                    percentage=percentage,
                    keep_aspect=keep_aspect,
                    format_ext=format_ext,
                    quality=quality
                )

                # Base64 encode the output image to return inside JSON
                encoded_image = base64.b64encode(output_bytes).decode('utf-8')
                mime_type = f"image/{format_ext if format_ext != 'jpg' else 'jpeg'}"
                data_url = f"data:{mime_type};base64,{encoded_image}"

                response_data = {
                    "success": True,
                    "filename": download_filename,
                    "width": out_w,
                    "height": out_h,
                    "size_bytes": out_size,
                    "data_url": data_url
                }

                resp_bytes = json.dumps(response_data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)
            else:
                msg = b"404 Not Found"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)

        except Exception as e:
            traceback.print_exc()
            resp_bytes = json.dumps({"error": f"Image processing failed: {str(e)}"}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

def run():
    print(f"Starting Python server on port {PORT}...")
    server_address = ("0.0.0.0", PORT)
    httpd = ThreadingHTTPServer(server_address, ImageResizerHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == "__main__":
    run()
