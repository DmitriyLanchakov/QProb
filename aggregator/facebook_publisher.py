from django.conf import settings
from django.utils.html import strip_tags

import facebook
from clint.textui import colored

from .models import Post


async def face_publish(data):
    cfg = {
        "page_id"      : settings.PAGE_ID,
        "access_token" : settings.ACCESS_TOKEN
    }

    try:
        api = get_api(cfg)
    except Exception as e:
        print((colored.red("[ERROR] At Facebook API!: {0}".format(e))))

    post = Post.objects.get(title=data['title'])

    if post.image:
        attachment =  {
            'name': data['title'],
            'link': '{0}{1}/'.format(settings.DOMAIN, post.slug),
            'description': strip_tags(post.summary),
            'picture': '{0}{1}'.format(settings.DOMAIN, post.image)
        }
    else:
        attachment =  {
            'name': data['title'],
            'link': '{0}{1}/'.format(settings.DOMAIN, post.slug),
            'description': strip_tags(post.summary)
        }

    try:
        status = api.put_wall_post(message=post.title, attachment=attachment)
        print((colored.green("Published to Facebook: {0}".format(post.title))))
    except Exception as e:
        print((colored.red("[ERROR] At Facebook publish: {0}".format(e))))

def get_api(cfg):
    graph = facebook.GraphAPI(cfg['access_token'])

    return graph
