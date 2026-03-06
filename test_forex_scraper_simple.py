#!/usr/bin/env python3
"""
Simple Forex Factory Scraper Test Script
Tests live scraping for today's date using undetected Chrome (bypasses Cloudflare).
"""

import sys
import json
from datetime import datetime, timezone
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_test_simple.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("scraper_test")

class SimpleForexTester:
    def __init__(self):
        self.driver = None
        self.today_utc = datetime.now(timezone.utc).date()

    def setup_browser(self):
        """Setup undetected Chrome for live scraping (bypasses Cloudflare)."""
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            logger.info("Setting up undetected Chrome for live Forex Factory scraping...")
            # Explicitly use Chrome version 144 to match installed Chrome
            self.driver = uc.Chrome(options=options, use_subprocess=True, version_main=144)
            logger.info("Browser setup successful")
            return True
        except Exception as e:
            logger.error(f"Browser setup failed: {e}")
            return False

    def navigate_to_today(self):
        """Navigate to today's date on Forex Factory (undetected Chrome bypasses Cloudflare)."""
        try:
            logger.info("Navigating to Forex Factory calendar (live)...")
            today_url = "https://www.forexfactory.com/calendar?day=today"
            self.driver.get(today_url)
            logger.info(f"Navigated to: {today_url}")
            time.sleep(5)  # Allow page and JS to load
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False

    def extract_events_selenium(self):
        """Extract events from the current page (often blocked by Cloudflare)."""
        try:
            logger.info("Extracting events from current page (Selenium)...")
            time.sleep(2)

            rows = self.driver.find_elements(By.CLASS_NAME, "calendar__row")
            logger.info(f"Found {len(rows)} calendar rows with 'calendar__row'")

            if len(rows) == 0:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "[class*='calendar'][class*='row']")
                logger.info(f"Found {len(rows)} calendar rows with CSS selector")

            if len(rows) == 0:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "tr[class*='calendar']")
                logger.info(f"Found {len(rows)} calendar rows with broad selector")

            if len(rows) == 0:
                all_rows = self.driver.find_elements(By.TAG_NAME, "tr")
                logger.info(f"Found {len(all_rows)} total table rows on page")
                page_source = self.driver.page_source
                if "Verifying you are human" in page_source or "Just a moment" in page_source:
                    logger.warning("Cloudflare challenge detected - Selenium cannot see the calendar.")
                if "calendar" in page_source.lower():
                    logger.info("Page contains 'calendar' text - calendar might be present")
                with open('debug_page_source.html', 'w', encoding='utf-8') as f:
                    f.write(page_source)
                logger.info("Page source saved to 'debug_page_source.html' for manual inspection")

            events = []
            today_utc = datetime.now(timezone.utc).date()

            for i, row in enumerate(rows):
                try:
                    currency = row.find_element(By.CLASS_NAME, "calendar__currency").text.strip()
                    time_str = row.find_element(By.CLASS_NAME, "calendar__time").text.strip()
                    event_name = row.find_element(By.CLASS_NAME, "calendar__event").text.strip()
                    try:
                        impact_element = row.find_element(By.CLASS_NAME, "calendar__impact")
                        impact_title = impact_element.find_element(By.TAG_NAME, "span").get_attribute("title") or "No Impact"
                    except Exception:
                        impact_title = "No Impact"
                    try:
                        event_time = datetime.strptime(time_str.strip(), "%I:%M%p").time()
                        today_local = datetime.now().date()
                        event_datetime = datetime.combine(today_local, event_time)
                        event_datetime_utc = event_datetime.replace(tzinfo=timezone.utc)
                        if event_datetime_utc.date() == today_utc:
                            events.append({
                                'currency': currency,
                                'time': time_str,
                                'name': event_name,
                                'impact': impact_title,
                                'datetime': event_datetime_utc.isoformat()
                            })
                            if i < 10:
                                logger.info(f"Event {i}: {currency} | {time_str} | {event_name} | {impact_title}")
                    except ValueError:
                        pass
                except Exception:
                    pass

            logger.info(f"Extracted {len(events)} events for today (Selenium)")
            return events

        except Exception as e:
            logger.error(f"Event extraction failed: {e}")
            return []

    def run_test(self):
        """Run the complete test: live scraping only (undetected Chrome)."""
        try:
            logger.info("Starting Forex Factory Live Scraping Test")
            logger.info("="*50)

            if not self.setup_browser():
                return False

            if not self.navigate_to_today():
                return False

            events = self.extract_events_selenium()

            results = {
                'test_date': datetime.now().isoformat(),
                'today_utc': str(self.today_utc),
                'total_events': len(events),
                'source': 'live_scrape',
                'events': events
            }
            with open('scraper_test_results_simple.json', 'w') as f:
                json.dump(results, f, indent=2)

            logger.info(f"Test completed. Found {len(events)} events for today (live scrape)")
            logger.info("Results saved to 'scraper_test_results_simple.json'")

            return len(events) > 0

        except Exception as e:
            logger.error(f"Test failed: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser closed")

def main():
    """Main function."""
    print("Forex Factory Scraper Test")
    print("=" * 30)

    tester = SimpleForexTester()
    success = tester.run_test()

    if success:
        print("Test completed successfully!")
    else:
        print("Test failed!")

if __name__ == "__main__":
    main()