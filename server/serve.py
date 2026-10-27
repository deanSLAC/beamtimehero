"""Run the app on every address in HOST (comma-separated; uvicorn's --host
takes one). An address this machine lacks is skipped. run.sh execs this.

    HOST=127.0.0.1,192.168.41.6 PORT=8742 python server/serve.py
"""

import errno
import logging
import os
import socket
import sys

import uvicorn

log = logging.getLogger("beamtimehero.serve")


def listen_sockets(hosts, port):
    """A listening TCP socket per address; an address this machine does not
    have (EADDRNOTAVAIL) is skipped with a warning, anything else (port in use) raises."""
    out = []
    for h in hosts:
        s = socket.socket(socket.AF_INET6 if ":" in h else socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((h, port))
        except OSError as e:
            s.close()
            if e.errno == errno.EADDRNOTAVAIL:
                log.warning("not listening on %s: this machine has no such address", h)
                continue
            raise
        s.listen(2048)
        s.set_inheritable(True)
        out.append(s)
    return out


def main():
    logging.basicConfig(level=logging.INFO)
    hosts = [h.strip() for h in os.getenv("HOST", "127.0.0.1").split(",") if h.strip()] or ["127.0.0.1"]
    port = int(os.getenv("PORT", "8080"))
    socks = listen_sockets(hosts, port)
    if not socks:
        sys.exit(f"none of {', '.join(hosts)} can be bound on port {port}")
    for s in socks:
        log.info("serving on http://%s:%d/", *s.getsockname()[:2])
    from app import app  # after the binds: a busy port fails before the app starts its workers
    uvicorn.Server(uvicorn.Config(app)).run(sockets=socks)


if __name__ == "__main__":
    main()
