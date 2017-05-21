from datetime import datetime
from time import mktime
import random
from os import listdir, rename, remove
from os.path import isfile, join

import feedparser
from newspaper import Article, Config
from textblob import TextBlob
from clint.textui import colored

from django.db import connection
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text, iri_to_uri
from django.db import IntegrityError

from .models import Sources, Twits, TwitsByTag, Tags, Post, Category
from . import summarize
from .facebook_publisher import face_publish
from .twitter import post_tweet, twitter_date, get_tweets_by_tag, get_tweets
from .amazon import parse_amazon
import warnings
warnings.filterwarnings("ignore")

#TODO refactor parsing mess, still too many errors
#TODO implement optimized images functions: start_opt, del_nonopt, use_opt,...

def feeds_to_db(data):
    sources = Sources.objects.create(feed = data[0], twitter_handle=data[1].replace('https://twitter.com/', '').replace('http://twitter.com/', ''))
    sources.save()


def tweets_to_db():
    sources_ = Sources.objects.all().filter(active=True).values('twitter_handle')

    sources = []
    for s in sources_:
        if not (s['twitter_handle'] == ''):
            sources.append(s['twitter_handle'])

    sample = random.sample(sources, len(sources))
    print((colored.yellow("Samples count {0} out from {1}sources".format(len(sample), len(sources)))))

    for source in sample:
        print((colored.green("Twitter handle: {0}".format(source))))
        data = get_tweets(source)
        if data is None:
            break

        for entry in data:
            try:
                sourc_obj = Sources.objects.get(twitter_handle=entry.user.screen_name)
                t = Twits.objects.create(tweet_id=entry.id, content=entry.text, \
                        twitter_handle=sourc_obj, screen_name=entry.user.name, \
                        profile_image=entry.user.profile_image_url, hashtags=entry.hashtags, \
                        date=twitter_date(entry.created_at))
                t.save()
                print((colored.green("Tweet cached to db.")))
            except Exception as e:
                print((colored.red("Continuing...: {0}").format(e)))
                continue


def tweets__by_tag_to_db():
    tags = Tags.objects.filter(type='T').filter(financial=True)

    for tag in tags:
        print((colored.green("Processing tag: {0}".format(tag))))
        tweets = get_tweets_by_tag(tag)
        if tweets is None:
            break

        for tweet in tweets:
            try:
                t = TwitsByTag.objects.create(tweet_id=tweet.id, content=tweet.text, \
                    twitter_handle=tweet.user.screen_name, screen_name=tweet.user.name, \
                    profile_image=tweet.user.profile_image_url, hashtags=tweet.hashtags, \
                    date=twitter_date(tweet.created_at), by_tag=tag)
                t.save()
                print((colored.green("Tweet inserted into db.")))
            except Exception as e:
                print((colored.red("Continuing...: {0}".format(e))))
                continue


def twit_cleaner(tweets):
    from .text_tools import replace_all

    replacements = { "u'": "", ")": "", "]": "", "'": "", ",": ""}
    for tweet in tweets:
        for each in tweet.hashtags.split('Hashtag'):
            if 'Text' in each:
                hashtag = replace_all(each.split('Text=')[1], replacements)
                try:
                    tweet.tags.add(hashtag)
                    tag = Tags.objects.create(title=hashtag, type='T')
                    tag.save()
                    print(("Tag {0} saved.".format(hashtag)))
                except Exception as e:
                    print(("This tag {0} already exists.".format(hashtag)))
                    print(e)
                    continue


def clean_tweet_hashtags():
    tweets = Twits.objects.all()
    twit_cleaner(tweets)
    tweets = TwitsByTag.objects.all()
    twit_cleaner(tweets)


