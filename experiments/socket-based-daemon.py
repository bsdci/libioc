import iocage.lib.Jail
import iocage.lib.events
import http.server
import sys
"""
A daemon that executes commands in temporary jails

Usage:
    python3.6 experiments/socket-based-daemon.py <JAIL>
    /usr/bin/time -l curl --data "whoami && hostname" http://127.0.0.1:8080
"""

jail = iocage.Jail(sys.argv[1])
list(jail.stop(force=True))


class ForkExecDaemon(http.server.BaseHTTPRequestHandler):

    def do_POST(self):

        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode("utf-8")
        command = ["/bin/sh", "-c", body.strip(" ")]
        message = None

        print(body)

        # hack to reset event stacks for multiple requests
        iocage.lib.events.IocageEvent.PENDING_COUNT = 0
        iocage.lib.events.IocageEvent.HISTORY = []

        try:
            for event in jail.fork_exec(command):
                is_target_event = isinstance(event, iocage.lib.events.JailExec)
                has_stdout = "stdout" in event.data.keys()
                if is_target_event and not event.pending and has_stdout:
                    message = event.data["stdout"]
        except iocage.lib.errors.CommandFailure:
            self.send_response(500)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

        if message is not None:
            self.wfile.write(bytes(message, "utf-8"))


server_address = ("127.0.0.1", 8080)
httpd = http.server.HTTPServer(server_address, ForkExecDaemon)
httpd.serve_forever()

