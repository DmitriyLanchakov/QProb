# QProb

QProb - fully automatic resources aggregator/ summarization platform. It is part of old concept about content auto-generation.

# Demo(s)

All websites have their own theme and distribute summarized content through various channels, like Twitter, Facebook, Feedburner, RSS.

* https://qprob.com/ (quantitative trading)
* https://stckmrktnws.com (stock market)
* https://bsnssnws.com/ (business)
* https://entreprnrnws.com/ (entrepreneurship)
* https://realestenews.com/ (real estate investing)
* https://parameterless.com/ (technology)

# Technologies

* Nginx
* uWSGI
* memcached
* MySQL
* Python 3.6
* Django 1.11

# TODO

* ~~API~~
* Drop full Anaconda, not needed and too big.
* ~~Async tasks.~~
* Interlink.
* MySQL, uWSGI, nginx, monit configs automation.
* Archives
* Redis as cache server.
* Postgres as db option.
* FIX Keywords/tags.
* Related stories
* URL shortener for Twitter statuses.

# "Issues"

* Amazon doesn't allow use of their reviews. This feature is experimental.
* As API requires Sanic, under Windows, Sanic should be built without uvloop.

# History

* 2004-2008. At first it was simple shell script that created websites out from tnohing. It ran over 1000 websites on 5 servers and generated me a home.
* 2015-2016. Qprob on Wordpress, MongoDB and Python 2.7 backend.
* 2016+. This one.

# Big Things for far Future

* A.I. generated content and/or images.
and/or:
* Automatic crawling.
