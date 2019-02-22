import typing
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import shutil
import urllib.request
import urllib.parse
import threading

LOCAL_MIRROR_PORT=8234

uname = os.uname()


class CacheHandler(SimpleHTTPRequestHandler):

    basedir = ".cache/libioc"

    def do_GET(self):

        url = urllib.parse.urlparse(self.path)
        if url.netloc.lower().endswith(".freebsd.org") is False:
            self.send_error(502)
            return

        if url.netloc.startswith("update"):
            cache_filename = f"{self.basedir}/update.freebsd.org{url.path}"
        else:
            cache_filename = f"{self.basedir}/{url.netloc.lower()}{url.path}"

        if os.path.exists(cache_filename) is False:
            print(f"Cache miss: {cache_filename} ({self.path})")
            
            if os.path.isdir(os.path.dirname(cache_filename)) is False:
                os.makedirs(os.path.dirname(cache_filename))
            try:
                self.__urlretrieve(self.path, cache_filename)
                print(f"{self.path} saved to {cache_filename}")
            except urllib.error.HTTPError as e:
                self.send_error(e.getcode())
                return
    
        try:
            with open(cache_filename, "rb") as f:
                fs = os.fstat(f.fileno())
                self.send_response(200)
                self.send_header("Content-Length", str(fs[6]))
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Accept-Ranges", " bytes")
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

    @staticmethod
    def __urlretrieve(url: str, cache_file: str) -> None:
        opener = urllib.request.FancyURLopener({})
        opener.retrieve(url, cache_file)


class BackgroundServer:

    def __init__(self, port: int) -> None:
        self.httpd = HTTPServer(("localhost", port,), CacheHandler)
        self.thread = threading.Thread(
            target=self.__run,
            args=(self.httpd,)
        )
        self.thread.start()

    @staticmethod
    def __run(httpd) -> None:
        httpd.serve_forever()

    def stop(self) -> None:
        self.httpd.shutdown()
