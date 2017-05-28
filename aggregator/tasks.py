from datetime import datetime
from time import mktime, sleep
import random
from os import listdir, rename, remove
from os.path import isfile, join
import asyncio

import requests
from PIL import Image
import urllib.request, urllib.error, urllib.parse
import imghdr
import feedparser
from newspaper import Article, Config
from textblob import TextBlob
from clint.textui import colored
from bs4 import BeautifulSoup

from django.db import connection
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text, iri_to_uri
from django.db import IntegrityError

from .models import Sources, Twits, TwitsByTag, Tags, Post, Category
from . import rake
from .facebook_publisher import face_publish
from .twitter import post_tweet, twitter_date, get_tweets_by_tag, get_tweets
from .amazon import parse_amazon
from .text_tools import replace_all, text_cleaner, summarizer
from textwrap import wrap
from .youtube import do_youtube_once
import warnings
warnings.filterwarnings("ignore")

config = Config()
config.browser_user_agent = settings.HEADERS['User-Agent']
config.skip_bad_cleaner = True

#TODO implement optimized images functions: start_opt, del_nonopt, use_opt,...


def feeds_to_db(data):
    sources = Sources.objects.create(feed = data[0], twitter_handle=data[1].replace('https://twitter.com/', '').replace('http://twitter.com/', ''))
    sources.save()


# TODO solve the problem if handle not in db, but called
# from somewhere, when should be saved to TwitsByTag
# this should be unified
async def get_source_obj(source):
    try:
        source_obj = Sources.objects.get(twitter_handle=source)
    except:
        source_obj = None
    return source_obj


async def save_tweet(entry, source):
    try:
        if settings.SHOW_DEBUG:
            print("Twitter handle {}".format(entry.user.screen_name))
        source_obj = await get_source_obj(source=source)
        if not (source_obj is None):
            t = Twits.objects.create(tweet_id=entry.id, content=entry.text,
                twitter_handle=source_obj, screen_name=entry.user.name,
                profile_image=entry.user.profile_image_url, hashtags=entry.hashtags,
                date=await twitter_date(entry.created_at))
            t.save()
            print(colored.green("Tweet cached to db."))
    except Exception as e:
        # TODO filter duplicate errors
        print(colored.red("At save_tweet {}").format(e))


async def generate_tweets(source, loop):
    data = await get_tweets(handle=source)

    if not (data is None):
        if (len(data) > 0):
            asyncio.gather(*[save_tweet(entry=entry, source=source) for entry in data],
                return_exceptions=True
            )


def tweets_to_db(loop):
    sources_ = Sources.objects.filter(active=True).values('twitter_handle')
    sources = [s['twitter_handle'] for s in sources_ if not (s['twitter_handle'] == "")]
    sample = random.sample(sources, len(sources))

    loop.run_until_complete(asyncio.gather(*[generate_tweets(\
        source=source, loop=loop) for source in sample], \
        return_exceptions=True
    ))


async def save_tweet_tag(tweet):
    try:
        t = TwitsByTag.objects.create(tweet_id=tweet.id, content=tweet.text,
            twitter_handle=tweet.user.screen_name, screen_name=tweet.user.name,
            profile_image=tweet.user.profile_image_url, hashtags=tweet.hashtags,
            date=await twitter_date(tweet.created_at), by_tag=tag)
        t.save()
        print(colored.green("Tweet inserted into db."))
    except Exception as e:
        print(colored.red("At tweetes by tag to db {0}".format(e)))


async def generate_tweets_tag():
    tweets = await get_tweets_by_tag(tag=tag)
    if not (tweets is None):
        if len(tweets) > 0:
            asyncio.gather(*[generate_tweets_tag(\
                tweet=tweet) for tweet in tweets], \
                return_exceptions=True
            )


# TODO this can be improved, definitely has duplicates
def tweets__by_tag_to_db(loop):
    tags = Tags.objects.filter(type='T').filter(active=True)

    loop.run_until_complete(asyncio.gather(*[generate_tweets_tag(\
        tag=tag, loop=loop) for tag in tags], \
        return_exceptions=True
    ))


