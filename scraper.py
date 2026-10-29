import re
import shelve
from urllib.parse import urlparse, urljoin, urldefrag, quote
from bs4 import BeautifulSoup

MAX_CONTENT_BYTES = 5 * 1024 * 1024   # skip responses larger than ~5 MB
MIN_WORDS = 50                        # pages with fewer words are treated as low information and checked for repeated shrot pages
MAX_URL_LENGTH = 200                  # URL length limit to reduce possible crawler traps

page_stat = shelve.open("page_stats.shelve")
visited_low_info = set()

# Common URL patterns that could generate repetitive pages or traps
TRAP_PATTERN = re.compile(
    r"/calendar|/events?/.*\d{4}-\d{2}|\d{4}-\d{2}-\d{2}"
    r"|[?&;](?:ical|outlook-ical|tribe-bar-date|share|replytocom|rev|version|idx|c|o)="
    r"|[?&;]do=(diff|revisions|edit|media|index|backlink|export)"
    r"|[?&;]action=(login|edit|download|diff|history)"
)

# change the absolute url to defragmented ASCII url 
def make_ascii(base, href): 
    try: 
        abs_url = urljoin(base, href)
        abs_url = urldefrag(abs_url)[0]

        #  Reject non-ASCIi hostnames
        if not urlparse(abs_url).netloc.isascii(): 
            return None

        # encode nonASCII characters
        abs_url = quote(abs_url, safe=":/?#[]@!$&'()*+,;=%")


        return abs_url

    except (ValueError, TypeError):
        return None
    
# Save each page's word count and frequencies in the shelf
def save_stats(url, words):
    url = urldefrag(url)[0]

    if url in page_stat: 
        return 

    page_stat[url] = {
        "word_count" : len(words),
        "freq": count_freq(words)
    }
    page_stat.sync()

# Clear all saved statistics when starting a completely new crawl
def reset_stats():
    page_stat.clear()
    page_stat.sync()


# Make sure statistics are saved and close the shelve file
def close_stats():
    page_stat.sync()
    page_stat.close()


# count word frequencies
def count_freq(words): 

    freqs = dict()

    for word in words: 
        word = word.lower()
        if word in freqs: 
            freqs[word] += 1
        else: 
            freqs[word] = 1

    return freqs

# load stop words from stopwords file
def load_stopwords(): 
    stopwords = set()

    with open("stopwords.txt", "r", encoding = "utf-8") as file: 
        for line in file: 
            word = line.strip().lower()
            if word: 
                stopwords.add(word)

    return stopwords


# get top 50 words
def get_top_50():
    stopwords = load_stopwords()
    total_freq = {}

    for stats in page_stat.values():
        for word, count in stats["freq"].items():

            if len(word) < 2 and word.isalpha(): 
                continue

            if word in stopwords:
                continue

            if word in total_freq:
                total_freq[word] += count
            else:
                total_freq[word] = count

    reversed = sorted(
        total_freq.items(),
        key=lambda item: item[1],
        reverse=True
    )[:50]

    return reversed

# Get subdomains
def get_subdomains(): 
    subdomains = {}

    for url in page_stat: 
        hostname = urlparse(url).hostname

        if hostname and hostname.endswith(".ics.uci.edu"):
            if hostname in subdomains: 
                subdomains[hostname] += 1
            else: 
                subdomains[hostname] = 1

    return sorted(subdomains.items())

# Get the number of unique pages crawled
def get_unique_page_count():
    return len(page_stat)


# Find the page with the largest word count
def get_longest_page():
    longest_url = None
    longest_word_count = 0

    for url, stats in page_stat.items():
        if stats["word_count"] > longest_word_count:
            longest_url = url
            longest_word_count = stats["word_count"]

    return longest_url, longest_word_count

