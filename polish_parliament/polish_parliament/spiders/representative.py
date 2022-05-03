import scrapy
from urllib.parse import urljoin


class RepresentativeSpider(scrapy.Spider):
    name = "representatives"
    base_url = 'https://www.sejm.gov.pl/sejm9.nsf/'
    start_urls = ["https://www.sejm.gov.pl/Sejm9.nsf/poslowie.xsp?type=A"]
    result = dict()
    info_div: scrapy.http.Response = None

    def parse(self, response: scrapy.http.Response, **kwargs):
        representatives = self.__get_a_href_list(response)
        for representative in representatives:
            url = urljoin(self.base_url, representative)
            yield scrapy.Request(url, callback=self.parse_representative)

    def __get_a_href_list(self, response: scrapy.http.Response):
        """
        Get list of href (link's destination) attributes from a (HTML hyperlink).
        :param response: response containing list of representatives
        :return: hrefs of representatives
        """
        return response.css('ul.deputies > li > div > a::attr(href)').getall()

    def parse_representative(self, response: scrapy.http.Response):
        self.result = dict()
        self.info_div = self.__get_info_div(response)
        self.result['nazwa'] = self.__get_name()
        self.result['zdjęcie'] = self.__get_picture()
        data_uls = self.__get_data_uls()
        self.__get_static_info(data_uls)
        # Opiniowanie projektów UE - Rafał Bochenek
        self.__get_static_datum_from_dynamic_div('#view\:_id1\:_id2\:facetMain\:_id189\:opinieue')
        # Naruszenie zasad etyki poselskiej - Grzegorz Braun
        self.__get_static_datum_from_dynamic_div('#view\:_id1\:_id2\:facetMain\:_id189\:naruszenie')
        # Strona WWW - Wanda Nowicka
        self.__get_static_datum_from_dynamic_div('#view\:_id1\:_id2\:facetMain\:_id189\:_id274', '#poselWWW::text')
        yield self.result

    def __get_info_div(self, response: scrapy.http.Response):
        """
        Get information div.
        :return: information div
        """
        return response.css("#title_content")

    def __get_name(self) -> str:
        return self.info_div.css('#title_content > h1::text').get()

    def __get_picture(self) -> str:
        return self.info_div.css('img::attr(src)').get()

    def __get_data_uls(self) -> scrapy.http.Response:
        return self.info_div.css('ul.data')

    def __get_static_info(self, uls: scrapy.http.Response):
        """
        Get information from static HTML elements.
        :param uls: HTML elements to loop through
        """
        for ul in uls[:2]:
            for li in ul.css('li'):
                key = li.css('p.left::text').get()
                if key:
                    self.result[key] = li.css('p.right::text').get()

    def __get_static_datum_from_dynamic_div(self, css_selector: str, key_css_selector=""):
        element = self.info_div.css(css_selector)
        if element:
            if key_css_selector:
                key = self.info_div.css(key_css_selector).get()
            else:
                key = element.css("::text").get()
            self.result[key] = element.css("::attr(href)").get()
