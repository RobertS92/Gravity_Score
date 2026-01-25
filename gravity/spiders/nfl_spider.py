import scrapy

class NflSpider(scrapy.Spider):
    name = "nfl"
    allowed_domains = ["nfl.com"]
    start_urls = [
        "https://www.nfl.com/teams/philadelphia-eagles/roster/",
    ]

    def parse(self, response):
        for player in response.css("div.d3-o-media-object"):
            yield {
                "name": player.css("a.d3-o-media-object__cta::text").get(),
                "link": response.urljoin(player.css("a.d3-o-media-object__cta::attr(href)").get()),
                "position": player.css("span.d3-o-player-roster__player-position::text").get(),
                "number": player.css("span.d3-o-player-roster__player-number::text").get(),
            }