async def clean_tweet(tweet, replacements):
    for each in tweet.hashtags.split('Hashtag'):
        if 'Text' in each:
            hashtag = await replace_all(each.split('Text=')[1], replacements)
            try:
                tweet.tags.add(hashtag)
                tag = Tags.objects.create(title=hashtag, type='T')
                tag.save()
                print("Tag {0} saved.".format(hashtag))
            except Exception as e:
                print("TAt tag cleaner {0} with {1}.".format(e, hashtag))


def twit_cleaner(tweets, loop):
    replacements = { "u'": "", ")": "", "]": "", "'": "", ",": ""}

    loop.run_until_complete(asyncio.gather(*[clean_tweet(\
        tweet=tweet, replacements=replacements) for tweet in tweets], \
        return_exceptions=True
    ))


def clean_tweet_hashtags(loop):
    tweets = Twits.objects.all()
    twit_cleaner(tweets=tweets, loop=loop)
    tweets = TwitsByTag.objects.all()
    twit_cleaner(tweets=tweets, loop=loop)


async def get_category(c):
    cat = wrap(c, 40)[0]
    if settings.SHOW_DEBUG:
        print(colored.green("New category name if changed: {0}".format(cat)))

    try:
        if len(cat) > 0:
            category_ = Category.objects.get(title=cat)
        else:
            category_ = Category.objects.get(title='Unknown')
    except ObjectDoesNotExist:
        if len(cat) > 0:
            category_ = Category.objects.create(title=cat)
            category_.save()
        else:
            category_ = Category.objects.create(title='Unknwon')
            category_.save()

    return category_


async def save_tags(tags, entry):
    if len(tags) > 0:
        for tg in tags:
            try:
                tag = Tags.objects.get(title=tg)
            except ObjectDoesNotExist:
                tag = Tags.objects.create(title=tg)
                tag.save()
            entry.tags.add(tag)


async def posts_to_db(row, loop):
    if settings.SHOW_DEBUG:
        print(colored.green("Data for insertion: {0}, {1}".format(row['title'], row['date'])))

    category_ = await get_category(c=row['category'])
    feed_ = Sources.objects.get(feed=row['feed'])

    if len(row['title']) > settings.MINIMUM_TITLE:
        try:
            entry = Post.objects.create(title=row['title'], url=row['url'], image=row['image_url'],
                working_content=row['cleaned_text'], content=row['cleaned_text'], summary=row['summary'],
                date=row['date'], sentiment=row['sentiment'], category=category_, feed=feed_,
                feed_content=row['feed_content'], pub_date=datetime.now())

            await save_tags(tags=row["tags"], entry=entry)

            entry.save()
            print(colored.green("Data inserted to db."))

            if settings.GET_YOUTUBE:
                print("Going to youtube...")
                await do_youtube_once(post=entry, loop=loop)

            if settings.POST_TO_TWITTER:
                print("Going to Twitter...")
                await post_tweet(data=row)

            if settings.POST_TO_FACEBOOK:
                print("Going to Facebook...")
                await face_publish(data=row)

            if settings.GET_AMAZON:
                await parse_amazon(title=row['title'], loop=loop)
        except Exception as e:
            print(colored.red("[ERROR] At post to db: {0}".format(e)))


async def get_body_from_internet(url):
    article = Article(url, config=config)
    article.download()
    article.parse()

    return article


async def sentiment(data):
    try:
        blob = TextBlob(data)
        sentiment =round(blob.sentiment.polarity, 2)
    except Exception as e:
        print("At sentiment {}".format(e))
        sentiment = None

    return sentiment


async def title_dropper(title):
        removals_ = open(join(settings.BASE_DIR, "aggregator", 'data', 'title_stops.txt'), 'r')
        removals = [r.replace('\n', '') for r in removals_]

        for r in removals:
            if r in title:
                return False

        return True


async def del_art(article):
    try:
        if await title_dropper(article.title) is False:
            if settings.SHOW_DEBUG:
                print(colored.green("This article should be deleted: {0}".format(article.title)))
            article.delete()
    except Exception as e:
        print(colored.red("At del_art {}".format(e)))


