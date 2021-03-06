#!/usr/bin/env python
from os import environ
import sys
from os.path import dirname, join

from dotenv import load_dotenv


BASE_DIR = dirname(dirname('__file__'))
BASE_PATH = dirname(BASE_DIR)
load_dotenv(join(BASE_PATH, '.env'))


if __name__ == "__main__":
    environ.setdefault("DJANGO_SETTINGS_MODULE", "qprob.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise
    execute_from_command_line(sys.argv)
