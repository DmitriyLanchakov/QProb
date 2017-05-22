from django.core.management.base import BaseCommand, CommandError

from django.conf import settings

import server
from server import app


class Command(BaseCommand):
    help = 'Serve API over Sanic.'

    try:
        app.run(host=settings.API_HOST, port=settings.API_PORT, debug=settings.DEBUG, workers=settings.API_WORKERS)
    except KeyboardInterrupt:
        pass
