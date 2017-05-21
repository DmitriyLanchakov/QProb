from django.core.management.base import BaseCommand, CommandError
from aggregator.youtube import do_youtube, clean_youtube_text

class Command(BaseCommand):
    help = 'Youtube searcher for article titles.'

    def handle(self, *args, **options):
        #TODO make normal commands for each function
        #do_youtube()
        clean_youtube_text('ALL', '')

        self.stdout.write(self.style.SUCCESS('Successfully done parsing jobs'))
