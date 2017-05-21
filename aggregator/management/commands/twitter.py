from django.core.management.base import BaseCommand, CommandError
from aggregator.tasks import (tweets_to_db, tweets__by_tag_to_db, clean_tweet_hashtags)

class Command(BaseCommand):
    help = 'Twitetr parser.'

    def handle(self, *args, **options):
        tweets_to_db()
        tweets__by_tag_to_db()
        clean_tweet_hashtags()

        self.stdout.write(self.style.SUCCESS('Successfully done parsing jobs'))
