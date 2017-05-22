from functools import lru_cache

import asyncio
import uvloop
from sanic import Sanic
from sanic.response import (json, html)
from sanic.exceptions import NotFound
from aoiklivereload import LiveReloader
from aiomysql import create_pool

from django.conf import settings


REDIRECT_HTML = """
<html xmlns="http://www.w3.org/1999/xhtml">
 <head>
   <title>{0}</title>
   <meta http-equiv="refresh" content="0;URL='{1}'" />
 </head>
 <body>
 </body>
</html>
""".format(settings.API_REDIRECT_TITLE, settings.API_DESCRIPTION_URL)


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.get_event_loop()


async def jsonify(records):
    return [dict(r.items()) for r in records]


async def pool():
    pool =  await create_pool(host=settings.DATABASE_HOST, port=settings.DATABASE_PORT,
        user=settings.DATABASE_USER, password=settings.DATABASE_PASSWORD,
        db=settings.DATABASE_NAME, loop=loop)
    return pool


app = Sanic(__name__)
if settings.DEV_ENV:
    DOMAIN = str(settings.BASE_URL).split('/')[1]
else:
    DOMAIN = settings.API_HOST

reloader = LiveReloader()
reloader.start_watcher_thread()


@lru_cache(maxsize=None)
@app.route("/", host=DOMAIN, methods=["GET"])
async def home(request):
    return html(REDIRECT_HTML)


@lru_cache(maxsize=None)
@app.route("/posts/", host=DOMAIN, methods=["GET"])
async def posts(request):
    async with pool().acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute("SELECT title, slug, url, summary, date, \
                    sentiment, image, category_id FROM aggregator_post \
                    ORDER BY date ASC LIMIT 100;")
                value = await cur.fetchall()
                return json({'data': await jsonify(value) })
            except:
                raise NotFound("Not foud.")
    pool().close()
    await pool().wait_closed()


@lru_cache(maxsize=None)
@app.route("/cats/", host=DOMAIN, methods=["GET"])
async def posts(request):
    async with pool().acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute("SELECT pk, title, slug FROM aggregator_category;")
                value = await cur.fetchone()
                return json({'data': await jsonify(value) })
            except:
                raise NotFound("Not foud.")
    pool().close()
    await pool().wait_closed()


@lru_cache(maxsize=None)
@app.route("/posts/<cat_slug>/", host=DOMAIN, methods=["GET"])
async def posts(request, cat_slug):
    async with pool().acquire() as conn:
        async with conn.cursor() as cur:
            try:
                #TODO needs better query cleanup
                await cur.execute("SELECT pk, title, slug, url, summary, date, \
                    sentiment, image, category_id FROM aggregator_post WHERE \
                    category_id='%s' LIMIT 100;", str(cat_slug))
                value = await cur.fetchone()
                return json({'data': await jsonify(value) })
            except:
                raise NotFound("Not foud.")
    pool().close()
    await pool().wait_closed()


@lru_cache(maxsize=None)
@app.route("/post/<slug>/", host=DOMAIN, methods=["GET"])
async def posts(request, slug):
    async with pool().acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute("SELECT pk, title, slug, rul, summary, date, \
                    sentiment, image, category_id FROM aggregator_post \
                    WHERE slug='%s';", str(int(pk)))
                value = await cur.fetchone()
                return json({'data': await jsonify(value) })
            except:
                raise NotFound("Not foud.")
    pool().close()
    await pool().wait_closed()


loop.close()