def title_cleaner_from_db(loop):
    articles = Post.objects.all()

    loop.run_until_complete(asyncio.gather(*[del_art(\
        article=article) for article in articles], \
        return_exceptions=True
    ))


def remake_summaries_from_content():
    articles = Post.objects.filter(parsed=True)

    for article in articles:
        entry = Post.objects.get(title=article.title)

        try:
            print((colored.green("Got this entry: {0}".format(entry.title))))
            entry.summary = summarizer(data=entry.content, sentences=settings.SUMMARIZER_SENTENCES)
            entry.sentiment = sentiment(entry.content)
            entry.save()
            print((colored.green("Remade summary: {0}".format(entry.summary))))
        except Exception as e:
            print((colored.red("[ERROR] At remake summaries: {0}".format(e))))


async def update_item(article):
    try:
        entry = Post.objects.get(title=article.title)
        entry.content = await text_cleaner(data=entry.working_content)
        entry.save()
    except Exception as e:
        print(colored.red("[ERROR] At update db with cleaned content {}".format(e)))


def update_db_with_cleaned_content(loop):
    articles = Post.objects.all()

    loop.run_until_complete(asyncio.gather(*[update_item(\
        article=article) for article in articles], \
        return_exceptions=True
    ))


def update_wrong_image_urls():
    articles = Post.objects.filter(image__icontains='%')

    for article in articles:
        oldname = "{0}".format(article.image)
        newname = "{0}".format(article.image).replace('%', '')
        article.image = newname
        article.save()
        print((colored.green("Removed percents from image url {0}.".format(article.image))))
        original_filename = join(settings.BASE_DIR, 'uploads', oldname.split('/', 1)[1])
        new_filename = join(settings.BASE_DIR, 'uploads', newname.split('/', 1)[1])
        rename(original_filename, new_filename)
        print((colored.green("Renamed image from {0} to {1} in folder.".format(original_filename, new_filename))))


async def check_post(e):
    try:
        #if content from feed is betetr than acquired from web
        if (len(e.working_content) < 50) & (len(e.feed_content) > 50):
            soup = BeautifulSoup(e.feed_content)
            text = ''.join(soup.findAll(text=True))
            e.content = await text_cleaner(data=text)
            e.summary = await summarizer(data=text, sentences=settings.SUMMARIZER_SENTENCES)
            e.sentiment = await sentiment(data=text)
            e.parsed = True
            e.save()
            print(colored.green("Empty post updated with feed content: {0}".format(e.title)))
        else:
            #empty everyhing otherwise
            e.content = ""
            e.summary = ""
            e.parsed = True
            e.save()
    except Exception as e:
        print(colored.red("[ERROR] At content if emtpy [all] : {0}".format(e)))


def content_if_empty_all(loop):
    empty_posts = Post.objects.raw("SELECT * FROM aggregator_post WHERE LENGTH(working_content) < 50")

    loop.run_until_complete(asyncio.gather(*[check_post(\
        e=e) for e in empty_posts], \
        return_exceptions=True
    ))


async def check_img(filenames, post):
    if not (post.image in filenames):
        if (not (post.image == "")) | (not (post.image is None)):
            print(colored.red("Image not in folder: {0}".format(post.image)))
            post.image = None
            post.save()


def clean_images_from_db_if_no_folder(loop):
    path = join(settings.BASE_DIR, 'uploads')
    filenames = ["uploads/{0}".format(f) for f in listdir(path) if isfile(join(path, f))]
    posts = Post.objects.all()

    loop.run_until_complete(asyncio.gather(*[check_img(\
        filenames=filenames, post=post) for post in posts], \
        return_exceptions=True
    ))


async def check_db(fle):
    try:
        post = Post.objects.get(image='uploads/{0}'.format(fle))
    except:
        print(colored.green("File not in db: {0}".format(fle)))
        filename = join(settings.BASE_DIR, 'uploads', fle)
        remove(filename)
        print("Removed {0}".format(filename))


def clean_images_if_not_in_db(loop):
    path = filename = join(settings.BASE_DIR, 'uploads')
    filenames = [f for f in listdir(path) if isfile(join(path, f))]

    loop.run_until_complete(asyncio.gather(*[check_db(\
        fle=fle) for fle in filenames], \
        return_exceptions=True
    ))


async def download_image(url):
    try:
        source = requests.get(url, proxies=settings.PROXIES, headers=settings.HEADERS)
        image_name_ = url.rsplit('/', 1)[-1].split('?', 1)[0]
        replacements = {"%": "",
            ")": "",
            "]": "",
            "'": "",
            ",": "",
            "-": "",
            "_": "",
            "=": ""}
        img = await replace_all(image_name_, replacements)
        print("img")
        print(img)
        image_name = img.split(".")[-2][:100] + "." + img.split(".")[-1]
        print("image_name")
        print(image_name)
        filename = join(settings.BASE_DIR, 'uploads', image_name)

        post = Post.objects.filter(image="uploads/{0}".format(image_name)).count()

        if (post == 0):
            with open(filename, 'wb') as image:
                image.write(source.content)
                image.close()

            #check if this is really an image
            with Image.open(filename) as format_checker:
                width, height = format_checker.size
                if not (format_checker.format is None):
                    if width < settings.MINIMUM_IMAGE or height < settings.MINIMUM_IMAGE:
                        format_checker.close()
                        remove(filename)
                        return None
                    else:
                        format_checker.close()
                        return 'uploads/{0}'.format(image_name)
                else:
                    format_checker.close()
                    remove(filename)
                    return None
        else:
            return 'uploads/{0}'.format(image_name)
    except Exception as e:
        print(colored.red("At download_image {}".format(e)))


#TODO doersm\t see, tp work, remake
async def keyword_extractor(data):
    try:
        rake_object = rake.Rake(stop_words_path=join(settings.BASE_DIR, "aggregator", 'data', 'stop_words.txt'), min_char_length=3, max_words_length=2, min_keyword_frequency=3)
        keywords = rake_object.run(data)

        keywords_ = []
        if not (keywords is None):
            for k in keywords:
                keywords_.append(k[0])
    except Exception as e:
        print(colored.red("At keywords extraction {}".format(e)))
        keywords_ = []

    return keywords_


# TODO definitely can be better if we knew where content is
async def get_feed_content(data):
    try:
        feed_content = data.content
    except Exception as e:
        if settings.SHOW_DEBUG:
            print(colored.red("[ERROR] At body from feed #1: {0}".format(e)))
        try:
            feed_content = data.summary
        except Exception as e:
            if settings.SHOW_DEBUG:
                print(colored.red("[ERROR] At body from feed #2: {0}".format(e)))
            try:
                feed_content = data.description
            except Exception as e:
                if settings.SHOW_DEBUG:
                    print(colored.red("[ERROR] At body from feed #3: {0}".format(e)))
                feed_content = ""
    return feed_content


async def get_image(url):
    try:
        if len(url):
            image_name = await download_image(url=url)
        else:
            image_name = None
    except Exception as e:
        print(colored.red("[ERROR] At get_image: {}".format(e)))

    return image_name


async def get_date(data):
    try:
        dt = datetime.fromtimestamp(mktime(data.published_parsed))
    except Exception as e:
        print(colored.red("[ERROR] At creation parsing date: {0}".format(e)))
        dt = datetime.now()

    return dt


async def content_creation(data, feed, category, loop):
    row = {}

    try:
        if (len(category) > 0) & (len(feed) > 0) & (len(data.title) > 0) & (len(data.link) > 0):
            row['category'] = category
            row['feed'] = feed
            row['title'] = data.title
            row['url'] = data.link
            row['feed_content'] = await get_feed_content(data=data)
            body = await get_body_from_internet(url=row['url'])
            if len(body.top_image) > 0:
                row['image_url'] = await get_image(url=body.top_image)
            else:
                row['image_url'] = None
            if len(body.text) > 0:
                st = smart_text(body.text[:6000])
                row['working_content'] = st
                row['cleaned_text'] = await text_cleaner(data=st)
            else:
                row['working_content'] = None
                row['cleaned_text'] = None
            if not (row['cleaned_text'] is None):
                row['summary'] = await summarizer(data=row['cleaned_text'], sentences=settings.SUMMARIZER_SENTENCES)
            else:
                row['summary'] = None
            if not (row['working_content'] is None):
                row['sentiment'] = await sentiment(data=row['working_content'])
            else:
                row['sentiment'] = None
            row['date'] = await get_date(data=data)
            if not (row['cleaned_text'] is None):
                if len(row['cleaned_text']) > 0:
                    row['tags'] = await keyword_extractor(data=row['cleaned_text'])
                else:
                    row['tags'] = []
            else:
                row['tags'] = []

            await posts_to_db(row=row, loop=loop)

    except Exception as e:
        print(colored.red("[ERROR] At content creation: {0}".format(e)))


async def parse_item(posts, data, feed, category, i, loop):
    try:
        post = posts.get(title=data.entries[i].title)
        if settings.SHOW_DEBUG:
            print(colored.green("Article is in database: {0}.".format(post.title)))
    except Exception as e:
        if data.entries[i].title:
            if await title_dropper(data.entries[i].title):
                if settings.SHOW_DEBUG:
                    print(colored.green("This article not in db: '{0}'".format(data.entries[i].title)))
                try:
                    if len(data.entries[i].link) < 150:
                        await content_creation(data=data.entries[i], feed=feed, category=category, loop=loop)
                except Exception as e:
                    print(colored.red("[ERROR] At content cretion iterator: {0}.".format(e)))
                sleep(settings.DELAY_REQUESTS)


async def get_data_from_feed(feed, posts, loop):
    try:
        data = feedparser.parse(feed)
        if data.bozo == 0:
            items = []
            category = data['feed']['title']
            if len(category) > 0:
                asyncio.gather(*[parse_item(\
                    posts=posts, data=data, feed=feed, category=category, \
                    i=i, loop=loop) for i in range(0, len(data.entries))], \
                    return_exceptions=True
                )
        else:
            err = data.bozo_exception
            print(colored.red("Feed {0} is malformed: {1}".format(feed, err)))
            s = Sources.objects.get(feed=feed)
            if s.failures < 5:
                s.failures = s.failures + 1
            else:
                s.failures = s.failures + 1
                s.active = False
            s.save()
    except Exception as e:
        print(colored.red("At get_data_from_feed {}".format(e)))


async def parse_feed(feed, posts, loop):
    try:
        if settings.SHOW_DEBUG:
            print("Working with: {0}".format(feed))
        await get_data_from_feed(feed=feed, posts=posts, loop=loop)
    except Exception as e:
        print(colored.red("[ERROR] At parse feed {0}: {1}".format(feed, e)))


def parse_all_feeds(loop):
    posts = Post.objects
    sources_ = Sources.objects.all().filter(active=True).values('feed')
    feeds = [s['feed'] for s in sources_]
    sample = random.sample(feeds, len(feeds))

    if posts.all().count() > 0 or posts.all().count() == 0:
        loop.run_until_complete(asyncio.gather(*[parse_feed(\
            feed=feed, posts=posts, loop=loop) for feed in sample], \
            return_exceptions=True
        ))


def sources_to_db():
    """
    Used to parse sources from text list of tuples.
    """
    data = [('', '')]

    for item in data:
        try:
            feeds_to_db(item)
        except Exception as e:
            print(colored.red(e))
    print(colored.green("Done"))


async def check_source(source):
    posts = Post.objects.filter(feed=source).count()
    if posts == 0:
        s = Sources.objects.get(feed=source["feed"])
        s.active = False
        s.save()


def empty_sources(loop):
    sources = Sources.objects.filter(active=True)

    loop.run_until_complete(asyncio.gather(*[check_source( source=source)\
        for source in sources], return_exceptions=True
    ))
