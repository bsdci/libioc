from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import shutil
import urllib.request
import threading

LOCAL_MIRROR_PORT=8234

uname = os.uname()


class CacheHandler(SimpleHTTPRequestHandler):

    basedir = "/releases"

    @property
    def release(self):
        return "12.0-RELEASE"
        return str(uname.release)

    @property
    def upstream_mirror(self):
        return (
            f"https://download.freebsd.org/ftp/releases"
            f"/{uname.machine}/{uname.machine}"
        )

    def do_GET(self):
        cache_filename = f"{self.basedir}{self.path}"

        if os.path.exists(cache_filename):
            print(f"Cache hit: {self.path}")
        else:
            print(f"Cache miss: {self.path}")
            url = self.upstream_mirror + self.path
            print(f"Download: {url}")
            
            if os.path.isdir(os.path.dirname(cache_filename)) is False:
                os.makedirs(os.path.dirname(cache_filename))

            try:
                urllib.request.urlretrieve(url, cache_filename)
            except urllib.error.HTTPError as e:
                self.send_error(e.getcode())
                return
    
        try:
            with open(cache_filename, "rb") as f:
                print(f"sending {cache_filename}")
                fs = os.fstat(f.fileno())
                self.send_response(200)
                self.send_header("Content-Length", str(fs[6]))
                self.end_headers()
                shutil.copyfileobj(f, self.wfile)
                return
        except Exception:
            pass
        
        try:
            self.send_error(500)
        except BrokenPipeError:
            print("Client disconnected before finishing download")
            pass

def run(port: int) -> None:
    server_address = ("localhost", port)
    httpd = HTTPServer(server_address, CacheHandler)
    httpd.serve_forever()

def run_thread(port: int) -> threading.Thread:
    thread = threading.Thread(target=run, args=(port,))
    thread.start()
    return thread

