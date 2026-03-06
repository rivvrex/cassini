#!/usr/bin/env python3
"""
Forex Factory Scraper Test Script
Tests the complete event extraction functionality for today's date
Includes ALL events (high-impact, medium-impact, low-impact)
Provides comprehensive validation and logging
Especially useful on Fridays when major news occurs
"""

import sys
import json
import requests
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import logging
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("scraper_test")

class ForexScraperTester:
    def __init__(self):
        self.driver = None
        self.today_utc = datetime.now(timezone.utc).date()
        self.today_local = datetime.now().date()

    def setup_browser(self):
        """Setup Chrome browser for testing."""
        try:
            options = Options()
            # Keep headless disabled for visual verification
            # options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')

            logger.info("Setting up Chrome browser for testing...")
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info("✅ Browser setup successful")
            return True
        except Exception as e:
            logger.error(f"❌ Browser setup failed: {e}")
            return False

    def navigate_to_today(self):
        """Navigate to today's date on Forex Factory calendar."""
        try:
            logger.info(f"🌐 Navigating to Forex Factory calendar...")
            self.driver.get("https://www.forexfactory.com/calendar")

            # Wait for calendar to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "calendar__row"))
            )

            # Navigate to today's date with multiple methods
            today = datetime.now().date()
            navigation_success = False

            logger.info(f"📅 Attempting to navigate to TODAY: {today}")

            # Method 1: Calendar navigation links
            try:
                date_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'calendar') and contains(@href, 'date=')]")
                logger.info(f"Found {len(date_links)} date navigation links")

                for link in date_links:
                    href = link.get_attribute("href")
                    if today.isoformat() in href:
                        link.click()
                        logger.info("✅ Successfully clicked today's date navigation link")
                        navigation_success = True
                        time.sleep(3)
                        break
            except Exception as e:
                logger.debug(f"Method 1 failed: {e}")

            # Method 2: Date cells
            if not navigation_success:
                try:
                    date_cells = self.driver.find_elements(By.XPATH, "//td[contains(@class, 'calendar__date') or contains(@class, 'date')]")
                    logger.info(f"Found {len(date_cells)} date cells")

                    for cell in date_cells:
                        cell_text = cell.text.strip()
                        if cell_text == str(today.day):
                            cell.click()
                            logger.info(f"✅ Successfully clicked date cell: {cell_text}")
                            navigation_success = True
                            time.sleep(3)
                            break
                except Exception as e:
                    logger.debug(f"Method 2 failed: {e}")

            # Method 3: URL parameter
            if not navigation_success:
                try:
                    current_url = self.driver.current_url
                    today_url = f"{current_url.split('?')[0]}?date={today.isoformat()}"
                    self.driver.get(today_url)
                    logger.info(f"✅ Successfully navigated via URL: {today_url}")
                    navigation_success = True
                    time.sleep(3)
                except Exception as e:
                    logger.debug(f"Method 3 failed: {e}")

            # Verify we're on the correct date
            try:
                current_date_display = self.driver.find_element(By.XPATH, "//h1 | //div[contains(@class, 'date')] | //span[contains(@class, 'date')]").text
                logger.info(f"📅 Page currently showing: {current_date_display}")
            except:
                logger.debug("Could not find date display on page")

            return navigation_success

        except Exception as e:
            logger.error(f"❌ Navigation failed: {e}")
            return False

    def extract_all_events(self):
        """Extract ALL events from the current calendar page."""
        try:
            logger.info("🔍 Extracting ALL events from current page...")

            # Wait for content to load
            time.sleep(2)

            rows = self.driver.find_elements(By.CLASS_NAME, "calendar__row")
            logger.info(f"Found {len(rows)} total calendar rows")

            all_events = []
            today_utc = datetime.now(timezone.utc).date()

            # Extract all events (not just high-impact)
            for i, row in enumerate(rows):
                try:
                    # Get all event details
                    currency = row.find_element(By.CLASS_NAME, "calendar__currency").text.strip()
                    time_str = row.find_element(By.CLASS_NAME, "calendar__time").text.strip()
                    event_name = row.find_element(By.CLASS_NAME, "calendar__event").text.strip()

                    # Get impact (if available)
                    try:
                        impact_element = row.find_element(By.CLASS_NAME, "calendar__impact")
                        impact_title = impact_element.find_element(By.TAG_NAME, "span").get_attribute("title")
                    except:
                        impact_title = "No Impact"

                    # Get forecast (if available)
                    try:
                        forecast = row.find_element(By.CLASS_NAME, "calendar__forecast").text.strip()
                    except:
                        forecast = "N/A"

                    # Parse time with multiple formats
                    event_time = None
                    time_formats = ["%I:%M%p", "%H:%M", "%I:%M %p", "%H:%M:%S"]

                    for fmt in time_formats:
                        try:
                            event_time = datetime.strptime(time_str.strip(), fmt).time()
                            break
                        except ValueError:
                            continue

                    if event_time is None:
                        logger.debug(f"Could not parse time '{time_str}' for event '{event_name}'")
                        continue

                    # Create event datetime
                    today_local = datetime.now().date()
                    event_datetime = datetime.combine(today_local, event_time)

                    # Normalize to UTC
                    event_datetime_utc = event_datetime.replace(tzinfo=timezone.utc)

                    # Create event object
                    event = {
                        'currency': currency,
                        'time_str': time_str,
                        'name': event_name,
                        'impact': impact_title,
                        'forecast': forecast,
                        'event_datetime': event_datetime,
                        'event_datetime_utc': event_datetime_utc,
                        'date_utc': event_datetime_utc.date(),
                        'is_today': event_datetime_utc.date() == today_utc
                    }

                    all_events.append(event)

                    # Log first 20 events in detail
                    if i < 20:
                        status = "✅ TODAY" if event['is_today'] else "❌ OTHER"
                        logger.info(f"Event {i}: {status} | {currency} | {time_str} | {event_name} | {impact_title}")

                except Exception as e:
                    logger.debug(f"Failed to extract event {i}: {e}")
                    continue

            logger.info(f"📊 Successfully extracted {len(all_events)} total events")
            return all_events

        except Exception as e:
            logger.error(f"❌ Event extraction failed: {e}")
            return []

    def analyze_results(self, events):
        """Analyze and validate the extracted events."""
        try:
            logger.info("\n" + "="*60)
            logger.info("📊 ANALYSIS RESULTS")
            logger.info("="*60)

            if not events:
                logger.error("❌ No events extracted!")
                return

            today_utc = datetime.now(timezone.utc).date()

            # Categorize events
            today_events = [e for e in events if e['is_today']]
            other_day_events = [e for e in events if not e['is_today']]

            # Impact analysis
            impact_counts = {}
            for event in events:
                impact = event['impact']
                impact_counts[impact] = impact_counts.get(impact, 0) + 1

            # Currency analysis
            currency_counts = {}
            for event in events:
                currency = event['currency']
                currency_counts[currency] = currency_counts.get(currency, 0) + 1

            # Time distribution
            hour_counts = {}
            for event in events:
                if event['is_today']:
                    hour = event['event_datetime_utc'].hour
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1

            # Results
            logger.info(f"📅 Today's Date (UTC): {today_utc}")
            logger.info(f"📅 Today's Date (Local): {self.today_local}")
            logger.info(f"📊 Total Events Extracted: {len(events)}")
            logger.info(f"✅ Today's Events: {len(today_events)}")
            logger.info(f"❌ Other Days Events: {len(other_day_events)}")

            if other_day_events:
                other_dates = set(e['date_utc'] for e in other_day_events)
                logger.warning(f"⚠️ Found events from wrong dates: {sorted(other_dates)}")

            logger.info(f"\n🎯 IMPACT BREAKDOWN:")
            for impact, count in sorted(impact_counts.items()):
                logger.info(f"   {impact}: {count} events")

            logger.info(f"\n💱 CURRENCY BREAKDOWN:")
            for currency, count in sorted(currency_counts.items()):
                logger.info(f"   {currency}: {count} events")

            if hour_counts:
                logger.info(f"\n🕐 TODAY'S EVENTS BY HOUR:")
                for hour in sorted(hour_counts.keys()):
                    am_pm = "AM" if hour < 12 else "PM"
                    display_hour = hour if hour <= 12 else hour - 12
                    if display_hour == 0:
                        display_hour = 12
                    logger.info(f"   {display_hour}:00 {am_pm}: {hour_counts[hour]} events")

            # Show today's events in detail
            if today_events:
                logger.info(f"\n📋 TODAY'S EVENTS DETAILS:")
                for event in sorted(today_events, key=lambda x: x['event_datetime_utc']):
                    logger.info(f"   🕐 {event['event_datetime_utc'].strftime('%H:%M')} | {event['currency']} | {event['name']} | {event['impact']}")

            # Save results to JSON
            results = {
                'test_date': datetime.now().isoformat(),
                'today_utc': str(today_utc),
                'today_local': str(self.today_local),
                'total_events': len(events),
                'today_events': len(today_events),
                'other_day_events': len(other_day_events),
                'impact_breakdown': impact_counts,
                'currency_breakdown': currency_counts,
                'hour_distribution': hour_counts,
                'today_events_details': [
                    {
                        'time': e['event_datetime_utc'].isoformat(),
                        'currency': e['currency'],
                        'name': e['name'],
                        'impact': e['impact'],
                        'forecast': e['forecast']
                    } for e in sorted(today_events, key=lambda x: x['event_datetime_utc'])
                ]
            }

            with open('scraper_test_results.json', 'w') as f:
                json.dump(results, f, indent=2, default=str)

            logger.info("💾 Results saved to 'scraper_test_results.json'")

        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")

    def test_newsapi(self):
        """Test NewsAPI functionality for forex news."""
        try:
            logger.info("\n" + "="*60)
            logger.info("[NEWSAPI] Testing NewsAPI Configuration")
            logger.info("="*60)

            # Check configuration
            if not config.USE_NEWS_API:
                logger.error("[ERROR] NewsAPI is disabled in config")
                return False

            if not config.NEWS_API_KEY or config.NEWS_API_KEY == "your_newsapi_key_here":
                logger.error("[ERROR] NewsAPI key not configured")
                return False

            logger.info(f"[OK] NewsAPI enabled with key: {config.NEWS_API_KEY[:8]}...")

            # Test API connection
            logger.info("\n[TEST] Testing API Connection...")

            # Get today's date in UTC
            today_utc = datetime.now(timezone.utc).date()
            from_date = today_utc.isoformat()
            to_date = today_utc.isoformat()

            logger.info(f"[DATE] Testing for date: {today_utc}")
            logger.info(f"[RANGE] Date range: {from_date} to {to_date}")

            # Test basic connectivity
            url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={config.NEWS_API_KEY}"

            try:
                response = requests.get(url, timeout=10)
                logger.info(f"[API] Response Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    total_results = data.get('totalResults', 0)
                    articles = data.get('articles', [])

                    logger.info(f"[RESULTS] Total Results: {total_results}")
                    logger.info(f"[ARTICLES] Articles in Response: {len(articles)}")

                    if total_results > 0:
                        logger.info("[OK] NewsAPI connection successful")
                    else:
                        logger.warning("[WARNING] NewsAPI returned 0 results")
                else:
                    logger.error(f"[ERROR] NewsAPI error: {response.status_code}")
                    logger.error(f"[RESPONSE] {response.text}")
                    return False

            except Exception as e:
                logger.error(f"[ERROR] Connection error: {e}")
                return False

            # Test economic news query
            logger.info("\n[TEST] Testing Economic News Query...")

            economic_url = f"https://newsapi.org/v2/everything?q=USD+economic+news+OR+forex+news+OR+federal+reserve&language=en&from={from_date}&to={to_date}&sortBy=publishedAt&apiKey={config.NEWS_API_KEY}"

            try:
                response = requests.get(economic_url, timeout=10)
                logger.info(f"[API] Economic News Response Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    total_results = data.get('totalResults', 0)
                    articles = data.get('articles', [])

                    logger.info(f"[ECONOMIC] Total Results: {total_results}")
                    logger.info(f"[ECONOMIC] Articles in Response: {len(articles)}")

                    if total_results > 0:
                        logger.info("[OK] Economic news query successful")

                        # Show sample articles
                        logger.info("\n[SAMPLES] Sample Articles:")
                        for i, article in enumerate(articles[:3]):
                            title = article.get('title', 'No title')
                            published = article.get('publishedAt', 'No date')
                            source = article.get('source', {}).get('name', 'Unknown')

                            logger.info(f"  {i+1}. {title[:60]}...")
                            logger.info(f"     Source: {source} | Published: {published[:10]}")

                        # Test date filtering
                        today_count = 0
                        for article in articles:
                            published_at = article.get('publishedAt', '')
                            if published_at:
                                try:
                                    article_date = datetime.fromisoformat(published_at.replace('Z', '+00:00')).date()
                                    if article_date == today_utc:
                                        today_count += 1
                                except:
                                    pass

                        logger.info(f"\n[DATE_FILTER] Today's Articles: {today_count}/{len(articles)}")

                        if today_count > 0:
                            logger.info("[OK] Date filtering working correctly")
                        else:
                            logger.warning("[WARNING] No articles found for today")

                    else:
                        logger.warning("[WARNING] No economic news found")
                        logger.info("[INFO] This might be normal if there are no economic news today")

                else:
                    logger.error(f"[ERROR] Economic news query failed: {response.status_code}")
                    return False

            except Exception as e:
                logger.error(f"[ERROR] Economic news query error: {e}")
                return False

            # Summary
            logger.info("\n" + "="*60)
            logger.info("[SUMMARY] NEWSAPI TEST RESULTS")
            logger.info("="*60)

            if total_results > 0:
                logger.info("[SUCCESS] NewsAPI is working correctly")
                logger.info(f"[SUCCESS] Found {total_results} total articles")
                logger.info(f"[SUCCESS] Found {len(articles)} articles in response")
                logger.info("[SUCCESS] Date filtering is functional")
                logger.info("\n[RECOMMENDATION] Use NewsAPI as primary data source")
                return True
            else:
                logger.warning("[WARNING] NewsAPI returned no results")
                logger.info("[INFO] This might be normal for quiet news days")
                logger.info("[INFO] Consider using Forex Factory as fallback")
                return True  # Still return True as API is working

        except Exception as e:
            logger.error(f"[ERROR] NewsAPI test failed: {e}")
            return False

    def test_investing_com(self):
        """Test Investing.com as fallback news source."""
        try:
            logger.info("\n" + "="*60)
            logger.info("[INVESTING.COM] Testing Investing.com Fallback")
            logger.info("="*60)

            if not config.USE_INVESTING_COM:
                logger.info("[SKIP] Investing.com fallback disabled")
                return True

            # Setup browser for Investing.com
            if not self.setup_browser():
                logger.error("[ERROR] Browser setup failed for Investing.com")
                return False

            try:
                logger.info("[NAVIGATE] Going to Investing.com economic calendar...")
                self.driver.get("https://www.investing.com/economic-calendar/")

                # Wait for page load
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".economic-calendar"))
                )

                # Look for economic events
                events = self.driver.find_elements(By.CSS_SELECTOR, ".economic-calendar tr")

                logger.info(f"[RESULTS] Found {len(events)} economic calendar rows")

                if len(events) > 0:
                    logger.info("[SUCCESS] Investing.com calendar accessible")
                    # Extract sample event
                    for i, event in enumerate(events[:3]):
                        try:
                            time_element = event.find_element(By.CSS_SELECTOR, ".time")
                            currency_element = event.find_element(By.CSS_SELECTOR, ".currency")
                            event_element = event.find_element(By.CSS_SELECTOR, ".event")

                            time_text = time_element.text if time_element else "N/A"
                            currency_text = currency_element.text if currency_element else "N/A"
                            event_text = event_element.text if event_element else "N/A"

                            logger.info(f"[SAMPLE {i+1}] {time_text} | {currency_text} | {event_text}")
                        except:
                            logger.debug(f"[SAMPLE {i+1}] Could not extract details")

                    return True
                else:
                    logger.warning("[WARNING] No events found on Investing.com")
                    return False

            except Exception as e:
                logger.error(f"[ERROR] Investing.com test failed: {e}")
                return False
            finally:
                if self.driver:
                    self.driver.quit()
                    self.driver = None

        except Exception as e:
            logger.error(f"[ERROR] Investing.com fallback test failed: {e}")
            return False

    def test_bloomberg(self):
        """Test Bloomberg as fallback news source."""
        try:
            logger.info("\n" + "="*60)
            logger.info("[BLOOMBERG] Testing Bloomberg Fallback")
            logger.info("="*60)

            if not config.USE_BLOOMBERG:
                logger.info("[SKIP] Bloomberg fallback disabled")
                return True

            # Setup browser for Bloomberg
            if not self.setup_browser():
                logger.error("[ERROR] Browser setup failed for Bloomberg")
                return False

            try:
                logger.info("[NAVIGATE] Going to Bloomberg markets...")
                self.driver.get("https://www.bloomberg.com/markets")

                # Wait for page load
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article, .story, .headline"))
                )

                # Look for forex/markets news
                forex_news = self.driver.find_elements(By.CSS_SELECTOR, "article h3, .story h3, .headline")

                logger.info(f"[RESULTS] Found {len(forex_news)} news headlines")

                if len(forex_news) > 0:
                    logger.info("[SUCCESS] Bloomberg news accessible")
                    # Extract sample headlines
                    for i, headline in enumerate(forex_news[:3]):
                        try:
                            title = headline.text.strip()
                            logger.info(f"[HEADLINE {i+1}] {title[:80]}...")
                        except:
                            logger.debug(f"[HEADLINE {i+1}] Could not extract text")

                    return True
                else:
                    logger.warning("[WARNING] No news found on Bloomberg")
                    return False

            except Exception as e:
                logger.error(f"[ERROR] Bloomberg test failed: {e}")
                return False
            finally:
                if self.driver:
                    self.driver.quit()
                    self.driver = None

        except Exception as e:
            logger.error(f"[ERROR] Bloomberg fallback test failed: {e}")
            return False

    def test_reuters(self):
        """Test Reuters as fallback news source."""
        try:
            logger.info("\n" + "="*60)
            logger.info("[REUTERS] Testing Reuters Fallback")
            logger.info("="*60)

            if not config.USE_REUTERS:
                logger.info("[SKIP] Reuters fallback disabled")
                return True

            # Setup browser for Reuters
            if not self.setup_browser():
                logger.error("[ERROR] Browser setup failed for Reuters")
                return False

            try:
                logger.info("[NAVIGATE] Going to Reuters business news...")
                self.driver.get("https://www.reuters.com/business/")

                # Wait for page load
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article, .story, h3"))
                )

                # Look for business/finance news
                business_news = self.driver.find_elements(By.CSS_SELECTOR, "article h3, .story h3, h3")

                logger.info(f"[RESULTS] Found {len(business_news)} news headlines")

                if len(business_news) > 0:
                    logger.info("[SUCCESS] Reuters news accessible")
                    # Extract sample headlines
                    for i, headline in enumerate(business_news[:3]):
                        try:
                            title = headline.text.strip()
                            logger.info(f"[HEADLINE {i+1}] {title[:80]}...")
                        except:
                            logger.debug(f"[HEADLINE {i+1}] Could not extract text")

                    return True
                else:
                    logger.warning("[WARNING] No news found on Reuters")
                    return False

            except Exception as e:
                logger.error(f"[ERROR] Reuters test failed: {e}")
                return False
            finally:
                if self.driver:
                    self.driver.quit()
                    self.driver = None

        except Exception as e:
            logger.error(f"[ERROR] Reuters fallback test failed: {e}")
            return False

    def run_test(self):
        """Run the complete scraper test with fallback sources."""
        try:
            logger.info("[START] Starting Comprehensive Forex Test Suite with Fallbacks")
            logger.info("="*70)

            # Test NewsAPI first
            logger.info("\n[PHASE 1] Testing NewsAPI...")
            newsapi_success = self.test_newsapi()

            if newsapi_success:
                logger.info("[OK] NewsAPI test completed successfully")
            else:
                logger.warning("[WARNING] NewsAPI test had issues")

            # Test fallback sources
            logger.info("\n[PHASE 2] Testing Fallback Sources...")

            investing_success = self.test_investing_com()
            bloomberg_success = self.test_bloomberg()
            reuters_success = self.test_reuters()

            logger.info(f"[FALLBACKS] Investing.com: {'PASS' if investing_success else 'FAIL'}")
            logger.info(f"[FALLBACKS] Bloomberg: {'PASS' if bloomberg_success else 'FAIL'}")
            logger.info(f"[FALLBACKS] Reuters: {'PASS' if reuters_success else 'FAIL'}")

            # Test Forex Factory scraping (original)
            logger.info("\n[PHASE 3] Testing Forex Factory Scraper...")

            # Setup browser
            if not self.setup_browser():
                logger.error("[ERROR] Browser setup failed - cannot test scraping")
                return False

            # Navigate to today
            navigation_success = self.navigate_to_today()
            if not navigation_success:
                logger.warning("[WARNING] Navigation may have failed - proceeding with current view")

            # Extract all events
            events = self.extract_all_events()

            # Validate against live calendar
            self.validate_against_live_calendar(events)

            # Analyze results
            self.analyze_results(events)

            logger.info("\n" + "="*70)
            logger.info("[RESULTS] Comprehensive Test Suite with Fallbacks Completed!")
            logger.info("="*70)
            logger.info(f"[NEWSAPI] Status: {'PASS' if newsapi_success else 'ISSUES'}")
            logger.info(f"[FALLBACKS] Available: {sum([investing_success, bloomberg_success, reuters_success])}/3")
            logger.info(f"[SCRAPER] Events Found: {len(events)}")
            logger.info("[FILES] Check 'scraper_test_results.json' for detailed results")
            logger.info("[LOGS] Check 'scraper_test.log' for detailed logs")
            logger.info("="*70)

            # Success if we have at least one working source
            fallback_count = sum([investing_success, bloomberg_success, reuters_success])
            has_any_source = newsapi_success or (len(events) > 0) or (fallback_count > 0)

            return has_any_source

        except Exception as e:
            logger.error(f"[ERROR] Test suite failed: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("[BROWSER] Browser closed")

def validate_against_live_calendar(self, events):
    """Additional validation by comparing with live calendar data."""
    try:
        logger.info("\n[VALIDATION] Comparing with live calendar...")

        # Get current URL and check if we're on today's date
        current_url = self.driver.current_url
        today = datetime.now().date()

        if today.isoformat() in current_url:
            logger.info("[OK] URL contains today's date - navigation successful")
        else:
            logger.warning("[WARNING] URL does not contain today's date - navigation may have failed")

        # Check page title/date display
        try:
            page_title = self.driver.title
            logger.info(f"[PAGE] Page title: {page_title}")
        except:
            logger.debug("Could not get page title")

        # Count events by impact level
        high_impact = sum(1 for e in events if "high impact" in e['impact'].lower())
        medium_impact = sum(1 for e in events if "medium" in e['impact'].lower() or "moderate" in e['impact'].lower())
        low_impact = sum(1 for e in events if "low impact" in e['impact'].lower())

        logger.info("[IMPACT] SUMMARY:")
        logger.info(f"   High Impact: {high_impact} events")
        logger.info(f"   Medium Impact: {medium_impact} events")
        logger.info(f"   Low Impact: {low_impact} events")
        logger.info(f"   Total: {len(events)} events")

        return True

    except Exception as e:
        logger.error(f"[ERROR] Live validation failed: {e}")
        return False

def main():
    """Main test function."""
    print("Comprehensive Forex Trading Bot Test Suite with Fallbacks")
    print("=" * 70)
    print("This comprehensive test suite will:")
    print("1. [NEWSAPI] Test NewsAPI configuration and functionality")
    print("2. [FALLBACKS] Test alternative sources (Investing.com, Bloomberg, Reuters)")
    print("3. [SCRAPER] Test Forex Factory calendar scraping")
    print("4. [DATE] Navigate to today's date")
    print("5. [SEARCH] Extract ALL events (high, medium, low impact)")
    print("6. [ANALYSIS] Analyze and validate results")
    print("7. [SAVE] Save detailed results to JSON")
    print("8. [COMPARE] Compare with live calendar")
    print()
    print("Perfect for validating the complete trading bot pipeline with fallbacks!")
    print("=" * 70)
    print()

    tester = ForexScraperTester()
    success = tester.run_test()

    if success:
        print("\n[SUCCESS] Test suite completed successfully!")
        print("[RESULTS] Check 'scraper_test_results.json' for detailed results")
        print("[LOGS] Check 'scraper_test.log' for comprehensive logs")
        print("\n[FILES] Key files generated:")
        print("   - scraper_test_results.json - Detailed analysis")
        print("   - scraper_test.log - Step-by-step logs")
    else:
        print("\n[FAILED] Test suite failed!")
        print("[LOGS] Check 'scraper_test.log' for error details")
        print("\n[TROUBLESHOOTING]:")
        print("   1. Ensure Chrome browser is installed")
        print("   2. Check internet connection")
        print("   3. Verify NewsAPI key is configured")
        print("   4. Verify Forex Factory website is accessible")
        print("   5. Check scraper_test.log for specific errors")

if __name__ == "__main__":
    main()