# Create the report required
def create_report(filename="report.txt"):
    unique_pages = get_unique_page_count()
    longest_url, longest_word_count = get_longest_page()
    top_words = get_top_50()
    subdomains = get_subdomains()

    with open(filename, "w", encoding="utf-8") as report:
        report.write("CS 121 - Assignment 2: Web Crawler Report\n\n")

        # Number of unique pages
        report.write("1. Unique Pages\n")
        report.write(f"{unique_pages}\n\n")

        # Longest page
        report.write("2. Longest Page\n")
        report.write(f"URL: {longest_url}\n")
        report.write(f"Word Count: {longest_word_count}\n\n")

        # Top 50 words
        report.write("3. 50 Most Common Words\n")
        for word, frequency in top_words:
            report.write(f"{word}, {frequency}\n")

        report.write("\n")

        # ICS subdomains
        report.write("4. ICS Subdomains\n")
        for subdomain, page_count in subdomains:
            report.write(f"http://{subdomain}, {page_count}\n")

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    links = []
    visited = set()

    raw = resp.raw_response

    # redirect that was not followed: return the target so the frontier crawls it
    if 300 <= resp.status < 400:
        location = raw.headers.get("Location") if raw is not None else None
        if location:
            target = make_ascii(resp.url, location)
            if target is not None: 
                links.append(target)

        return links

    # if the status returns other than 200, then return links
    if resp.status != 200:
        return links

    # for the case of raw_response is none, then return links
    if raw is None:
        return links

    content = raw.content

    # dead url: 200 status but no content
    if not content:
        return links

    # skip non-html responses and very large files
    content_type = raw.headers.get("Content-Type", "").lower()
    if content_type and "html" not in content_type:
        return links

    if len(content) > MAX_CONTENT_BYTES:
        return links

    try:
        # parse the content
        soup = BeautifulSoup(content, "html.parser", from_encoding="utf-8")
    except Exception:
        return links


    # Remove script and style content before extracting text
    for tag in soup(["script", "style"]):
        tag.decompose()

    words = re.findall(r"[a-zA-Z0-9]+(?:'[a-zA-Z0-9]+)*", soup.get_text(" ").lower())

    if is_valid(resp.url): 
        save_stats(resp.url, words) 

    # Extract hyperlinks from the webpage
    for tag in soup.find_all("a", href = True):
        href = tag["href"]

        # skip malformed hrefs
        # creating ASCII url 
        abs_url  = make_ascii(resp.url, href)
        if abs_url is None: 
            continue

        # Avoid returning duplicate links from the same pages
        if abs_url not in visited:
            visited.add(abs_url)
            links.append(abs_url)

    # Check short pages for repeated content and outgoing links
    if len(words) < MIN_WORDS:

        signature = (
            tuple(word.lower() for word in words), # All words extracted from the page, including repeated ones
            tuple(sorted(link for link in links if is_valid(link))) # valid outgoing links from the webpage
        )

        # if we already have the exact same signature, then stop exploring outgoing links from the page
        if signature in visited_low_info:
            return []

        # else we store new signature
        visited_low_info.add(signature)

    
    return links

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)

        if not url.isascii(): 
            return False
        
        if parsed.scheme not in set(["http", "https"]):
            return False

        hostname = parsed.hostname

        if hostname is None: 
            return False

        allowed_domains = (
            "ics.uci.edu",
            "cs.uci.edu",
            "informatics.uci.edu",
            "stat.uci.edu"
        )

        # Check whether the hostname belongs to allowed domain
        valid_domain = False
        for domain in allowed_domains: 
            if hostname == domain or hostname.endswith("."+domain): 
                valid_domain = True

        if not valid_domain:
            return False

        # avoid infinite traps: overly long urls
        if len(url) > MAX_URL_LENGTH:
            return False

        # avoid infinite traps: the same path segment repeated 3+ times (e.g. /a/b/a/b/a)
        segments = [s for s in parsed.path.split("/") if s]
        if any(segments.count(s) >= 3 for s in set(segments)):
            return False

        # avoid calendars, wiki revisions, sort orders and share links
        if TRAP_PATTERN.search(parsed.path.lower() + "?" + parsed.query.lower()):
            return False
        
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise
