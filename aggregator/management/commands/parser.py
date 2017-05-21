from django.core.management.base import BaseCommand, CommandError
from aggregator.tasks import (parse_all_feeds, title_cleaner_from_db, content_if_empty_all, clean_images_from_db_if_no_folder, update_db_with_cleaned_content)


class Command(BaseCommand):
    help = 'Parses feeds and exewcutes additional cleaning.'

    def handle(self, *args, **options):
        parse_all_feeds()
        title_cleaner_from_db()
        update_db_with_cleaned_content()
        clean_images_from_db_if_no_folder()

        self.stdout.write(self.style.SUCCESS('Successfully done parsing jobs'))
