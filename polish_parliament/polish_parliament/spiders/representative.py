import scrapy
from urllib.parse import urljoin
from scrapy_splash import SplashRequest


class RepresentativeSpider(scrapy.Spider):
    name = "representatives"
    base_url = 'https://www.sejm.gov.pl/sejm9.nsf/'
    start_urls = ["https://www.sejm.gov.pl/Sejm9.nsf/poslowie.xsp?type=A"]
    # one representative for testing
    # start_urls = ["https://www.sejm.gov.pl/Sejm9.nsf/posel.xsp?id=016&type=A"]
    result = dict()
    info_div: scrapy.http.Response = None

    # lua script to active all dynamic objects
    click_script = """
function wait_for_element(splash, css)
  maxwait = 10
  local i=0
  
  while not splash:select(css) do
    if i==maxwait then
      splash.error("Timeout waiting for element : " + selector);
    end
    splash:wait(1)
    i=i+1
  end
end

function main(splash)
  assert(splash:go(splash.args.url))
            
  speeches = splash:select('#wystapienia')
  speeches:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdWystapienia"] > div')
  
  actions = splash:select('#int')
  actions:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdInterpelacje"] > div')
  
  votes = splash:select('#glosowania')
  votes:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdGlosowania"] > div')
  
  commissions = splash:select('#komisje')
  commissions:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdKomisje"] > div')
  
  delegations = splash:select('#delegacje')
  delegations:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdDelegacje"] > div')
  
  teams = splash:select('#zespoly')
  teams:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdZespoly"] > div')
  
  offices = splash:select('#biura')
  offices:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdBiura"] > div')
  
  collaborators = splash:select('a[id*="view:_id1:_id2:facetMain:_id189:wsp"]')
  collaborators:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdWsp"] > div')
  
  financial_declarations = splash:select('#osw')
  financial_declarations:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdMajatek"] > div')
  
  benefit_record = splash:select('#rejkorz')
  benefit_record:mouse_click()
  wait_for_element(splash, 'div[id*="view:_id1:_id2:facetMain:_id189:holdKorzysci"] > div')
  
  email = splash:select('a[id*="view:_id1:_id2:facetMain:_id189:_id279"]')
  email:mouse_click()
  wait_for_element(splash, 'a[data-decoded="1"]')
  
  return splash:html()
end
    """

    def parse(self, response: scrapy.http.Response, **kwargs):
        """
        :param response: list of representatives
        :return: results of scrapping
        """
        representatives = self.__get_a_href_list(response)
        for representative in representatives:
            url = urljoin(self.base_url, representative)
            yield SplashRequest(url, callback=self.parse_representative, endpoint='execute',
                                args={'lua_source': self.click_script})
        # one representative for testing
        # yield SplashRequest(response.request.url, callback=self.parse_representative, endpoint='execute',
        #                     args={'lua_source': self.click_script})

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
        self.__get_dynamic_info()
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
                    value = li.css('p.right::text').get()
                    if not value:
                        value = li.css('p.right > a::text').get()
                    self.result[key] = value

        # Opiniowanie projektów UE - Rafał Bochenek
        self.__get_static_datum_from_dynamic_div('#view\:_id1\:_id2\:facetMain\:_id189\:opinieue')
        # Naruszenie zasad etyki poselskiej - Grzegorz Braun
        self.__get_static_datum_from_dynamic_div('#view\:_id1\:_id2\:facetMain\:_id189\:naruszenie')
        # Strona WWW - Wanda Nowicka
        self.__get_static_datum_from_dynamic_div('#view\:_id1\:_id2\:facetMain\:_id189\:_id274', '#poselWWW::text')

    def __get_static_datum_from_dynamic_div(self, css_selector: str, key_css_selector=""):
        """
        Ensure if the static element exists then store it in result.
        :param css_selector: css selector to the static element [value]
        :param key_css_selector: css selector to the static element [key]
        :return:
        """
        element = self.info_div.css(css_selector)
        if element:
            if key_css_selector:
                key = self.info_div.css(key_css_selector).get()
            else:
                key = element.css("::text").get()
            self.result[key] = element.css("::attr(href)").get()

    def __get_dynamic_info(self):
        self.__get_speeches()
        self.__get_actions()
        self.__get_votes()
        self.__get_commissions()
        self.__get_delegations()
        self.__get_teams()
        self.__get_offices()
        self.__get_collaborators()
        self.__get_financial_declarations()
        self.__get_benefit_record()
        self.__get_email()

    def __get_speeches(self):
        # Wystąpienia na posiedzeniach Sejmu
        key = 'wypowiedzi'
        self.result[key] = dict()
        speech_div = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdWystapienia')
        speech_td = speech_div.css('#content > table > tbody > tr > td')
        if speech_td:
            speech_a = speech_td.css('a')
            if speech_a:
                self.result[key]['href'] = speech_a.css('::attr(href)').get()
                self.result[key]['tekst'] = speech_div.css('td::text').get()

    def __get_actions(self):
        # Interpelacje, zapytania, pytania w sprawach bieżących, oświadczenia
        key = 'interpelacje'
        self.result[key] = list()
        action_div = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdInterpelacje')
        rows = action_div.css('tr')
        for i, row in enumerate(rows):
            tds = row.css('td')
            if len(tds) == 3:
                self.result[key].append(dict())
                left_td, right_td = tds[0], tds[1]
                left_a = left_td.css('a')
                self.result[key][i]['nazwa'] = left_a.css('::text').get()
                self.result[key][i]['href'] = left_a.css('::attr(href)').get()
                self.result[key][i]['liczba'] = right_td.css('::text').get()

    def __get_votes(self):
        vote_div = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdGlosowania')
        vote_tds = vote_div.css('td')
        key = 'głosy'
        self.result[key] = dict()
        self.result[key]['procent'] = vote_tds[0].css('::text').get()
        self.result[key]['liczba'] = vote_tds[1].css('::text').get()
        self.result[key]['href'] = vote_tds[2].css('a::attr(href)').get()

    def __get_table(self, key: str, html_element, head_names: list = [], last_column_is_file=False,
                    last_row_is_info=False):
        self.result[key] = list()
        if not head_names:
            head_names = self.__get_table_heads(html_element)
        trs = html_element.css('tbody > tr')
        self.__get_rows(key, trs, head_names, last_column_is_file, last_row_is_info)

    def __get_table_heads(self, div) -> list:
        head_names = list()
        for head_th in div.css('#content > table > thead > tr > th'):
            head_names.append(head_th.css('::text').get())
        return head_names

    def __get_rows(self, key, trs, head_names, last_column_is_file=False, last_row_is_info=False):
        for i, tr in enumerate(trs):
            self.result[key].append(dict())
            tds = tr.css('td')
            for j, td in enumerate(tds):
                if last_row_is_info and i == len(trs) - 1:
                    self.result[key][i]['info'] = td.css('::text').get()
                    break
                elif j == 0:
                    self.result[key][i]['nazwa'] = td.css('::text').get()
                    if not last_column_is_file and not last_row_is_info:
                        a = td.css('a')
                        if a:
                            self.result[key][i]['href'] = a.css('::attr(href)').get()
                elif last_column_is_file and j == len(tds) - 1:
                    self.result[key][i]['plik'] = td.css('::text').get()
                    self.result[key][i]['href'] = td.css('a::attr(href)').get()
                else:
                    self.result[key][i][head_names[j]] = td.css('::text').get()

    def __get_commissions(self) -> None:
        div = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdKomisje')
        self.__get_table('komisje', div)

    def __get_delegations(self) -> None:
        div = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdDelegacje')
        self.__get_table('delegacje', div)

    def __get_teams(self) -> None:
        div = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdZespoly')
        self.__get_table('zespoły', div)

    def __get_offices(self) -> None:
        key = 'biura'
        divs = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdBiura > div#content')
        main_div, reports_div = divs[0], divs[1].css('tbody')
        head_names = [
            "nazwa",
            "adres",
            "telefon",
            "email"
        ]
        self.__get_table(key, main_div, head_names, last_row_is_info=True)
        # Some representatives do not have office reports - e.g., Zbigniew Ajchler
        if reports_div:
            self.__get_table("biurowe raporty", reports_div)

    def __get_collaborators(self) -> None:
        div = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdWspInner')
        head_names = [
            "nazwa",
            "rola"
        ]
        self.__get_table('współpracownicy', div, head_names, last_column_is_file=True)

    def __get_financial_declarations(self):
        tbody = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdMajatekInner > table > tbody')
        head_names = [
            "nazwa"
        ]
        self.__get_table('oświadczenia majątkowe', tbody, head_names, last_column_is_file=True)

    def __get_benefit_record(self):
        key = 'rejestr korzyści'
        self.result[key] = list()
        benefit_div = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:holdKorzysciInner')
        as_ = benefit_div.css('a')
        for i, a in enumerate(as_):
            self.result[key].append(dict())
            self.result[key][i]['nazwa'] = a.css('::text').get()
            self.result[key][i]['href'] = a.css('::attr(href)').get()

    def __get_email(self) -> None:
        self.result['email'] = self.info_div.css('#view\:_id1\:_id2\:facetMain\:_id189\:_id279::text').get()
