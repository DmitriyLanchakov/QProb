import asyncio

import uvloop

from django.core.management.base import BaseCommand

from aggregator.tasks import (parse_all_feeds, title_cleaner_from_db,
    clean_images_from_db_if_no_folder, update_db_with_cleaned_content,
    clean_images_if_not_in_db)


class Command(BaseCommand):
    help = 'Parses feeds and exewcutes additional cleaning.'

    def handle(self, *args, **options):
        loop = uvloop.new_event_loop()
        asyncio.set_event_loop(loop)

        parse_all_feeds(loop=loop)
        title_cleaner_from_db(loop=loop)
        update_db_with_cleaned_content(loop=loop)
        clean_images_from_db_if_no_folder(loop=loop)
        clean_images_if_not_in_db(loop=loop)

        loop.close()

        self.stdout.write(self.style.SUCCESS('Successfully done parsing jobs'))
