import time
from os.path import join

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text
from django.utils.html import strip_tags

from .amazon_api import AmazonAPI
from .models import (Post, Books, BooksCat)


def make_summaries(title):
    from .tasks import summarizer

    book = Books.objects.get(title=title)

    try:
        book.summary = summarizer(strip_tags(book.review), (settings.SUMMARIZER_SENTENCES+3))
        book.save()
        print(("Amazon summary saved to database: {0}".format(book.summary)))
    except Exception as e:
        print(("[ERROR] At Amazon summary: {0}".format(e)))


def download_image(url):
    import requests

    print(("Image url to be downloaded: {0}".format(url)))

    source = requests.get(url, proxies=settings.PROXIES, headers=settings.HEADERS)
    image_name = url.rsplit('/', 1)[-1].split('?', 1)[0].replace('%', '')

    #print "Image names parsed"
    filename = join(settings.BASE_DIR, 'uploads', 'books', image_name)

    with open(filename, 'wb') as image:
        image.write(source.content)
        image.close()
        print(("Successfully saved image w. path {0}".format(filename)))

        return 'uploads/books/{0}'.format(image_name)

    #default return if something goes wrong
    return None


def get_amazon_images():
    books = Books.objects.filter(got_image=False)

    for book in books:
        if book.medium_image_url:
            print(("Image from db: {0}".format(book.medium_image_url)))
            image_name = download_image(book.medium_image_url)
            print(("Got image from folder: {0}".format(image_name)))

            if image_name:
                book.image = image_name
                book.got_image = True
                book.save()
                print(("Amazon image saved to database book: {0}".format(book.title)))


def query_amazon(query, howmuch):
    try:
        time.sleep(10)
        amazon = AmazonAPI(settings.AMAZON_ACCESS_KEY, settings.AMAZON_SECRET_KEY, settings.AMAZON_ASSOC_TAG)
        products = amazon.search(Keywords=query, SearchIndex='Books', n=howmuch)
        return products
    except Exception as e:
        print(("[ERROR] At query Amazon: {0}".format(e)))
        products = []
        return products


def create_categories(product, entry):
    try:
        for c in range(0, len(product.browse_nodes)):
            print((product.browse_nodes[c].name))
            try:
                cat = BooksCat.objects.get(id=product.browse_nodes[c].id)
            except ObjectDoesNotExist:
                cat = BooksCat.objects.create(id=product.browse_nodes[c].id, title=product.browse_nodes[c].name)
                cat.save()
                print(("Book category saved: {0}".format(product.browse_nodes[c].name)))

            entry.categories.add(cat)
            print(("Book category added to book: {0}".format(product.browse_nodes[c].name)))
    except Exception as e:
        print(("[ERROR] At Book category creation: {0}".format(e)))


def create_book(product):
    try:
        authors_ = product.authors
        if len(authors_) > 1:
            authors = ', '.join(product.authors)
        else:
            authors = product.authors[0]

        if product.large_image_url:
            image = product.large_image_url
        else:
            image = product.medium_image_url

        #print unicode("Product title: {0}, ASIN: {1}, authors: {2}, date: {3}, price: {4}{5}, review: {6}".format(product.title, product.asin, \
            #authors, product.publication_date, product.list_price[0], \
            #product.list_price[1], smart_text(product.editorial_review)))

        entry = Books.objects.create(title=product.title, \
            asin=product.asin, authors=authors, \
            publication_date=product.publication_date, \
            pages=product.pages, medium_image_url=image, \
            price=product.list_price[0], currency=product.list_price[1], \
            review=product.editorial_review)

        create_categories(product, entry)
        entry.save()
        print(("Book saved: {0}".format(product.title)))
        return entry
    except Exception as e:
        print(("[ERROR] At creating book: {0}".format(e)))
        return None


def parse_by_categories():
    cats = BooksCat.objects.filter(financial=True)

    for cat in cats:
        try:
            print((smart_text(cat.title)))
            products = query_amazon(cat.title, 100)

            for i, product in enumerate(products):
                try:
                    entry = create_book(product)
                except Exception as e:
                    print(("[ERROR] At ctaegory parsing: {0}".format(e)))
                    continue
        except Exception as e:
            print(e)
            continue


def parse_by_keywords():
    keywords = ['trading system', 'quantitative trading', 'momnetum strategy', 'mean reversion straetgy', \
            'mechanical trading strategy', 'algorithmic trading strategy', 'algorithmic trading', 'quants', \
            'swing trading', 'trading', 'investing', 'investments', 'forex strategies', 'stock trading', \
            'stock market', 'forex market', 'futures market', 'how I made', 'day trading', 'market microstructure', \
            'Warren Buffet', 'John Tempelton', 'Philip Fisher', 'Benjamin Graham', 'Peter Lynch', 'George Soros', \
            'Jack Bogle', 'Bill Ackman', 'Peter Thiel', 'Ray Dalio', 'Prince Alwaleed', 'hedge fund', \
            'hedge fund strategyes', 'alpha models', 'data analsysis', 'quantitative investing', 'trading techniques',
            'investment banking', 'futures market', 'volatility', 'risk management', 'technical analysis', \
            'ETF', 'trading techniques']

    for k in keywords:
        try:
            products = query_amazon(k, 100)
            for product in products:
                try:
                    create_book(product)
                    print((colored.green("Book included in post: {0}".format(product.title))))
                except Exception as e:
                    print(("[ERROR] At Amazon product y keyword: {0}".format(e)))
                    continue
        except Exception as e:
            print(("[ERROR] At Amazon keyword: {0}".format(e)))
            continue


def parse_amazon(title):
    post = Post.objects.get(title=title)

    try:
        print((smart_text(post.title)))
        products = query_amazon(post.title, 10)

        for i, product in enumerate(products):
            try:
                entry = create_book(product)
                post.books.add(entry)
                post.got_books = True
                post.save()
                print(("Book included in post: {0}".format(product.title)))
                make_summaries(entry.title)

            except Exception as e:
                print(("[ERROR] At Amazon: {0}".format(e)))
                continue
        get_amazon_images()
    except Exception as e:
        print(e)
        post.got_books = True
        post.save()
        print("Updated book as unsuccessfull Amazon parse.")
        #continue
