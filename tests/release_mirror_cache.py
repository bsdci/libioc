# Copyright (c) 2017-2019, Stefan Grönke
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
import typing
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import shutil
import urllib.request
import urllib.parse
import threading

LOCAL_MIRROR_PORT = 8234

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
            download = True
        elif url.path.endswith(".ssl") or url.path.endswith("/MANIFEST"):
            print(f"Force re-download if {cache_filename}")
            download = True
        else:
            download = False

        if download is True:
            if os.path.isdir(os.path.dirname(cache_filename)) is False:
                os.makedirs(os.path.dirname(cache_filename))
            try:
                self.__urlretrieve(self.path, cache_filename)
                print(f"{self.path} saved to {cache_filename}")
            except urllib.error.HTTPError:  # noqa: T484
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
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)

        chunk_size = 1024
        with open(cache_file, "wb") as f:
            with opener.open(url) as res:
                while True:
                    chunk = res.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)


class BackgroundServer:
    """HTTP server thread."""

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
        """Stop the HTTP server."""
        self.httpd.shutdown()
