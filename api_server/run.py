from os import unlink
from os.path import exists
import socket

from server import app
import settings


def main():
    try:
        if settings.DEV_ENV:
            app.run(host=settings.API_HOST, port=settings.DEV_PORT, debug=settings.DEBUG)
        else:
            try:
                addr = '/tmp/{}_api_sock'.format(settings.FOLDER)
                unlink(addr)
            except OSError:
                    if exists(addr):
                        raise
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(addr)

            app.run(host=None, port=None, sock=sock, debug=settings.DEBUG, workers=settings.API_WORKERS)
    except KeyboardInterrupt:
        pass


main()
