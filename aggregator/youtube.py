from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.tools import argparser
from nltk.tokenize import sent_tokenize
from clint.textui import colored

from django.conf import settings
from django.utils.encoding import smart_text

from .models import Video, Post


def youtube_date(value):
    import dateutil.parser

    dte_ = dateutil.parser.parse(value)
    dte = dte_.replace(tzinfo=None)

    return dte


def clean_text(text):
    sentence_tokens = sent_tokenize(text)

    for sentence in sentence_tokens:
        if not ('http' in sentence):
            text += "{0} ".format(sentence)

    return text


def clean_youtube_text():
    videos = Video.objects.all()
    print(("Got: {0} videos".format(videos.count())))

    for video in videos:
        text = ''
        #print u"Video description: {0}".format(video.description)
        if video.description:
            sentence_tokens = sent_tokenize(video.description)

            for sentence in sentence_tokens:
                if not ('http' in sentence):
                    text += "{0} ".format(sentence)
            video.description = text
            video.save()
            print((colored.green("Cleaned video description saved to db: {0}".format(smart_text(video.title)))))


def youtube_search(q, max_results):
    youtube = build(settings.YOUTUBE_API_SERVICE_NAME, settings.YOUTUBE_API_VERSION, developerKey=settings.DEVELOPER_KEY)

    search_response = youtube.search().list(q=q, part="id,snippet", maxResults=max_results).execute()

    videos = []

    for search_result in search_response.get("items", []):
        if search_result["id"]["kind"] == "youtube#video":
            video = {}

            video['title'] = search_result["snippet"]['title']
            video['description'] = search_result["snippet"]['description']
            video['date'] = youtube_date(search_result["snippet"]['publishedAt'])
            video['channel_title'] = search_result["snippet"]['channelTitle']
            video['channel_id'] = search_result["snippet"]['channelId']
            video['video_id'] = search_result["id"]["videoId"]

            #print "that"
            print((video['date']))
            #youtube_date(video['date'])
            videos.append(video)

    return videos


async def do_youtube_once(post):
    try:
        res = youtube_search(q=post.title, max_results=25)
    except Exception as e:
        print(colored.red("Problem with parsing youtube {}".format(e)))

    for entry in res:
        try:
            description = smart_text(clean_text(entry['description']))
            video = Video.objects.create(title=entry['title'], \
                description=description, date=entry['date'], \
                channel_title=entry['channel_title'], \
                channel_id=entry['channel_id'], video_id=entry['video_id'])
            video.save()
            if settings.SHOW_DEBUG:
                print("Video inserted to db.")
            post.videos.add(entry['title'])
        except Exception as e:
            if settings.SHOW_DEBUG:
                print(("[ERROR] At creating video entry: {0}".format(e)))

    return post


def do_youtube():
    posts = Post.objects.all()

    for post in posts:
        try:
            try:
                print(("Requesting videos on: {0}".format(post.title)))

                res = youtube_search(q=post.title, max_results=25)
            except Exception as e:
                print(("[ERROR] At getting videos: {0}".format(e)))
                res = []

            for entry in res:
                try:
                    video = Video.objects.create(title=entry['title'], \
                        description=entry['description'], date=entry['date'], \
                        channel_title=entry['channel_title'], \
                        channel_id=entry['channel_id'], video_id=entry['video_id'])
                    video.save()
                except Exception as e:
                    print(("[ERROR] At updating post: {0}".format(e)))

                post.videos.add(entry['title'])
                post.save()
        except Exception as e:
            print(("[ERROR] At last point: {0}".format(e)))