def posts_to_db(data):
    from textwrap import wrap
    from .youtube import do_youtube_once

    for row in data:
        print((colored.green("Data for insertion: {0}, {1}".format(row['title'], row['date']))))

        #get category for the post
        cat = wrap(row['category'], 40)[0]
        print((colored.green("New category name if changed: {0}".format(cat))))

        try:
            if len(cat) > 0:
                category_ = Category.objects.get(title=cat)
            else:
                category_ = Category.objects.get(title='Unknown')
        except ObjectDoesNotExist:
            if len(cat) > 0:
                category_ = Category.objects.create(title=cat, slug='')
                category_.save()
            else:
                category_ = Category.objects.create(title='Unknwon', slug='')
                category_.save()

        #get feed for the post
        feed_ = Sources.objects.get(feed=row['feed'])

        #construct the entry
        try:
            if len(row['title']) > settings.MINIMUM_TITLE:
                entry = Post.objects.create(title=row['title'], \
                    url=row['url'], image=row['image_url'],\
                    # movies=row['movie_url'],
                    working_content=row['cleaned_text'], \
                    content=row['cleaned_text'], summary=row['summary'], \
                    date=row['date'], sentiment=row['sentiment'], \
                    category=category_, feed=feed_, feed_content=row['feed_content'], \
                    pub_date=datetime.now())

                try:
                    if row['tags']:
                        for tg in row['tags']:
                            try:
                                tag = Tags.objects.get(title=tg)
                            except ObjectDoesNotExist:
                                tag = Tags.objects.create(title=tg)
                                tag.save()
                            entry.tags.add(tag)
                except Exception as e:
                    print((colored.red("[ERROR] At tag creation: {0}".format(e))))

            if settings.GET_YOUTUBE:
                print("Going to youtube...")
                entry = do_youtube_once(entry)

            entry.save()
            print((colored.green("Data inserted to db.")))

            if settings.POST_TO_TWITTER:
                print("Going to Twitter...")
                post_tweet(row)

            if settings.POST_TO_FACEBOOK:
                print("Going to Facebook...")
                face_publish(row)

            if settings.GET_AMAZON:
                parse_amazon(title=row['title'])
        except Exception as e:
            print((colored.red("[ERROR] At post to db: {0}".format(e))))


def get_body_from_internet(url):
    config = Config()
    config.browser_user_agent = settings.HEADERS['User-Agent']

    article = Article(url)
    article.download()
    article.parse()
    return article


def summarizer(data, sentences):
    try:
        ss = summarize.SimpleSummarizer()
        summary =  ss.summarize(data, sentences)
    except Exception as e:
        print((colored.red("At summarizer: {0}".format(e))))

    return summary


def sentiment(data):
    blob = TextBlob(data)
    return round(blob.sentiment.polarity, 2)


def title_dropper(title):
        #get a list of removals from file
        removals_ = open(join(settings.BASE_DIR, "aggregator", 'data', 'title_stops.txt'), 'r')
        removals = []
        for r in removals_:
            removals.append(r.replace('\n', ''))

        for r in removals:
            if r in title:
                return False

        return True


def title_cleaner_from_db():
    articles = Post.objects.all()

    for article in articles:
        if title_dropper(article.title) is False:
            print((colored.green("This article should be deleted: {0}".format(article.title))))
            d = article.delete()
            print((colored.green("Answer: {0}".format(title_cleaner_from_db))))


def text_cleaner(data):
    from nltk.tokenize import sent_tokenize

    keep_endings = ['.', '?']

    #get a list of removals from file
    removals_ = open(join(settings.BASE_DIR, "aggregator", 'data', 'stop_sentences.txt'), 'r')
    removals = []
    for r in removals_:
        removals.append(r.replace('\n', ''))

    #get not too short paragrpahs.
    text = data.split('\n')
    paragraphs = []
    for p in text:
        if len(p) > settings.MINIMUM_PARAGRAPH:
            paragraphs.append(p)

    #clean text
    paragraphs_ = ""
    for p in paragraphs:
        sentence_tokens = sent_tokenize(p)
        paragraph = ""
        for sentence in sentence_tokens:
            if sentence[-1] in keep_endings:
                    if len(sentence) > settings.MINIMUM_SENTENCE:
                        #should remove most of the code:
                        if sentence[0].isupper():
                            if not any(to_remove in sentence for to_remove in removals):
                                #eliminate some bad ending strings:
                                if not sentence.endswith(('e.g.', 'i.e.')):
                                    paragraph += "{0} ".format(sentence)
                                    #print "Sentence added: {0}".format(sentence)

        paragraphs_ +=  "<p>{0}</p>".format(paragraph)
        #print "Paragrapah added: {0}".format(paragraphs_)

    return paragraphs_


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


def update_db_with_cleaned_content():
    articles = Post.objects.all()

    for article in articles:
        entry = Post.objects.get(title=article.title)

        try:
            entry.content = text_cleaner(entry.working_content)
            entry.save()
        except Exception as e:
            print((colored.red("[ERROR] At update db with cleaned content;ea: {0}".format(e))))


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


def content_if_empty_all():
    from bs4 import BeautifulSoup

    empty_posts = Post.objects.raw("SELECT * FROM aggregator_post WHERE LENGTH(working_content) < 50")

    for e in empty_posts:
        try:
            if len(e.working_content) < 50 and len(e.feed_content) > 50:
                soup = BeautifulSoup(e.feed_content)
                text = ''.join(soup.findAll(text=True))
                e.content = text_cleaner(text)
                e.summary = summarizer(text, settings.SUMMARIZER_SENTENCES)
                e.sentiment = sentiment(text)
                e.parsed = True
                e.save()
                print((colored.green("Empty post updated with feed content: {0}".format(e.title))))
            else:
                e.content = ""
                e.summary = ""
                e.parsed = True
                e.save()
        except Exception as e:
            print((colored.red("[ERROR] At content if emtpy [all] : {0}".format(e))))
            continue


def content_if_empty(data):
    from bs4 import BeautifulSoup

    try:
        e = Post.objects.get(title=data)
        if len(e.working_content) < 50 and len(e.feed_content) > 50:
            soup = BeautifulSoup(e.feed_content)
            text = ''.join(soup.findAll(text=True))
            e.content = text_cleaner(text)
            e.summary = summarizer(text, settings.SUMMARIZER_SENTENCES)
            e.sentiment = sentiment(text)
            e.parsed = True
            e.save()
            print(("Empty post updated with feed content: {0}".format(e.title)))
        else:
            e.content = ""
            e.summary = ""
            e.parsed = True
            e.save()
    except Exception as e:
        print((colored.red("[ERROR] At content if emtpy : {0}".format(e))))


def clean_images_from_db_if_no_folder():
    path = join(settings.BASE_DIR, 'uploads')
    print((colored.green(b"Path: {0}".format(path))))

    filenames = [b"uploads/{0}".format(f) for f in listdir(path) if isfile(join(path, f))]

    posts = Post.objects.all()

    i = 0
    for post in posts:
        if not (post.image in filenames):
            if not (post.image == ''):
                print((colored.red(b"Image not in folder: {0}".format(post.image))))
                post.image = None
                post.save()
        else:
            print((colored.green(b"Image in folder: {0}".format(post.image))))


def clean_images_if_not_in_db():
    path = filename = join(settings.BASE_DIR, 'uploads')
    print((colored.green("Path: {0}".format(path))))

    filenames = [f for f in listdir(path) if isfile(join(path, f))]

    for file in filenames:
        try:
            post = Post.objects.get(image='uploads/{0}'.format(file))
            print((colored.green("File exists in db: {0}".format(post.image))))
        except:
            print((colored.green("File not in db: {0}".format(file))))
            filename = join(settings.BASE_DIR, 'uploads', file)
            remove(filename)
            print((colored.green("Removed {0}".format(filename))))
            continue


def download_image(url):
    import requests
    from PIL import Image
    import urllib.request, urllib.error, urllib.parse
    import imghdr

    print((colored.green("Image url found by newspaper: {0}".format(url))))

    source = requests.get(url, proxies=settings.PROXIES, headers=settings.HEADERS)
    image_name = url.rsplit('/', 1)[-1].split('?', 1)[0].replace('%', '')

    #print "Image names parsed"
    filename = join(settings.BASE_DIR, 'uploads', image_name)

    post = Post.objects.filter(image="uploads/{0}".format(image_name)).count()
    print((colored.green("Imgs found in db: {0}".format(post))))

    if (post == 0):
        with open(filename, 'wb') as image:
            print((colored.green("Successfully opened image w. path {0}".format(filename))))
            image.write(source.content)
            image.close()

        #check if this is image
        with Image.open(filename) as format_checker:
            width, height = format_checker.size
            if not (format_checker.format is None):
                if width < settings.MINIMUM_IMAGE or height < settings.MINIMUM_IMAGE:
                    print((colored.green("This would be deletd due to size: {0}".format(filename))))
                    format_checker.close()
                    remove(filename)
                    return ''
                else:
                    format_checker.close()
                    print((colored.green("This would be inserted to db: {0}".format(filename))))
                    return 'uploads/{0}'.format(image_name)
            else:
                print((colored.green("This would be deleted due to None format: {0}".format(filename))))
                format_checker.close()
                remove(filename)
                return ''
    else:
        return 'uploads/{0}'.format(image_name)

    #default return if something goes wrong
    return ''


def keyword_extractor(data):
    from aggregator import rake

    rake_object = rake.Rake(stop_words_path=join(settings.BASE_DIR, "aggregator", 'data', 'stop_words.txt'), min_char_length=3, max_words_length=2, min_keyword_frequency=3)
    keywords = rake_object.run(data)

    keywords_ = []
    if keywords:
        for k in keywords:
            keywords_.append(k[0])

    return keywords_


