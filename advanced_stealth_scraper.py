#!/usr/bin/env python3
"""
Advanced Stealth Web Scraper for Financial News
Bypasses anti-bot detection with human-like behavior and Gmail authentication
Targets: Investing.com and Forex Factory
"""

import random
import time
import json
import pickle
import os
from datetime import datetime, timezone, timedelta
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
import logging
import config

# Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler('stealth_scraper.log'),
#         logging.StreamHandler()
#     ]
# )
logger = logging.getLogger("stealth_scraper")

class AdvancedStealthScraper:
    def __init__(self):
        self.driver = None
        self.session_file = "scraper_session.pkl"
        self.proxy_list = [
            # Free proxy list - replace with premium residential proxies for production
            "proxy1.example.com:8080",
            "proxy2.example.com:8080",
            "proxy3.example.com:8080"
        ]
        self.current_proxy_index = 0
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        self.today_utc = datetime.now(timezone.utc).date()
        
    def get_next_proxy(self):
        """Get next proxy from rotation list."""
        if not self.proxy_list:
            return None
        
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return proxy
    
    def setup_stealth_browser(self, use_proxy=False):
        """Setup undetected Chrome for live scraping (bypasses Cloudflare)."""
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            if use_proxy and self.proxy_list:
                proxy = self.get_next_proxy()
                if proxy:
                    options.add_argument(f'--proxy-server=http://{proxy}')
                    logger.info(f"Using proxy: {proxy}")
            window_sizes = ['1920,1080', '1366,768', '1440,900']
            options.add_argument(f'--window-size={random.choice(window_sizes)}')
            logger.info("Setting up undetected Chrome for live scraping...")
            # Explicitly use Chrome version 144 to match installed Chrome
            self.driver = uc.Chrome(options=options, use_subprocess=True, version_main=144)
            
            # Execute advanced stealth JavaScript
            stealth_js = """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'permissions', {get: () => ({query: () => Promise.resolve({state: 'granted'})})});
            
            // Override canvas fingerprinting
            const getContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type) {
                if (type === '2d') {
                    const context = getContext.call(this, type);
                    const getImageData = context.getImageData;
                    context.getImageData = function(x, y, w, h) {
                        const imageData = getImageData.call(this, x, y, w, h);
                        for (let i = 0; i < imageData.data.length; i += 4) {
                            imageData.data[i] += Math.floor(Math.random() * 10) - 5;
                            imageData.data[i + 1] += Math.floor(Math.random() * 10) - 5;
                            imageData.data[i + 2] += Math.floor(Math.random() * 10) - 5;
                        }
                        return imageData;
                    };
                    return context;
                }
                return getContext.call(this, type);
            };
            
            // Override WebGL fingerprinting
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) Iris(TM) Graphics 6100';
                }
                return getParameter.call(this, parameter);
            };
            """
            self.driver.execute_script(stealth_js)
            
            # Random initial delay
            time.sleep(random.uniform(2, 5))
            
            logger.info("Advanced stealth browser with proxy rotation initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Stealth browser setup failed: {e}")
            return False
    
    def human_like_behavior(self):
        """Simulate human-like browsing behavior."""
        try:
            # Random mouse movements
            action = ActionChains(self.driver)
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                action.move_by_offset(x, y).perform()
                time.sleep(random.uniform(0.1, 0.3))
            
            # Random scrolling
            scroll_amount = random.randint(100, 500)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.5, 1.5))
            
            # Random page interaction
            if random.choice([True, False]):
                try:
                    clickable_elements = self.driver.find_elements(By.CSS_SELECTOR, "a, button")
                    if clickable_elements:
                        element = random.choice(clickable_elements[:5])
                        action.move_to_element(element).perform()
                        time.sleep(random.uniform(0.2, 0.8))
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Human behavior simulation error: {e}")
    
    def handle_gmail_authentication(self, email, password):
        """Handle Gmail authentication with 2FA support."""
        try:
            logger.info("Attempting Gmail authentication...")
            
            # Navigate to Gmail login
            self.driver.get("https://accounts.google.com/signin")
            time.sleep(random.uniform(2, 4))
            
            # Enter email
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            
            # Human-like typing
            for char in email:
                email_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            time.sleep(random.uniform(0.5, 1.5))
            
            # Click Next
            next_button = self.driver.find_element(By.ID, "identifierNext")
            next_button.click()
            time.sleep(random.uniform(2, 4))
            
            # Enter password
            password_field = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.NAME, "password"))
            )
            
            # Human-like password typing
            for char in password:
                password_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            time.sleep(random.uniform(0.5, 1.5))
            
            # Click Next
            password_next = self.driver.find_element(By.ID, "passwordNext")
            password_next.click()
            time.sleep(random.uniform(3, 6))
            
            # Handle 2FA if present
            try:
                # Check for 2FA prompt
                two_fa_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-step-name='2sv']"))
                )
                logger.warning("2FA detected - manual intervention required")
                logger.info("Please complete 2FA verification manually...")
                
                # Wait for user to complete 2FA
                WebDriverWait(self.driver, 120).until(
                    EC.url_contains("myaccount.google.com")
                )
                logger.info("2FA completed successfully")
                
            except TimeoutException:
                # No 2FA required or already completed
                pass
            
            # Save session cookies
            self.save_session()
            logger.info("Gmail authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False
    
    def save_session(self):
        """Save browser session for reuse."""
        try:
            cookies = self.driver.get_cookies()
            session_data = {
                'cookies': cookies,
                'user_agent': self.driver.execute_script("return navigator.userAgent;"),
                'timestamp': datetime.now().isoformat()
            }
            
            with open(self.session_file, 'wb') as f:
                pickle.dump(session_data, f)
            
            logger.info("Session saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def load_session(self):
        """Load saved browser session."""
        try:
            if not os.path.exists(self.session_file):
                return False
            
            with open(self.session_file, 'rb') as f:
                session_data = pickle.load(f)
            
            # Check if session is still valid (less than 24 hours old)
            session_time = datetime.fromisoformat(session_data['timestamp'])
            if datetime.now() - session_time > timedelta(hours=24):
                logger.info("Session expired, will create new one")
                return False
            
            # Load cookies
            for cookie in session_data['cookies']:
                try:
                    self.driver.add_cookie(cookie)
                except:
                    pass
            
            logger.info("Session loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False
    
    def bypass_cloudflare(self):
        """Advanced Cloudflare bypass techniques."""
        try:
            # Check if we're on a Cloudflare challenge page
            page_source = self.driver.page_source.lower()
            
            if any(indicator in page_source for indicator in ['cloudflare', 'checking your browser', 'just a moment']):
                logger.info("Cloudflare challenge detected, attempting bypass...")
                
                # Wait for challenge to complete
                max_wait = 15  # Reduced from 30 to fail faster
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    current_source = self.driver.page_source.lower()
                    
                    if not any(indicator in current_source for indicator in ['cloudflare', 'checking your browser']):
                        logger.info("Cloudflare challenge passed")
                        return True
                    
                    # Simulate human behavior during wait
                    self.human_like_behavior()
                    time.sleep(random.uniform(1, 3))
                
                logger.warning("Cloudflare challenge timeout")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Cloudflare bypass error: {e}")
            return False
    
    def scrape_investing_com_advanced(self):
        """Advanced scraping of Investing.com with stealth measures."""
        events = []
        
        try:
            logger.info("Starting advanced Investing.com scraping...")
            
            # Navigate with session management
            self.driver.get("https://www.investing.com")
            time.sleep(random.uniform(3, 6))
            
            # Load session if available
            self.load_session()
            
            # Human-like behavior
            self.human_like_behavior()
            
            # Navigate to economic calendar
            self.driver.get("https://www.investing.com/economic-calendar/")
            time.sleep(random.uniform(4, 8))
            
            # Bypass any protection
            if not self.bypass_cloudflare():
                logger.error("Failed to bypass Investing.com protection")
                return []
            
            # Wait for calendar to load
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.ID, "economicCalendarData")),
                        EC.presence_of_element_located((By.CLASS_NAME, "economic-calendar")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='economic-calendar']"))
                    )
                )
            except TimeoutException:
                logger.error("Economic calendar not found on Investing.com")
                return []
            
            # Filter for today's events
            today_filter_attempts = [
                "//button[contains(text(), 'Today')]",
                "//a[contains(text(), 'Today')]",
                "//span[contains(text(), 'Today')]",
                f"//button[@data-date='{self.today_utc.isoformat()}']"
            ]
            
            for filter_xpath in today_filter_attempts:
                try:
                    today_button = self.driver.find_element(By.XPATH, filter_xpath)
                    today_button.click()
                    logger.info("Successfully filtered for today's events")
                    time.sleep(random.uniform(2, 4))
                    break
                except:
                    continue
            
            # Extract events with multiple selectors
            event_selectors = [
                ".economic-calendar tbody tr",
                "#economicCalendarData tr",
                "[data-test='calendar-row']",
                ".calendar-row"
            ]
            
            rows = []
            for selector in event_selectors:
                try:
                    rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if rows:
                        logger.info(f"Found {len(rows)} events using selector: {selector}")
                        break
                except:
                    continue
            
            if not rows:
                logger.error("No event rows found with any selector")
                return []
            
            # Extract event data
            for i, row in enumerate(rows[:20]):  # Limit to first 20
                try:
                    # Multiple attempts to extract data
                    time_selectors = [".time", "[data-test='time']", ".calendar-time"]
                    currency_selectors = [".currency", "[data-test='currency']", ".flag"]
                    event_selectors = [".event", "[data-test='event']", ".calendar-event"]
                    impact_selectors = [".impact", "[data-test='impact']", ".calendar-impact"]
                    
                    time_text = self.extract_text_with_selectors(row, time_selectors)
                    currency_text = self.extract_text_with_selectors(row, currency_selectors)
                    event_text = self.extract_text_with_selectors(row, event_selectors)
                    impact_text = self.extract_text_with_selectors(row, impact_selectors)
                    
                    if currency_text == "USD" and time_text and event_text:
                        try:
                            # Parse time with multiple formats
                            event_time = self.parse_time_flexible(time_text)
                            if event_time:
                                event_datetime = datetime.combine(self.today_utc, event_time)
                                # Fix: Assume scraped time is Local (browser time), convert to UTC
                                # Previously: event_datetime_utc = event_datetime.replace(tzinfo=timezone.utc)
                                event_datetime_utc = event_datetime.astimezone(timezone.utc)
                                
                                events.append({
                                    'name': event_text,
                                    'time': event_datetime_utc,
                                    'forecast': 'N/A',
                                    'headline': event_text,
                                    'currency': 'USD',
                                    'impact': impact_text or 'Unknown',
                                    'source': 'Investing.com'
                                })
                                
                                logger.info(f"Extracted: {time_text} | {currency_text} | {event_text}")
                        except:
                            continue
                            
                except Exception as e:
                    logger.debug(f"Failed to extract event {i}: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(events)} events from Investing.com")
            return events
            
        except Exception as e:
            logger.error(f"Investing.com advanced scraping failed: {e}")
            return []
    
    def scrape_forex_factory_advanced(self):
        """Advanced scraping of Forex Factory with stealth measures."""
        events = []
        
        try:
            logger.info("Starting advanced Forex Factory scraping...")
            
            # Navigate with session management
            self.driver.get("https://www.forexfactory.com")
            time.sleep(random.uniform(3, 6))
            
            # Load session if available
            self.load_session()
            
            # Human-like behavior
            self.human_like_behavior()
            
            # Navigate to calendar with today's date
            today_url = f"https://www.forexfactory.com/calendar?date={self.today_utc.isoformat()}"
            self.driver.get(today_url)
            time.sleep(random.uniform(4, 8))
            
            # Advanced Cloudflare bypass
            if not self.bypass_cloudflare():
                logger.error("Failed to bypass Forex Factory protection")
                return []
            
            # Wait for calendar with multiple strategies
            calendar_selectors = [
                ".calendar__row",
                "[class*='calendar'][class*='row']",
                ".calendar-row",
                "tr[class*='calendar']"
            ]
            
            rows = []
            for selector in calendar_selectors:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if rows:
                        logger.info(f"Found {len(rows)} calendar rows using: {selector}")
                        break
                except:
                    continue
            
            if not rows:
                logger.error("No calendar rows found with any selector")
                return []
            
            # Extract events
            for i, row in enumerate(rows):
                try:
                    # Multiple selector strategies for each field
                    currency_selectors = [".calendar__currency", "[class*='currency']"]
                    time_selectors = [".calendar__time", "[class*='time']"]
                    event_selectors = [".calendar__event", "[class*='event']"]
                    impact_selectors = [".calendar__impact", "[class*='impact']"]
                    forecast_selectors = [".calendar__forecast", "[class*='forecast']"]
                    actual_selectors = [".calendar__actual", "[class*='actual']"]
                    previous_selectors = [".calendar__previous", "[class*='previous']"]
                    
                    currency = self.extract_text_with_selectors(row, currency_selectors)
                    time_str = self.extract_text_with_selectors(row, time_selectors)
                    event_name = self.extract_text_with_selectors(row, event_selectors)
                    impact = self.extract_impact_with_selectors(row, impact_selectors)
                    forecast = self.extract_text_with_selectors(row, forecast_selectors)
                    actual = self.extract_text_with_selectors(row, actual_selectors)
                    previous = self.extract_text_with_selectors(row, previous_selectors)
                    
                    if currency == "USD" and time_str and event_name:
                        # Check for high impact
                        if "high" in impact.lower():
                            try:
                                event_time = self.parse_time_flexible(time_str)
                                if event_time:
                                    event_datetime = datetime.combine(self.today_utc, event_time)
                                    # Fix: Assume scraped time is Local (browser time), convert to UTC
                                    # Previously: event_datetime_utc = event_datetime.replace(tzinfo=timezone.utc)
                                    event_datetime_utc = event_datetime.astimezone(timezone.utc)
                                    
                                    events.append({
                                        'name': event_name,
                                        'time': event_datetime_utc,
                                        'forecast': forecast,
                                        'actual': actual,
                                        'previous': previous,
                                        'headline': event_name,
                                        'currency': 'USD',
                                        'impact': impact,
                                        'source': 'ForexFactory'
                                    })
                                    
                                    logger.info(f"Extracted: {time_str} | {currency} | {event_name} | {impact}")
                            except:
                                continue
                                
                except Exception as e:
                    logger.debug(f"Failed to extract event {i}: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(events)} events from Forex Factory")
            return events
            
        except Exception as e:
            logger.error(f"Forex Factory advanced scraping failed: {e}")
            return []
    
    def extract_text_with_selectors(self, element, selectors):
        """Extract text using multiple selector strategies."""
        for selector in selectors:
            try:
                sub_element = element.find_element(By.CSS_SELECTOR, selector)
                text = sub_element.text.strip()
                if text:
                    return text
            except:
                continue
        return ""
    
    def extract_impact_with_selectors(self, element, selectors):
        """Extract impact information with multiple strategies."""
        for selector in selectors:
            try:
                impact_element = element.find_element(By.CSS_SELECTOR, selector)
                
                # Try to get title attribute first
                impact_title = impact_element.get_attribute("title")
                if impact_title:
                    return impact_title
                
                # Try to get text content
                impact_text = impact_element.text.strip()
                if impact_text:
                    return impact_text
                
                # Try to get from child span
                try:
                    span = impact_element.find_element(By.TAG_NAME, "span")
                    span_title = span.get_attribute("title")
                    if span_title:
                        return span_title
                except:
                    pass
                    
            except:
                continue
        return "Unknown Impact"
    
    def parse_time_flexible(self, time_str):
        """Parse time with multiple format support."""
        time_formats = [
            "%I:%M%p",      # 6:00PM
            "%I:%M %p",     # 6:00 PM
            "%H:%M",        # 18:00
            "%H:%M:%S",     # 18:00:00
            "%I%p",         # 6PM
            "%I %p"         # 6 PM
        ]
        
        time_str = time_str.strip().replace(" ", "").upper()
        
        for fmt in time_formats:
            try:
                return datetime.strptime(time_str, fmt).time()
            except ValueError:
                continue
        
        return None
    
    def retry_with_backoff(self, func, max_retries=2, use_proxy_rotation=True):
        """Execute function with exponential backoff retry and proxy rotation."""
        for attempt in range(max_retries):
            try:
                result = func()
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.info(f"Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                    
                    # Reset browser for retry with proxy rotation
                    if self.driver:
                        self.driver.quit()
                    
                    # Use proxy on retry if enabled
                    use_proxy = use_proxy_rotation and attempt > 0
                    self.setup_stealth_browser(use_proxy=use_proxy)
        
        return []
    
    def rotate_ip_address(self):
        """Rotate IP address using proxy or other methods."""
        try:
            if self.proxy_list:
                logger.info("Rotating IP address using proxy...")
                if self.driver:
                    self.driver.quit()
                self.setup_stealth_browser(use_proxy=True)
                return True
            else:
                logger.warning("No proxies available for IP rotation")
                return False
        except Exception as e:
            logger.error(f"IP rotation failed: {e}")
            return False
    
    def run_advanced_scraping(self, gmail_email=None, gmail_password=None):
        """Run the complete advanced scraping process."""
        try:
            logger.info("Starting Advanced Stealth Scraping Suite")
            logger.info("=" * 60)
            
            # Setup browser
            if not self.setup_stealth_browser():
                return []
            
            all_events = []
            
            # Gmail authentication if credentials provided
            if gmail_email and gmail_password:
                logger.info("Attempting Gmail authentication for enhanced access...")
                self.handle_gmail_authentication(gmail_email, gmail_password)
            
            # Scrape Forex Factory with retry
            logger.info("\n[FOREX FACTORY] Advanced scraping with stealth...")
            forex_events = self.retry_with_backoff(self.scrape_forex_factory_advanced)
            if forex_events:
                all_events.extend(forex_events)
                logger.info(f"SUCCESS: {len(forex_events)} events from Forex Factory")
            
            # Save results
            results = {
                'timestamp': datetime.now().isoformat(),
                'today_date': str(self.today_utc),
                'total_events': len(all_events),
                'investing_events': 0,
                'forex_factory_events': len(forex_events) if forex_events else 0,
                'events': [
                    {
                        'name': e['name'],
                        'time': e['time'].isoformat(),
                        'currency': e['currency'],
                        'source': e['source'],
                        'impact': e.get('impact', 'Unknown')
                    } for e in all_events
                ]
            }
            
            with open('advanced_scraper_results.json', 'w') as f:
                json.dump(results, f, indent=2)
            
            logger.info(f"\nADVANCED SCRAPING COMPLETE:")
            logger.info(f"Total events extracted: {len(all_events)}")
            logger.info("Investing.com: 0 (disabled)")
            logger.info(f"Forex Factory: {len(forex_events) if forex_events else 0}")
            logger.info("Results saved to 'advanced_scraper_results.json'")
            
            return all_events
            
        except Exception as e:
            logger.error(f"Advanced scraping failed: {e}")
            return []
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser closed")

def main():
    """Main function for advanced scraper."""
    print("Advanced Stealth Financial News Scraper")
    print("=" * 50)
    print("Features:")
    print("- Advanced anti-bot detection bypass")
    print("- Human-like browsing behavior")
    print("- Gmail authentication support")
    print("- Session persistence")
    print("- Intelligent retry mechanisms")
    print("- Today's news filtering")
    print("=" * 50)
    
    # Run without Gmail authentication for automated testing
    gmail_email = None
    gmail_password = None
    
    # Uncomment below for interactive mode with Gmail auth
    # try:
    #     gmail_email = input("Gmail email (optional, press Enter to skip): ").strip()
    #     if gmail_email:
    #         import getpass
    #         gmail_password = getpass.getpass("Gmail password: ")
    # except EOFError:
    #     print("Running in automated mode without Gmail authentication")
    
    scraper = AdvancedStealthScraper()
    success = scraper.run_advanced_scraping(gmail_email, gmail_password)
    
    if success:
        print("\nSUCCESS: Advanced scraping completed!")
        print("Check 'advanced_scraper_results.json' for results")
        print("Check 'stealth_scraper.log' for detailed logs")
    else:
        print("\nFAILED: Advanced scraping failed!")
        print("Check 'stealth_scraper.log' for error details")

if __name__ == "__main__":
    main()
