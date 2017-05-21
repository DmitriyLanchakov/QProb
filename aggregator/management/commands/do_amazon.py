from django.core.management.base import BaseCommand, CommandError
from aggregator.amazon import (parse_amazon, parse_by_categories, parse_by_keywords)

class Command(BaseCommand):
    help = 'Parses Amazon.'

    def handle(self, *args, **options):
        #TODO make normal commands for each function
        #parse_amazon(type_='ALL', title='')
        #parse_by_categories()

        parse_by_keywords()

        self.stdout.write(self.style.SUCCESS('Successfully done jobs'))