def content_creation(data, feed, category):
    items = []
    row = {}

    try:
        row['category'] = category
        row['feed'] = feed

        row['title'] = data.title
        row['url'] = data.link
        try:
            row['feed_content'] = data.content
        except Exception as e:
            print((colored.red("[ERROR] At body from feed: {0}".format(e))))
            try:
                row['feed_content'] = data.summary
                print((colored.green("Got feed content from summary.")))
            except Exception as e:
                print((colored.red("[ERROR] At body from feed #2: {0}".format(e))))
                try:
                    row['feed_content'] = data.description
                    print((colored.green("Got feed content from description.")))
                except Exception as e:
                    print((colored.red("[ERROR] At body from feed #3: {0}".format(e))))
                    row['feed_content'] = ''

        print((colored.green("Requesting body from web: {0}".format(row['url']))))

        try:
            body = get_body_from_internet(row['url'])
            print("Got body from internet.")
        except Exception as e:
            print((colored.red("[ERROR] At requesting body from internet: {0}".format(e))))
            body = row['feed_content']

        try:
            if body.top_image:
                image_name = download_image(body.top_image)
                print((colored.green("Image name from body: {0}".format(image_name))))
            else:
                image_name = None
                print((colored.green("No image found in body.")))

            if not (image_name is None):
                row['image_url'] = image_name
            else:
                row['image_url'] = None
        except Exception as e:
            print((colored.red("[ERROR] At content creation image: {0}".format(e))))

        #removed for new youtube parser
        #try:
            #row['movie_url'] = body.movies
        #except Exception as e:
            #print colored.red("[ERROR] At content movies: {0}".format(e))

        try:
            row['working_content'] = smart_text(body.text[:6000])
        except Exception as e:
            print((colored.red("[ERROR] At working content: {0}".format(e))))
            row['working_content'] = ''

        try:
            cleaned = text_cleaner(smart_text(body.text[:6000]))
        except Exception as e:
            print(("[ERROR] At cleaned: {0}".format(e)))
            cleaned = None

        row['cleaned_text'] = cleaned

        if cleaned:
            try:
                row['summary'] = summarizer(data=cleaned, sentences=settings.SUMMARIZER_SENTENCES)
            except Exception as e:
                print((colored.red("[ERROR] At creation summary: {0}".format(e))))
                row['summary'] = ''

        if row['working_content']:
            row['sentiment'] = sentiment(row['working_content'])

        try:
            row['date'] = datetime.fromtimestamp(mktime(data.published_parsed))
        except Exception as e:
            print((colored.red("[ERROR] At creation parsing date: {0}".format(e))))
            row['date'] = datetime.now()

        try:
            row['tags'] = keyword_extractor(cleaned)
        except Exception as e:
            print((colored.red("[ERROR] At tags extraction: {0}".format(e))))
            row['tags'] = []

        items.append(row)

        posts_to_db(items)

    except Exception as e:
        print((colored.red("[ERROR] At content creation: {0}".format(e))))


def get_data_from_feed(feed):
    import time

    data = feedparser.parse(feed)
    if data.bozo == 0:
        #post only not available in db titles
        items = []
        posts = Post.objects
        category = data['feed']['title']
        if posts.all().count() > 0 or posts.all().count() == 0:
            for i in range(0, len(data.entries)):
                try:
                    post = posts.get(title=data.entries[i].title)
                    print((colored.green("Article is in database: {0}.".format(post.title))))
                except Exception as e:
                    print((colored.green("Article NOT in database: {0}.".format(e))))
                    if data.entries[i].title:
                        if title_dropper(data.entries[i].title):
                            #except Post.DoesNotExist:
                            print((colored.green("This article not in db: '{0}'".format(data.entries[i].title))))
                            try:
                                if len(data.entries[i].link) < 150:
                                    content_creation(data.entries[i], feed, category)
                            except Exception as e:
                                print((colored.red("[ERROR] At content cretion iterator: {0}.".format(e))))
                            time.sleep(settings.DELAY_REQUESTS)
    else:
        excep = data.bozo_exception
        print((colored.green("Feed {0} is malformed: {1}".format(feed, excep))))


def parse_all_feeds():
    sources_ = Sources.objects.all().filter(active=True).values('feed')

    sources = []
    for s in sources_:
        sources.append(s['feed'])

    sample = random.sample(sources, len(sources))
    for feed in sample:
        try:
            print((colored.green("Working with: {0}".format(feed))))
            get_data_from_feed(feed)
        except Exception as e:
            print((colored.red("[ERROR] At parse all feeds: {0}".format(e))))


def sources_to_db():
    data = [('', '')]

    for item in data:
        try:
            feeds_to_db(item)
        except Exception as e:
            print((colored.red(e)))
    print((colored.green("Done")))
