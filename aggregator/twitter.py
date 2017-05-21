import datetime

from django.http import HttpResponse
from django.shortcuts import render
from django.conf import settings

import twitter


api = twitter.Api(consumer_key=settings.CONSUMER_KEY,
                  consumer_secret=settings.CONSUMER_SECRET,
                  access_token_key=settings.ACCESS_TOKEN_KEY,
                  access_token_secret=settings.ACCESS_TOKEN_SECRET)


def get_tweets(handle):
    try:
        tweets = api.GetUserTimeline(screen_name=handle, exclude_replies=True, \
                    include_rts=False)  # includes entities
        return tweets
    except:
        return None


def twitter_date(value):
    split_date = value.split()
    del split_date[0], split_date[-2]
    value = ' '.join(split_date)  # Fri Nov 07 17:57:59 +0000 2014 is the format
    return datetime.datetime.strptime(value, '%b %d %H:%M:%S %Y')


def get_tweets_by_tag(tag):
    try:
        tweets = api.GetSearch(term=tag, raw_query=None, geocode=None, since_id=None, \
                    max_id=None, until=None, since=None, count=50, lang='en', locale=None, \
                    result_type="mixed", include_entities=True)
        return tweets
    except:
        return None


def post_tweet(data):
    from aggregator.models import Post
    #tags_ = u''
    media_ = None

    try:
        post = Post.objects.get(title=data['title'])

        try:
            tags_ = "".join(["#{0}".format(tag) for tag in post.tags])[:40]
            print(tags_)
        except Exception as e:
            print(e)
            tags_ = u""

        status_ = "{0} [{1}]: {2}{3}/ {4}".format(post.title[:80], post.sentiment, settings.DOMAIN, post.slug, tags_)
        print(("Status: {0}".format(status_)))

        if post.image:
            media_ = "{0}{1}".format(settings.DOMAIN, post.image)
            print(("Media: {0}".format(media_)))
            api.PostUpdate(status=status_, media=media_)
        else:
            api.PostUpdate(status=status_, media=None)

        print("Sent tweet.")

    except Exception as e:
        print(("At Twitter post: {0}".format(e)))
