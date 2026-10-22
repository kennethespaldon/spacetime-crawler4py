import os 
import sqlite3
import tempfile

from scraper import save_stats, count_freq

with tempfile.TemporaryDirectory() as folder:
    os.chdir(folder)

    # Simulate crawling three pages
    save_stats("https://www.ics.uci.edu/about", 500)
    save_stats("https://www.ics.uci.edu/faculty", 1200)
    save_stats("https://www.ics.uci.edu/about#section1", 500)

    conn = sqlite3.connect("crawl_stat.db")
    cursor = conn.cursor()

    # Test unique page count
    cursor.execute("SELECT COUNT(*) FROM pages")
    print("Unique pages:", cursor.fetchone()[0])

    # Test longest page
    cursor.execute("""
        SELECT url, word_count
        FROM pages
        ORDER BY word_count DESC
        LIMIT 1
    """)
    print("Longest page:", cursor.fetchone())

    words = ["UCI", "computer", "science", "UCI", "science"]

    print(count_freq(words))
    conn.close()