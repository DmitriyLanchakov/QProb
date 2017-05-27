from functools import lru_cache

import asyncio
import uvloop
from sanic import Sanic
from sanic.response import (json, html)
from sanic.exceptions import NotFound
from aoiklivereload import LiveReloader
from aiomysql import create_pool, DictCursor

import settings


#TODO new sites should use ids insetad of slugs for post requetss
#TODO *maybe* provide elastic search results

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.get_event_loop()
app = Sanic(__name__)
reloader = LiveReloader()
reloader.start_watcher_thread()


@app.listener("before_server_start")
async def get_pool(app, loop):
    app.pool = {"aiomysql": await create_pool(host=settings.DATABASE_HOST, port=settings.DATABASE_PORT,
        user=settings.DATABASE_USER, password=settings.DATABASE_PASSWORD,
        db=settings.DATABASE_NAME, maxsize=5)}


@lru_cache(maxsize=None)
@app.route("/", methods=["GET"])
async def home(request):
    return html(settings.REDIRECT_HTML)


@lru_cache(maxsize=None)
@app.route("/posts/", methods=["GET"])
async def posts(request):
    async with app.pool['aiomysql'].acquire() as conn:
        async with conn.cursor(DictCursor) as cur:
            await cur.execute("SELECT title, slug, url, summary, date, \
                sentiment, image, category_id FROM aggregator_post \
                ORDER BY date ASC LIMIT 100;")
            value = await cur.fetchall()
            return json({'data': value })


@lru_cache(maxsize=None)
@app.route("/cats/", methods=["GET"])
async def cats(request):
    async with app.pool['aiomysql'].acquire() as conn:
        async with conn.cursor(DictCursor) as cur:
            await cur.execute("SELECT title, slug FROM aggregator_category;")
            value = await cur.fetchall()
            return json({'data': value })


@lru_cache(maxsize=None)
@app.route("/posts/<cat_slug>/", methods=["GET"])
async def posts_by_cat(request, cat_slug):
    async with app.pool['aiomysql'].acquire() as conn:
        async with conn.cursor(DictCursor) as cur:
            await cur.execute("SELECT posts.title, posts.slug, posts.url, \
                posts.summary, posts.date, posts.sentiment, posts.image, \
                cats.slug AS cat FROM aggregator_post AS posts INNER JOIN \
                aggregator_category AS cats ON posts.category_id = cats.title \
                WHERE cats.slug=%s LIMIT 100;", (cat_slug,))
            value = await cur.fetchall()
            return json({'data': value })


@lru_cache(maxsize=None)
@app.route("/post/<slug>/", methods=["GET"])
async def post_by_id(request, slug):
    async with app.pool['aiomysql'].acquire() as conn:
        async with conn.cursor(DictCursor) as cur:
            await cur.execute("SELECT title, slug, url, summary, date, \
                sentiment, image, category_id FROM aggregator_post \
                WHERE slug=%s;", (slug,))
            value = await cur.fetchone()
            return json({'data': value })


loop.close()
