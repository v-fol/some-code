import hashlib
from abc import ABCMeta, abstractmethod
from json import dumps as json_dumps
from re import compile as re_compile, IGNORECASE
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup, SoupStrainer

from framework.validators import (
    ProductValidator,
    DefaultCartValidator,
    DefaultSelectionValidator,
    DefaultStockValidator,
)
from result_parser.product_code_checker import check_product_codes
from result_parser.scrape_result_parsers import (
    FullScrapeResultParser,
    MpiScrapeResultParser,
    AvailabilityScrapeResultParser,
)
from scrapers.browser.aiohttp_browser import AiohttpAsyncBrowser
from scrapers.custom_exception import WrongCurrencyPageException
from scrapers.utils import bs_garbage_collector
from scrapers.utils.currency import CurrencyConvert

SELECT_ATTR_LABEL_RE = re_compile(r'^select a?\s?', IGNORECASE)
CHOSE_ATTR_LABEL_RE = re_compile(r'^choose a?\s?', IGNORECASE)


class BaseParser:
    base_url = None
    base_url_parts = None
    bs_features = 'lxml'
    max_allowed_requests = None

    def __init__(self, scraper, url):
        self.scraper = scraper
        self.url = url
        self.soup = None
        if self.base_url:
            self.base_url_parts = urlparse(self.base_url)

    def check_price(self, data, currency=None, check_currency=True, allow_excessive_precision=False):
        if currency is None:
            currency = getattr(self, 'currency', None)
        if not currency:
            raise WrongCurrencyPageException('There is no currency for checking. Please add currency to your parser')

        check_obj = CurrencyConvert(data, currency, check_currency, allow_excessive_precision)
        return check_obj.get_clear_price()

    async def load_document(self, **kwargs):
        return await self.scraper.browser.get(kwargs.pop('url', self.url), **kwargs)

    async def parse_document(self, **kwargs):
        response = await self.load_document(**kwargs)
        return self.create_bs(response)

    def create_bs(self, markup='', features=None, parse_only=None, **kwargs):
        if not isinstance(parse_only, SoupStrainer):
            parse_only = SoupStrainer(parse_only)
        return self.scraper.register_bs(
            BeautifulSoup(
                markup,
                features=features or self.bs_features,
                parse_only=parse_only,
                **kwargs
            )
        )

    def check_url(self, url):
        scheme, netloc, url, params, query, fragment = urlparse(url)
        if not scheme:
            scheme = self.base_url_parts.scheme
        if not netloc:
            netloc = self.base_url_parts.netloc
        return urlunparse((scheme, netloc, url, params, query, fragment))


class BaseScraper(object, metaclass=ABCMeta):
    parser = BaseParser
    browser_class = AiohttpAsyncBrowser

    def __init__(self,
                 classified_store_name,
                 proxy_factory,
                 country,
                 aiohttp_tcp_pool=None,
                 get_raw_html=None):
        # pylint: disable=too-many-arguments
        self.__classified_store_name = classified_store_name
        self._country = country
        self.aiohttp_tcp_pool = aiohttp_tcp_pool
        self.__browser = self._create_browser(
            lambda: proxy_factory.create(self.__classified_store_name, self._country),
            get_raw_html,
        )
        self.bs_references = []
        self.cpu_time = 0.0

    def _create_browser(self, proxy_provider, get_raw_html=None):
        return self.browser_class(
            proxy_provider,
            tcp_pool=self.aiohttp_tcp_pool,
            max_allowed_requests=self.parser.max_allowed_requests,
            get_raw_html=get_raw_html,
        )

    @property
    def _browser(self):
        return self.__browser

    @property
    def browser(self):
        return self._browser

    @property
    def proxy_ip(self):
        return self._browser.proxy_ip

    @property
    def num_of_http_requests(self):
        return self.__browser.num_of_http_requests

    @property
    def overall_network_time(self):
        return self.__browser.overall_network_time

    @property
    def classified_store_name(self):
        return self.__classified_store_name

    @abstractmethod
    async def scrape(self, url):
        """
        :param url: string
        """
        pass

    # pylint:disable=too-many-arguments
    async def run(self, url, affiliate_url, store_id, product_id, page_id):
        """
        :param url: string
        :param affiliate_url: string
        :param store_id: string
        :param product_id: string
        :param page_id: string
        :return: tuple
        """
        with bs_garbage_collector(self):
            self._before_scraping()
            product = await self.scrape(url)
            self._after_scraping(product)

        product['url'] = url
        class_name = self.__class__.__name__
        if class_name.endswith('Full'):
            result_parser = FullScrapeResultParser()
        elif class_name.endswith('Mpi'):
            result_parser = MpiScrapeResultParser()
        else:
            result_parser = AvailabilityScrapeResultParser()
            product['variants'] = check_product_codes(
                product_id, self.classified_store_name, product['variants'], dont_change=True
            )

        schematics_obj = result_parser.parse(product)
        schematics_obj.validate(partial=True)
        product = schematics_obj.to_primitive()

        product['scrapingStatus'] = 0
        product['store_id'] = store_id
        product['product_id'] = product_id
        product['page_id'] = page_id
        product['hash'] = int(hashlib.md5(json_dumps(product).encode()).hexdigest(), 16)
        product['affiliateUrl'] = affiliate_url
        if 'extractedUrl' not in list(product.keys()):
            product['extractedUrl'] = url

        return {
            'product': product,
            'num_of_http_requests': self._browser.num_of_http_requests,
            'overall_network_time': self._browser.overall_network_time,
            'number_of_retries': self._browser.number_of_retries,
            'number_of_timeouts': self._browser.number_of_timeouts,
            'cpu_time': self.cpu_time
        }

    def _before_scraping(self):
        # pylint: disable=protected-access
        self.__browser.cookie_jar.clear()

    def _after_scraping(self, product):
        pass

    def register_bs(self, soup_obj):
        if isinstance(soup_obj, BeautifulSoup):
            self.bs_references.append(soup_obj)
        return soup_obj

    async def fetch_pages(self, sizes_urls, _filter=lambda x: x):
        return [
            self.register_bs(BeautifulSoup(result, 'lxml'))
            for result in await self._browser.get_all(sizes_urls) if _filter
        ]

    @staticmethod
    def get_store_url_base():
        """
        get store url base
        :return string | None
        """
        return None


