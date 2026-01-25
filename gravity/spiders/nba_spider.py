import scrapy

class NbaSpider(scrapy.Spider):
    name = "nba"
    allowed_domains = ["nba.com"]
    start_urls = [
        "https://www.nba.com/teams",
    ]

    def parse(self, response):
        # First, get all team links
        team_links = response.css("a[href*='/teams/']::attr(href)").getall()
        
        for team_link in team_links:
            if '/roster' in team_link or '/players' in team_link:
                full_url = response.urljoin(team_link)
                yield scrapy.Request(full_url, callback=self.parse_roster)
            else:
                # Try to construct roster URL
                team_slug = team_link.split('/')[-1] if team_link else None
                if team_slug:
                    roster_url = f"https://www.nba.com/teams/{team_slug}/roster"
                    yield scrapy.Request(roster_url, callback=self.parse_roster)
    
    def parse_roster(self, response):
        # NBA.com roster page structure may vary, try multiple selectors
        players = response.css("div.PlayerList_item, div.roster__player, div.player-card, a[href*='/player/']")
        
        if not players:
            # Try alternative selectors
            players = response.css("tr[data-player-id], .player-row, .roster-player")
        
        for player in players:
            # Extract player information
            name = (
                player.css("a::text").get() or 
                player.css(".player-name::text").get() or
                player.css("span::text").get() or
                player.css("td:first-child::text").get()
            )
            
            link = (
                player.css("a::attr(href)").get() or
                player.css("a[href*='/player/']::attr(href)").get()
            )
            
            position = (
                player.css(".position::text").get() or
                player.css("td:nth-child(2)::text").get() or
                player.css("[data-position]::attr(data-position)").get()
            )
            
            number = (
                player.css(".jersey-number::text").get() or
                player.css("td:nth-child(1)::text").get() or
                player.css("[data-number]::attr(data-number)").get()
            )
            
            if name:
                yield {
                    "name": name.strip(),
                    "link": response.urljoin(link) if link else None,
                    "position": position.strip() if position else None,
                    "number": number.strip() if number else None,
                }

