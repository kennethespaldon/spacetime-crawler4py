from scraper import save_stats, print_report

save_stats(
    "https://www.ics.uci.edu/about",
    ["uci", "computer", "science", "uci"]
)

save_stats(
    "https://vision.ics.uci.edu/research",
    ["computer", "vision", "research"]
)

save_stats(
    "https://www.ics.uci.edu/about#section",
    ["duplicate"]
)

print_report()