class AvailabilityScraper(BaseScraper, metaclass=ABCMeta):
    def __init__(self,
                 classified_store_name,
                 proxy_factory,
                 country,
                 aiohttp_tcp_pool=None,
                 get_raw_html=None):
        # pylint: disable=too-many-arguments
        super().__init__(
            classified_store_name=classified_store_name,
            proxy_factory=proxy_factory,
            country=country,
            aiohttp_tcp_pool=aiohttp_tcp_pool,
            get_raw_html=get_raw_html,
        )

    # pylint: disable=C0103
    def get_availability_schema_validator(self):
        return ProductValidator(self.get_cart_validator(), self.get_selection_validator(), self.get_stock_validator())

    @staticmethod
    def get_cart_validator():
        return DefaultCartValidator()

    @staticmethod
    def get_selection_validator():
        return DefaultSelectionValidator()

    @staticmethod
    def get_stock_validator():
        return DefaultStockValidator()

    async def scrape(self, url):
        return await self.parser(self, url).scrape_availability()  # pylint: disable=no-member


class FullScraper(BaseScraper, metaclass=ABCMeta):
    def __init__(self,
                 classified_store_name,
                 proxy_factory,
                 country,
                 aiohttp_tcp_pool=None,
                 get_raw_html=None):
        # pylint: disable=too-many-arguments
        super().__init__(
            classified_store_name=classified_store_name,
            proxy_factory=proxy_factory,
            country=country,
            aiohttp_tcp_pool=aiohttp_tcp_pool,
            get_raw_html=get_raw_html,
        )

    def _after_scraping(self, product):
        """
        make up full scraping results
        :param product: dict
        :return: dict
        """
        self._full_makeup_assets(product)
        self._full_makeup_attributes(product)

    @staticmethod
    def _full_makeup_assets(product):
        # add default asset's element if required
        if product['assets'] and next((False for asset in product['assets'] if not asset['selector']), True):
            assets_dependencies = {}
            for asset in product['assets']:
                for key, value in list(asset['selector'].items()):
                    if not isinstance(value, list):
                        value = [value]
                    asset['selector'][key] = value
                    if key not in assets_dependencies:
                        assets_dependencies.update({key: set()})
                    assets_dependencies[key].update(value)

            for key, values in list(assets_dependencies.items()):
                without_asset = next(
                    (
                        v for v in next((at['values'] for at in product['attributes'] if at['id'] == key), ())
                        if v['id'] not in values
                    ),
                    None,
                )
                if without_asset:
                    product['assets'] = [product['assets'][0].copy()] + product['assets']
                    product['assets'][0]['selector'] = {}
                    break

    @staticmethod
    def _full_makeup_attributes(product):
        """if attributes label starts with "select|choose" remove it"""
        for attr in product['attributes']:
            if attr['label'].lower().startswith('select '):
                attr['label'] = SELECT_ATTR_LABEL_RE.sub('', attr['label'])
            if attr['label'].lower().startswith('choose '):
                attr['label'] = CHOSE_ATTR_LABEL_RE.sub('', attr['label'])

            if not attr['label'][-1].isalpha() and not attr['label'][-1].isdigit():
                attr['label'] = attr['label'][:-1]

            attr['label'] = attr['label'].title()

    async def scrape(self, url):
        return await self.parser(self, url).scrape_full()  # pylint: disable=no-member


class MpiScraper(BaseScraper, metaclass=ABCMeta):
    def __init__(self,
                 classified_store_name,
                 proxy_factory,
                 country,
                 aiohttp_tcp_pool=None,
                 get_raw_html=None):
        # pylint: disable=too-many-arguments
        super().__init__(
            classified_store_name=classified_store_name,
            proxy_factory=proxy_factory,
            country=country,
            aiohttp_tcp_pool=aiohttp_tcp_pool,
            get_raw_html=get_raw_html,
        )

    async def scrape(self, url):
        return await self.parser(self, url).scrape_mpi()  # pylint: disable=no-member
