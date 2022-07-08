import scrapy

from itertools import count

from app.spiders.base import BaseSpider
from app.utils import strip_product_id


class Spider(BaseSpider):
    base_url = 'https://website.com/'
    name = 'collection_us'
    start_urls = (base_url, )
    categories_to_skip = (
        'stores',
        'about',
    )

    def parse(self, response):
        index_counter = count()
        for item in response.css('.js-mega-menu-item'):
            name = item.css('a span::text').extract_first().strip()
            if name.lower() in self.categories_to_skip:
                continue

            l1_cat = self._make_category(
                name=name,
                url=self.check_url(item.css('a::attr(href)').extract_first()),
                index=index_counter.__next__(),
            )
            subcats = item.css('.mega-menu-link-list__link')
            if subcats:
                yield l1_cat

                yield from self.parse_second_level(subcats, l1_cat)

            else:
                yield scrapy.Request(
                    url=l1_cat['url'],
                    callback=self.parse_products,
                    dont_filter=True,
                    meta={'category': l1_cat},
                )

    def parse_second_level(self, subcats, l1_cat):
        index_counter = count()
        for item2 in subcats:
            l3_cat = self._make_category(
                name=item2.css('::text').extract_first().strip(),
                url=self.check_url(item2.css('::attr(href)').extract_first()),
                index=index_counter.__next__(),
                parent_id=l1_cat['id'],
            )
            yield scrapy.Request(
                url=l3_cat['url'],
                callback=self.parse_products,
                dont_filter=True,
                meta={'category': l3_cat},
            )

    def parse_third_level(self, subcats, l2_cat):
        index_counter = count()
        for item in subcats:
            l3_cat = self._make_category(
                name=item.css('a::text').extract_first().strip(),
                url=self.check_url(item.css('a::attr(href)').extract_first()),
                index=index_counter.__next__(),
                parent_id=l2_cat['id'],
            )
            yield scrapy.Request(
                url=l3_cat['url'],
                callback=self.parse_products,
                dont_filter=True,
                meta={'category': l3_cat},
            )

    def parse_products(self, response):
        category = response.meta['category']
        if category['name'].lower() == 'gift card':
            category['product_urls'].append({
                'id': strip_product_id(response.url.split('/')[-1]),
                'url': response.url,
            })
            yield category

            return

        category['product_urls'].extend(self.extract_products(response))
        next_page = response.css('.next a')
        if next_page:
            yield scrapy.Request(
                url=self.check_url(next_page.css('::attr(href)').extract_first()),
                callback=self.parse_products,
                dont_filter=True,
                meta={'category': category},
            )

            return

        if category['product_urls']:
            yield category

    def extract_products(self, response):
        products = response.css('.js-lookbook-slider > div') or response.css('.product-card')
        for product in products:
            path = product.css('a::attr(href)').extract_first()
            yield {
                'id': strip_product_id(path.split('/')[-1]),
                'url': self.check_url(path),
            }
