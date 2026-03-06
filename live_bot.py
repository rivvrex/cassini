#!/usr/bin/env python3
"""
Full-Featured Live Trading Bot with NLP and Precise Entry Logic
Integrates Exness MT5, Forex Factory scraping, FinBERT sentiment analysis, and automated trading
"""

import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import random
import re
import time as time_module
import pandas as pd
import MetaTrader5 as mt5
### FIX: Use the correct model class for classification ###
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import time
from datetime import datetime, timedelta, timezone
import threading
import queue
import logging
import sys
import io

# Fix UnicodeEncodeError on Windows consoles
# Use a safe stream wrapper that handles encoding errors gracefully
class SafeStream:
    def __init__(self, stream):
        self.stream = stream
        self.encoding = getattr(stream, 'encoding', 'utf-8')
    
    def write(self, msg):
        try:
            self.stream.write(msg)
        except UnicodeEncodeError:
            # Fallback: remove emojis/special chars that can't be encoded
            try:
                # Try to encode with replacement and decode back
                safe_msg = msg.encode(self.encoding, errors='replace').decode(self.encoding)
                self.stream.write(safe_msg)
            except Exception:
                # Ultimate fallback: ASCII only
                self.stream.write(msg.encode('ascii', 'replace').decode('ascii'))
                
    def flush(self):
        if hasattr(self.stream, 'flush'):
            self.stream.flush()

if sys.platform == 'win32':
    # Try to set console to utf-8 if possible
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from flask import Flask, render_template, jsonify, request
import webbrowser
import os
from advanced_stealth_scraper import AdvancedStealthScraper
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler(SafeStream(sys.stderr)),
    ],
)
logger = logging.getLogger("live_bot")
EVENT_CACHE = {"schedule": [], "last_fetched": None}

class LiveTradingBot:
    def __init__(self):
        self.running = False
        self.paused = False
        self.thread = None
        self.scraper_thread = None  # Separate thread for scraping
        self.model_loader_thread = None  # Background model loading
        self.events = []
        self.tokenizer = None
        self.model = None
        self.model_loaded = False  # Track model loading status
        self.model_loading = False  # Track if model is being loaded
        self.point = 0.001  # Default for USDJPY, will be updated upon MT5 connection
        self.symbol = "USDJPY"  # Default symbol, will be updated upon MT5 connection
        self.account_data = {}
        self.trade_history = []
        self.scraper_running = False
        self.scrape_lock = threading.Lock()
        # Performance monitoring
        self.last_analysis_time = 0
        self.total_analysis_count = 0
        self.avg_analysis_time = 0
        # Model caching
        self.model_cache_path = "finbert_cache"
        # MT5 connection status
        self.mt5_connected = False
        self.mt5_last_check = 0

        # Start background model loading immediately
        self.start_background_model_loading()

    def normalize_event_time(self, event_time):
        """Normalize event time to UTC timezone for consistent processing."""
        if event_time.tzinfo is None:
            # Assume local time if no timezone info and convert to UTC
            # Selenium scrapers get local time from the browser/system
            try:
                event_time = event_time.astimezone(timezone.utc)
            except Exception:
                # Fallback if astimezone fails on naive object (older python versions or edge cases)
                # Assume system local time is effectively what we have, but we need to make it offset-aware
                event_time = event_time.replace(tzinfo=datetime.now().astimezone().tzinfo).astimezone(timezone.utc)
        else:
            # Convert to UTC
            event_time = event_time.astimezone(timezone.utc)
        return event_time

    def load_events_from_json(self, json_file_path=None):
        """Load events from a JSON file instead of scraping."""
        if json_file_path is None:
            json_file_path = getattr(config, 'EVENTS_JSON_FILE', 'forex_events.json')
        
        try:
            import json
            logger.info(f"Loading events from JSON file: {json_file_path}")
            
            if not os.path.exists(json_file_path):
                logger.warning(f"JSON file not found: {json_file_path}")
                logger.info("Please create a JSON file with your events. See forex_events.json.example for format.")
                return []
            
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                logger.error("JSON file should contain a list of events")
                return []
            
            events = []
            today_utc = datetime.now(timezone.utc).date()
            
            for item in data:
                try:
                    # Parse the date string
                    date_str = item.get('date', '')
                    if not date_str:
                        continue
                    
                    # Parse ISO format date string
                    event_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    event_time_utc = self.normalize_event_time(event_time)
                    
                    # Only include today's events
                    if event_time_utc.date() == today_utc:
                        event = {
                            'name': item.get('title', 'Unknown Event'),
                            'title': item.get('title', 'Unknown Event'),
                            'time': event_time_utc,
                            'date': event_time_utc,  # For compatibility
                            'country': item.get('country', 'N/A'),
                            'currency': item.get('country', 'N/A'),  # For compatibility
                            'impact': item.get('impact', 'Low'),
                            'forecast': item.get('forecast', ''),
                            'actual': item.get('actual', ''),  # Actual result after news release
                            'previous': item.get('previous', ''),
                            'headline': item.get('title', 'Unknown Event'),
                            'source': 'JSON File'
                        }
                        events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to parse event: {item.get('title', 'Unknown')} - {e}")
                    continue
            
            logger.info(f"✅ Loaded {len(events)} events from JSON file for today ({today_utc})")
            return sorted(events, key=lambda x: x['time'])
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in {json_file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading JSON file: {e}")
            return []

    def validate_today_events(self, events):
        """Validate and log today's events for debugging."""
        if not events:
            logger.warning("❌ No events to validate")
            return events

        today_utc = datetime.now(timezone.utc).date()
        today_events = []
        other_dates = set()

        logger.info(f"🔍 VALIDATING EVENTS FOR TODAY: {today_utc}")

        for event in events:
            event_date = event['time'].date()
            if event_date == today_utc:
                today_events.append(event)
                # Special check for 6:00 PM events
                event_time = event['time'].time()
                if event_time.hour == 18 and event_time.minute == 0:  # 6:00 PM
                    logger.info(f"🎯 FOUND 6:00 PM EVENT: {event['name']} at {event_time}")
                logger.debug(f"✅ Valid today event: {event['name']} at {event['time']}")
            else:
                other_dates.add(event_date)
                logger.debug(f"❌ Filtered out event from {event_date}: {event['name']}")

        logger.info(f"✅ FINAL RESULT: Found {len(today_events)} TODAY'S events ({today_utc})")
        if other_dates:
            logger.warning(f"⚠️  Filtered out events from other dates: {sorted(other_dates)}")

        return today_events

    def debug_six_pm_events(self):
        """Debug function to specifically look for 6:00 PM events."""
        logger.info("🔍 DEBUG: Searching for 6:00 PM events...")
        try:
            scraped_events = self.scrape_events_selenium()
            six_pm_events = []

            for event in scraped_events:
                event_time = event['time'].time()
                if event_time.hour == 18 and event_time.minute == 0:  # 6:00 PM
                    six_pm_events.append(event)
                    logger.info(f"🎯 6:00 PM Event Found: {event['name']} - {event['time']}")

            if not six_pm_events:
                logger.warning("❌ No 6:00 PM events found in scraped data")
            else:
                logger.info(f"✅ Found {len(six_pm_events)} events at 6:00 PM")

            return six_pm_events
        except Exception as e:
            logger.error(f"Debug 6:00 PM search failed: {e}")
            return []

    def preload_events(self):
        """Force immediate event loading for fastest startup."""
        logger.info("Preloading events for immediate availability...")
        try:
            # Use unified schedule fetch with locking
            self.fetch_schedule(force_refresh=True)
            logger.info(f"Preloaded {len(self.events)} events successfully")
        except Exception as e:
            logger.error(f"Preload failed: {e}")

    def initialize(self):
        """Initialize all components of the bot."""
        # Clean state first
        self.events = []
        
        # Preload events immediately for sub-second readiness
        self.preload_events()

        if not self.initialize_mt5():
            logger.warning("MT5 initialization failed, but continuing with event fetching")
        
        if not self.initialize_finbert(): return False
        return True

    def initialize_mt5(self):
        try:
            logger.info("Initializing MT5 connection...")
            if not mt5.initialize():
                error_code = mt5.last_error()
                logger.error(f"MT5 initialization failed. Error code: {error_code}")
                logger.error("Please ensure MetaTrader 5 terminal is installed and running.")
                self.mt5_connected = False
                return False
            
            ### IMPROVEMENT: Load credentials securely from config file ###
            logger.info(f"Attempting MT5 login to server: {config.MT5_SERVER}")
            if not mt5.login(login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
                error_code = mt5.last_error()
                logger.error(f"MT5 login failed for account {config.MT5_LOGIN}")
                logger.error(f"Error code: {error_code}")
                logger.error("Please verify your credentials in config.py:")
                logger.error(f"  - Login: {config.MT5_LOGIN}")
                logger.error(f"  - Server: {config.MT5_SERVER}")
                self.mt5_connected = False
                mt5.shutdown()
                return False
            
            # Verify connection by checking account info
            account_info = mt5.account_info()
            if account_info is None:
                logger.error("MT5 login succeeded but account info is unavailable")
                self.mt5_connected = False
                mt5.shutdown()
                return False
            
            logger.info(f"✅ MT5 login successful! Account: {account_info.login}, Balance: {account_info.balance}")
            
            # Try different USDJPY symbol variations that Exness/Vantage might use
            symbol_names = ["USDJPY", "USDJPY.", "USDJPY+", "USDJPY.pro", "USDJPYm", "USDJPYmicro", "USDJPYc"]
            selected_symbol = None

            for symbol_name in symbol_names:
                logger.info(f"Trying to access symbol: {symbol_name}")
                if mt5.symbol_select(symbol_name, True):
                    symbol_info = mt5.symbol_info(symbol_name)
                    if symbol_info:
                        selected_symbol = symbol_name
                        self.point = symbol_info.point
                        logger.info(f"Successfully selected {symbol_name}. Point size: {self.point}")
                        break
                else:
                    logger.warning(f"Failed to select {symbol_name}")

            if not selected_symbol:
                # Get all available symbols and log them for user reference
                symbols = mt5.symbols_get()
                if symbols:
                    usd_symbols = [s.name for s in symbols if "USD" in s.name and "JPY" in s.name]
                    logger.info(f"Available USD/JPY symbols: {usd_symbols}")
                    logger.error("No USD/JPY symbol found. Please check your MT5 terminal and ensure USDJPY is available.")
                    logger.error("Manual steps: 1) Open MT5 terminal 2) Go to Market Watch 3) Right-click 4) Select 'Symbols' 5) Find and enable USDJPY")
                else:
                    logger.error("Could not retrieve symbol list from MT5")
                self.mt5_connected = False
                return False

            # Store the working symbol name for trading
            self.symbol = selected_symbol
            self.mt5_connected = True
            logger.info(f"✅ MT5 initialization successful. Using symbol: {self.symbol}")
            return True
        except Exception as e:
            logger.error(f"MT5 initialization error: {e}")
            self.mt5_connected = False
            return False

    def start_background_model_loading(self):
        """Start loading the model in background for instant availability."""
        if not self.model_loading and not self.model_loaded:
            self.model_loading = True
            self.model_loader_thread = threading.Thread(target=self.background_model_loader, daemon=True)
            self.model_loader_thread.start()
            logger.info("Started background model loading...")

    def background_model_loader(self):
        """Background thread to load and cache the model."""
        try:
            logger.info("Background model loader started")

            # Try cache first
            if self.load_model_from_cache():
                self.warmup_model()
                logger.info("Model ready for instant use!")
                return

            # Download and cache
            logger.info("Downloading model in background...")
            self.initialize_finbert()
            self.warmup_model()
            logger.info("Model ready for instant use!")

        except Exception as e:
            logger.error(f"Background model loading failed: {e}")
        finally:
            self.model_loading = False

    def load_model_from_cache(self):
        """Try to load model from local cache for instant startup."""
        try:
            import os
            if os.path.exists(self.model_cache_path):
                logger.info("Loading FinBERT from cache...")
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_cache_path)
                self.model = AutoModelForSequenceClassification.from_pretrained(self.model_cache_path)
                self.model.eval()
                self.model_loaded = True
                logger.info("FinBERT loaded from cache successfully")
                return True
        except Exception as e:
            logger.warning(f"Cache loading failed: {e}")
        return False

    def cache_model_locally(self):
        """Cache the model locally for future fast loading."""
        try:
            import os
            if not os.path.exists(self.model_cache_path):
                logger.info("Caching FinBERT model locally...")
                # Download and save model
                tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
                model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
                tokenizer.save_pretrained(self.model_cache_path)
                model.save_pretrained(self.model_cache_path)
                logger.info("FinBERT cached successfully")
        except Exception as e:
            logger.warning(f"Model caching failed: {e}")

    def warmup_model(self):
        """Warm up the model with a test inference for instant readiness."""
        try:
            if self.model_loaded and self.model is not None:
                logger.info("Warming up FinBERT model...")
                test_text = "This is a test economic news headline for model warm-up."
                inputs = self.tokenizer(test_text, return_tensors="pt", truncation=True, max_length=128, padding=True)
                with torch.no_grad():
                    _ = self.model(**inputs)
                logger.info("Model warm-up completed - ready for instant analysis!")
        except Exception as e:
            logger.warning(f"Model warm-up failed: {e}")

    def initialize_finbert(self):
        try:
            # Check if already loaded by background loader
            if self.model_loaded and self.model is not None and self.tokenizer is not None:
                logger.info("FinBERT already loaded by background loader")
                return True

            # Try loading from cache first (instant)
            if self.load_model_from_cache():
                return True

            # Wait for background loader if it's still working
            if self.model_loading:
                logger.info("Waiting for background model loading to complete...")
                wait_time = 0
                while self.model_loading and wait_time < 30:  # Wait up to 30 seconds
                    time.sleep(1)
                    wait_time += 1

                if self.model_loaded:
                    logger.info("Background loading completed successfully")
                    return True

            # Fallback to fresh download
            logger.info("Downloading FinBERT model...")
            self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
            self.model.eval()
            self.model_loaded = True

            # Cache for future use
            self.cache_model_locally()

            # Warm up the model
            self.warmup_model()

            logger.info("FinBERT model loaded, cached, and warmed up successfully")
            return True
        except Exception as e:
            logger.error(f"FinBERT initialization error: {e}")
            return False

    def fetch_schedule(self, force_refresh=False):
        """Fetches the event schedule using multiple data sources for speed."""
        global EVENT_CACHE
        now = datetime.now(timezone.utc)
        
        # Prevent concurrent scrapes spawning multiple browser instances
        acquired = self.scrape_lock.acquire(blocking=False)
        if not acquired:
            logger.info("Scrape already in progress - using cached schedule")
            # Ensure we have events set from cache
            self.events = EVENT_CACHE["schedule"]
            return
        # Fix: Ensure last_fetched is timezone-aware
        if EVENT_CACHE["last_fetched"] and EVENT_CACHE["last_fetched"].tzinfo is None:
            EVENT_CACHE["last_fetched"] = EVENT_CACHE["last_fetched"].replace(tzinfo=timezone.utc)

        # Force refresh if it's a new day (date changed since last fetch)
        last_fetch_date = EVENT_CACHE["last_fetched"].date() if EVENT_CACHE["last_fetched"] else None
        today = now.date()
        is_new_day = last_fetch_date != today

        is_stale = force_refresh or not EVENT_CACHE["last_fetched"] or (now - EVENT_CACHE["last_fetched"]) > timedelta(hours=config.SCHEDULE_FETCH_INTERVAL_HOURS)

        if is_new_day:
            logger.info(f"📅 NEW DAY DETECTED: {today} (previous: {last_fetch_date}) - Forcing fresh data extraction")
            is_stale = True

        if is_stale:
            logger.info("Cache is stale or empty. Fetching new event schedule...")
            all_events = []

            # PRIORITY 1: Live scraping – Forex Factory (undetected Chrome, bypasses Cloudflare)
            logger.info("🔍 PRIORITY 1: Live scraping Forex Factory (real-time)...")
            try:
                scraped_events = self.scrape_events_selenium()
                if scraped_events:
                    all_events.extend(scraped_events)
                    logger.info(f"✅ SUCCESS: Added {len(scraped_events)} events from live Forex Factory scrape")
                else:
                    logger.warning("⚠️ Live Forex Factory scrape returned no events")
            except Exception as e:
                logger.error(f"❌ Live Forex Factory scraping failed: {e}")

            # Last-resort fallback: static Forex Factory JSON (not real-time)
            if not all_events:
                logger.info("Fallback: Forex Factory JSON (static weekly feed)...")

                ff_json_events = self.fetch_forex_factory_json()
                if ff_json_events:
                    all_events.extend(ff_json_events)
                    logger.info(f"✅ Added {len(ff_json_events)} events from Forex Factory JSON fallback")

            # Update cache with all collected events
            if all_events:
                # Remove duplicates and sort by time
                unique_events = []
                seen_headlines = set()
                for event in sorted(all_events, key=lambda x: x['time']):
                    headline = event.get('headline', event.get('name', ''))
                    if headline not in seen_headlines:
                        unique_events.append(event)
                        seen_headlines.add(headline)

                # Validate and filter for today's events only
                today_events = self.validate_today_events(unique_events)

                self.events = today_events
                EVENT_CACHE["schedule"] = self.events
                EVENT_CACHE["last_fetched"] = now

                # Summary of today's events
                today_utc = datetime.now(timezone.utc).date()
                logger.info(f"🎯 EXTRACTION COMPLETE: {len(self.events)} events for TODAY ({today_utc})")
                for event in self.events[:5]:  # Show first 5 events
                    logger.info(f"   📅 {event['time'].strftime('%H:%M')} - {event['name']} ({event['source']})")
                if len(self.events) > 5:
                    logger.info(f"   ... and {len(self.events) - 5} more events")
            else:
                logger.warning("No events fetched from any source")
        else:
            self.events = EVENT_CACHE["schedule"]
            logger.info(f"Loaded {len(self.events)} events from cache")
        try:
            self.scrape_lock.release()
        except Exception:
            pass

    def fetch_forex_factory_json(self):
        """Fetch calendar from Forex Factory's public JSON (no Cloudflare, no Selenium)."""
        try:
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            logger.info("Fetching Forex Factory calendar (public JSON)...")
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Forex Factory JSON returned status {response.status_code}")
                return []
            data = response.json()
            if not isinstance(data, list):
                return []
            today_utc = datetime.now(timezone.utc).date()
            events = []
            for item in data:
                date_str = item.get("date") or item.get("eventTime")
                if not date_str:
                    continue
                try:
                    # e.g. "2026-02-02T10:00:00-05:00"
                    event_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if event_dt.tzinfo is None:
                        event_dt = event_dt.replace(tzinfo=timezone.utc)
                    else:
                        event_dt = event_dt.astimezone(timezone.utc)
                except Exception:
                    continue
                if event_dt.date() != today_utc:
                    continue

                country = (item.get("country") or "").strip().upper()
                if not country:
                    continue

                title = (item.get("title") or item.get("name") or "Event").strip()
                impact_value = (item.get("impact") or "").strip() or "Low"
                events.append({
                    "time": event_dt,
                    "name": title,
                    "source": "ForexFactoryJSON",
                    "headline": title,
                    "forecast": item.get("forecast", "") or "N/A",
                    "currency": country,
                    "impact": impact_value,
                })

            if events:
                logger.info(f"Forex Factory JSON: {len(events)} events for today across currencies")
            return events
        except Exception as e:
            logger.warning(f"Forex Factory JSON fetch failed: {e}")
            return []

    def fetch_news_api(self):
        """Fetch economic news using NewsAPI (much faster than scraping)."""
        try:
            if not config.USE_NEWS_API or not config.NEWS_API_KEY:
                return []

            logger.info("Fetching today's news from NewsAPI...")
            # Get today's date in UTC for consistent filtering
            today_utc = datetime.now(timezone.utc).date()
            from_date = today_utc.isoformat()
            to_date = today_utc.isoformat()

            logger.info(f"🗓️  NewsAPI filtering for TODAY: {today_utc}")
            logger.info(f"📅 Date range: {from_date} to {to_date}")

            url = f"https://newsapi.org/v2/everything?q=USD+economic+news+OR+forex+news+OR+federal+reserve&language=en&from={from_date}&to={to_date}&sortBy=publishedAt&apiKey={config.NEWS_API_KEY}"

            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                events = []

                logger.info(f"🔍 Filtering NewsAPI results for TODAY: {today_utc}")

                for article in data.get('articles', [])[:20]:  # Check more articles for today's news
                    published_at = article.get('publishedAt', '')
                    if published_at:
                        try:
                            # Parse the published time
                            event_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                            event_time = event_time.astimezone()

                            # Normalize to UTC for consistent processing
                            event_time_utc = self.normalize_event_time(event_time)

                            # Double-check: only include today's articles
                            if event_time_utc.date() == today_utc:
                                logger.info(f"✅ Found TODAY'S NewsAPI article ({today_utc}): {article.get('title', '')[:50]}... at {event_time_utc}")
                                events.append({
                                    'name': article.get('title', 'Economic News'),
                                    'time': event_time_utc,  # Store normalized UTC time
                                    'forecast': 'N/A',
                                    'headline': article.get('title', ''),
                                    'currency': 'USD',
                                    'source': 'NewsAPI'
                                })
                            else:
                                logger.debug(f"❌ Skipping non-today NewsAPI article from {event_time_utc.date()}: {article.get('title', '')[:30]}...")
                        except Exception as e:
                            logger.debug(f"Failed to parse NewsAPI time: {e}")
                            continue

                logger.info(f"Fetched {len(events)} articles from NewsAPI")
                return events
            else:
                logger.warning(f"NewsAPI request failed: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"NewsAPI fetch error: {e}")
            return []

    def fetch_alpha_vantage(self):
        """Fetch economic indicators from Alpha Vantage API."""
        try:
            if not config.USE_ALPHA_VANTAGE or not config.ALPHA_VANTAGE_KEY:
                return []

            logger.info("Fetching economic data from Alpha Vantage...")
            # Example: Fetch CPI data
            url = f"https://www.alphavantage.co/query?function=CPI&interval=monthly&apikey={config.ALPHA_VANTAGE_KEY}"

            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                events = []

                # Parse economic data and create events
                # This is a simplified example - you'd parse actual economic releases
                logger.info("Alpha Vantage data fetched (simplified)")
                return events
            else:
                logger.warning(f"Alpha Vantage request failed: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Alpha Vantage fetch error: {e}")
            return []

    def fetch_ultimate_economic_calendar(self):
        """Fetch events from the Ultimate Economic Calendar API."""
        if not config.USE_ULTIMATE_ECONOMIC_CALENDAR:
            logger.info("Ultimate Economic Calendar API is disabled in config.")
            return []

        logger.info("Fetching events from Ultimate Economic Calendar API...")
        try:
            import http.client
            import json
            from datetime import datetime, timezone

            conn = http.client.HTTPSConnection(config.ULTIMATE_ECONOMIC_CALENDAR_API_HOST)
            headers = {
                'x-rapidapi-key': config.ULTIMATE_ECONOMIC_CALENDAR_API_KEY,
                'x-rapidapi-host': config.ULTIMATE_ECONOMIC_CALENDAR_API_HOST
            }

            # Fetch events for today
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            endpoint = f"/economic-events/tradingview?from={today}&to={today}&countries=US,JP,GB,EU"
            
            conn.request("GET", endpoint, headers=headers)
            res = conn.getresponse()
            data = res.read()
            
            if res.status != 200:
                logger.error(f"Ultimate Economic Calendar API request failed with status {res.status}: {data.decode('utf-8')}")
                return []

            api_response = json.loads(data.decode("utf-8"))
            
            # The actual events are inside the 'data' key of the response
            api_events = api_response.get('data', [])
            if not api_events:
                logger.warning("Ultimate Economic Calendar API returned no events for today.")
                return []

            formatted_events = []
            for event in api_events:
                event_time_str = event.get('eventTime')
                if not event_time_str:
                    continue

                # The timestamp is in ISO 8601 format (e.g., "2024-07-26T12:30:00Z")
                event_time = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))

                formatted_events.append({
                    'time': event_time,
                    'name': event.get('title', 'Unnamed Event'),
                    'source': 'UltimateEconomicCalendar',
                    'impact': event.get('impact', 'Low'),
                    'headline': event.get('title', 'Unnamed Event')
                })
            
            logger.info(f"✅ SUCCESS: Added {len(formatted_events)} events from Ultimate Economic Calendar")
            return formatted_events

        except Exception as e:
            logger.error(f"Error fetching from Ultimate Economic Calendar API: {e}")
            return []

    def scrape_events_selenium(self):
        """Selenium-based scraper to extract today's high-impact USD events (fallback method)."""
        logger.info("Scraping Forex Factory using Selenium (fallback)...")
        driver = None
        try:
            driver = self.setup_selenium_browser()
            if not driver:
                raise RuntimeError("Failed to initialize Selenium browser.")

            # Forex Factory supports ?day=today (preferred) or ?date=YYYY-MM-DD
            today = datetime.now().date()
            today_str = today.strftime("%B %d, %Y")
            logger.info(f"📅 Navigating to TODAY'S date: {today_str}")

            # Load calendar for today - try native "today" URL first (most reliable)
            driver.get("https://www.forexfactory.com/calendar?day=today")
            time.sleep(3)

            # Wait for calendar content to load (JS-rendered; rows may use calendar__row or table)
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='calendar']"))
                )
            except Exception:
                pass  # proceed and try multiple row selectors below

            navigation_success = True  # day=today URL targets today
            if navigation_success:
                logger.info("🎯 Successfully navigated to today's calendar date")
            else:
                logger.warning("⚠️ Could not navigate to today's date, proceeding with current view")
                logger.warning("This may include events from multiple days - results may be inaccurate")

            # Verify we're on the correct date
            try:
                # Try to find the current date display on the page
                current_date_display = driver.find_element(By.XPATH, "//h1 | //div[contains(@class, 'date')] | //span[contains(@class, 'date')]").text
                logger.info(f"📅 Page currently showing date: {current_date_display}")
            except:
                logger.debug("Could not find date display on page")

            # Additional wait for dynamic content (JS-rendered rows)
            time.sleep(3)

            # Try multiple selectors - Forex Factory may use calendar__row or other classes
            rows = driver.find_elements(By.CLASS_NAME, "calendar__row")
            if not rows:
                rows = driver.find_elements(By.CSS_SELECTOR, "[class*='calendar'][class*='row']")
            if not rows:
                rows = driver.find_elements(By.CSS_SELECTOR, "tr.calendar_row")
            if not rows:
                # Fallback: table rows inside calendar table that have multiple cells
                try:
                    table = driver.find_element(By.CSS_SELECTOR, "table.calendar__table, table[class*='calendar']")
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    # Filter to rows that look like event rows (have time/currency-like content)
                    rows = [r for r in rows if len(r.find_elements(By.TAG_NAME, "td")) >= 4]
                except Exception:
                    pass
            logger.info(f"Found {len(rows)} calendar rows on the current page")
            events = []

            # Get today's date - use UTC for consistency across all operations
            today_utc = datetime.now(timezone.utc).date()
            logger.info(f"🔍 EXTRACTING EVENTS FOR TODAY: {today_utc} (UTC)")
            logger.info(f"Current UTC time: {datetime.now(timezone.utc)}")
            logger.info(f"Current local time: {datetime.now()}")

            # Double-check: Warn if we might not be on today's date
            if not navigation_success:
                logger.warning("⚠️ WARNING: Could not verify we're viewing today's calendar!")
                logger.warning("⚠️ The extracted events may NOT be from today - results may be inaccurate")
                logger.info("🔧 FALLBACK: Will still attempt to filter events by date during processing")

            # DEBUG: Log all events found for troubleshooting
            logger.info("=== DEBUG: All events found on Forex Factory ===")
            all_events_found = []
            for i, row in enumerate(rows[:20]):  # Check first 20 rows
                try:
                    currency = row.find_element(By.CLASS_NAME, "calendar__currency").text.strip()
                    time_str = row.find_element(By.CLASS_NAME, "calendar__time").text.strip()
                    event_name = row.find_element(By.CLASS_NAME, "calendar__event").text.strip()
                    impact_element = row.find_element(By.CLASS_NAME, "calendar__impact")
                    impact_title = impact_element.find_element(By.TAG_NAME, "span").get_attribute("title")

                    all_events_found.append(f"{currency} | {time_str} | {event_name} | {impact_title}")
                    if i < 10:  # Log first 10 in detail
                        logger.info(f"DEBUG Event {i}: {currency} | {time_str} | {event_name} | Impact: {impact_title}")
                except Exception as e:
                    logger.debug(f"DEBUG: Could not parse row {i}: {e}")

            logger.info(f"DEBUG: Total events parsed: {len(all_events_found)}")
            logger.info("=== END DEBUG ===")

            last_time_str = None

            for i, row in enumerate(rows):
                ### FIX: Safer scraping logic to prevent 'NoneType' errors ###
                try:
                    impact_element = row.find_element(By.CLASS_NAME, "calendar__impact")
                    impact_title = impact_element.find_element(By.TAG_NAME, "span").get_attribute("title")

                    try:
                        current_time_str = row.find_element(By.CLASS_NAME, "calendar__time").text.strip()
                        if current_time_str:
                            last_time_str = current_time_str
                    except Exception as e:
                        logger.debug(f"Row {i}: Could not read time cell - {e}")

                    # Debug: Log all events found (first 10)
                    if i < 10:
                        try:
                            currency = row.find_element(By.CLASS_NAME, "calendar__currency").text.strip()
                            time_str = row.find_element(By.CLASS_NAME, "calendar__time").text.strip()
                            event_name = row.find_element(By.CLASS_NAME, "calendar__event").text.strip()
                            logger.debug(f"Row {i}: {currency} | {time_str} | {event_name} | Impact: {impact_title}")
                        except Exception as debug_e:
                            logger.debug(f"Row {i}: Could not extract details - {debug_e}")

                    impact_title_lower = impact_title.lower()
                    is_high_impact = ("high" in impact_title_lower and "impact" in impact_title_lower)
                    is_medium_impact = ("medium" in impact_title_lower and "impact" in impact_title_lower)

                    if is_high_impact or is_medium_impact:
                        impact_label = "High" if is_high_impact else "Medium"
                        logger.debug(f"Found {impact_label.lower()} impact event with title: '{impact_title}'")
                        currency = row.find_element(By.CLASS_NAME, "calendar__currency").text.strip()
                        if not currency:
                            continue
                        time_str = row.find_element(By.CLASS_NAME, "calendar__time").text.strip()
                        if not time_str and last_time_str:
                            logger.debug(f"Row {i}: Empty time field detected, reusing last time '{last_time_str}'")
                            time_str = last_time_str
                        event_name = row.find_element(By.CLASS_NAME, "calendar__event").text.strip()
                        forecast = row.find_element(By.CLASS_NAME, "calendar__forecast").text.strip()
                        actual = row.find_element(By.CLASS_NAME, "calendar__actual").text.strip()
                        previous = row.find_element(By.CLASS_NAME, "calendar__previous").text.strip()

                        if time_str:
                            try:
                                # Try multiple time formats (12-hour with AM/PM, 24-hour, etc.)
                                event_time = None
                                time_formats = ["%I:%M%p", "%H:%M", "%I:%M %p", "%H:%M:%S"]

                                for fmt in time_formats:
                                    try:
                                        event_time = datetime.strptime(time_str.strip(), fmt).time()
                                        logger.debug(f"Successfully parsed time '{time_str}' with format '{fmt}'")
                                        break
                                    except ValueError:
                                        continue

                                if event_time is None:
                                    logger.warning(f"Could not parse time '{time_str}' for event '{event_name}' with any known format")
                                    continue

                                # Remember this time for subsequent rows with blank time fields
                                last_time_str = time_str

                                # Create event datetime - assume it's in local timezone of the website
                                today_local = datetime.now().date()
                                event_datetime = datetime.combine(today_local, event_time)

                                # Normalize to UTC for consistent processing
                                event_datetime_utc = self.normalize_event_time(event_datetime)

                                # Only include today's events (UTC date comparison)
                                if event_datetime_utc.date() == today_utc:
                                    logger.info(f"✅ EXTRACTED TODAY'S EVENT ({today_utc}): '{event_name}' at {time_str}")
                                    logger.info(f"   Event UTC time: {event_datetime_utc}")
                                    events.append({
                                        'name': event_name,
                                        'time': event_datetime_utc,  # Store normalized UTC time
                                        'forecast': forecast,
                                        'actual': actual,
                                        'previous': previous,
                                        'headline': event_name,
                                        'currency': currency,
                                        'impact': impact_label,
                                        'source': 'ForexFactory'
                                    })
                                else:
                                    logger.debug(f"❌ Skipping non-today event: '{event_name}' on {event_datetime_utc.date()} (today is {today_utc})")
                            except Exception as e:
                                logger.warning(f"Failed to process event '{event_name}' with time '{time_str}': {e}")
                                continue
                except Exception as e:
                    logger.debug(f"Skipping row due to error: {e}")
                    continue # Skip rows that are not standard event rows

            logger.info(f"Successfully extracted {len(events)} high-impact events")

            # Final verification: Check that all extracted events are actually from today
            if events:
                today_events_count = sum(1 for event in events if event['time'].date() == today_utc)
                other_dates = set(event['time'].date() for event in events if event['time'].date() != today_utc)

                logger.info(f"📊 FINAL VERIFICATION: {today_events_count}/{len(events)} events are from today ({today_utc})")

                if other_dates:
                    logger.error(f"🚨 ERROR: Found events from wrong dates: {sorted(other_dates)}")
                    logger.error("🚨 This indicates the calendar navigation failed!")
                    for event in events:
                        if event['time'].date() != today_utc:
                            logger.error(f"   Wrong date event: '{event['name']}' on {event['time'].date()}")
                else:
                    logger.info("✅ All extracted events are correctly from today's date")

            return sorted(events, key=lambda x: x['time'])
        finally:
            if driver:
                driver.quit()

    def setup_selenium_browser(self):
        """Initializes undetected Chrome for live scraping (bypasses Cloudflare)."""
        try:
            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-images")
            
            # AWS Headless Mode Support
            if config.HEADLESS_MODE:
                logger.info("Running in HEADLESS mode (AWS)")
                options.add_argument("--headless=new")
                
            # JavaScript must stay enabled - calendar loads via JS

            logger.info("Setting up undetected Chrome for live Forex Factory scraping...")
            # Explicitly use Chrome version 144 to match installed Chrome
            browser = uc.Chrome(options=options, use_subprocess=True, version_main=144)

            # Random mouse movements (only possible in GUI mode, skip if headless)
            if not config.HEADLESS_MODE:
                time_module.sleep(random.uniform(1, 2))
                try:
                    action = ActionChains(browser)
                    action.move_by_offset(random.randint(50, 200), random.randint(50, 200)).perform()
                    time_module.sleep(random.uniform(0.3, 0.8))
                except Exception:
                    pass # Ignore mouse move errors

            logger.info("Browser initialized (undetected Chrome) for real-time scraping")
            return browser
        except Exception as e:
            logger.error(f"Browser setup error: {e}")
            return None

    def analyze_event(self, event):
        """Analyze event headline using FinBERT and return sentiment score."""
        start_time = time.time()
        try:
            if not self.model or not self.tokenizer:
                logger.error("FinBERT model not initialized")
                return 0.0

            headline = event.get('headline', event.get('name', ''))
            if not headline:
                logger.warning("No headline to analyze")
                return 0.0

            # Tokenize and predict (optimized for speed)
            inputs = self.tokenizer(headline, return_tensors="pt", truncation=True, max_length=128, padding=True)
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.softmax(outputs.logits, dim=1)

            # FinBERT labels (ProsusAI/finbert): 0=positive, 1=negative, 2=neutral
            positive_score = predictions[0][0].item()
            negative_score = predictions[0][1].item()
            neutral_score = predictions[0][2].item()

            # Calculate net sentiment score (positive - negative)
            # Weighted sentiment: Give slightly more weight to strong signals
            # If neutral is dominant (>0.8), force score to 0 to avoid noise
            if neutral_score > 0.8:
                sentiment_score = 0.0
            else:
                sentiment_score = positive_score - negative_score

            if sentiment_score == 0.0 and event.get('forecast') and event.get('previous'):
                try:
                    def parse_value(val_str):
                        clean_str = re.sub(r'[^\d.-]', '', val_str)
                        if not clean_str: return None
                        val = float(clean_str)
                        if 'K' in val_str: val *= 1000
                        elif 'M' in val_str: val *= 1000000
                        elif 'B' in val_str: val *= 1000000000
                        elif '%' in val_str: val /= 100
                        return val

                    forecast_val = parse_value(event['forecast'])
                    previous_val = parse_value(event['previous'])

                    if forecast_val is not None and previous_val is not None:
                        is_inverse = any(x in headline.lower() for x in ['unemployment', 'jobless', 'claimant'])
                        
                        if forecast_val > previous_val:
                            sentiment_score = -0.5 if is_inverse else 0.5
                            logger.info(f"Derived Fundamental Sentiment from Data: Forecast ({forecast_val}) > Previous ({previous_val}) => Score {sentiment_score}")
                        elif forecast_val < previous_val:
                            sentiment_score = 0.5 if is_inverse else -0.5
                            logger.info(f"Derived Fundamental Sentiment from Data: Forecast ({forecast_val}) < Previous ({previous_val}) => Score {sentiment_score}")
                except Exception as e:
                    logger.warning(f"Failed to derive fundamental sentiment: {e}")

            # Performance tracking
            analysis_time = time.time() - start_time
            self.total_analysis_count += 1
            self.avg_analysis_time = (self.avg_analysis_time * (self.total_analysis_count - 1) + analysis_time) / self.total_analysis_count

            logger.info(f"Analyzed '{headline}' in {analysis_time:.3f}s: Score={sentiment_score:.3f} (Avg: {self.avg_analysis_time:.3f}s)")
            return sentiment_score

        except Exception as e:
            logger.error(f"Error analyzing event: {e}")
            return 0.0

    def check_trade_conditions(self, event, sentiment_score):
        """Check if all conditions are met for placing a trade."""
        try:
            # --- 1. IMPACT FILTERING ---
            impact = event.get('impact', 'Low').lower()
            if 'high' not in impact:
                logger.info(f"Skipping '{event['name']}' due to low impact: {impact}")
                return False, None

            # --- 2. SENTIMENT THRESHOLD ---
            if abs(sentiment_score) < config.TRADE_THRESHOLD:
                logger.info(f"Sentiment score {sentiment_score:.3f} below threshold {config.TRADE_THRESHOLD}")
                return False, None

            now = datetime.now(timezone.utc)
            event_time = event['time']

            if now.date() != event_time.date():
                return False, None

            # --- 4. DYNAMIC SYMBOL SELECTION ---
            event_currency = event.get('currency', 'USD')
            currency_to_symbol = {
                'USD': 'XAUUSD', # Trade Gold for US news
                'EUR': 'EURUSD',
                'GBP': 'GBPUSD',
                'AUD': 'AUDUSD',
                'NZD': 'NZDUSD',
                'CAD': 'USDCAD',
                'CHF': 'USDCHF',
                'JPY': 'USDJPY'
            }
            
            target_base = currency_to_symbol.get(event_currency, config.DEFAULT_SYMBOL)
            symbol_variations = [target_base, f"{target_base}.", f"{target_base}+", f"{target_base}.pro", f"{target_base}m"]
            
            found_symbol = False
            for sym in symbol_variations:
                if mt5.symbol_select(sym, True):
                    symbol_info_check = mt5.symbol_info(sym)
                    if symbol_info_check:
                        self.symbol = sym
                        self.point = symbol_info_check.point
                        found_symbol = True
                        logger.info(f"Selected symbol {self.symbol} for {event_currency} news")
                        break
            
            if not found_symbol:
                logger.warning(f"Could not find valid symbol for {event_currency}, using fallback {self.symbol}")

            # --- 5. SYMBOL-SPECIFIC PARAMS ---
            # Get config for the selected symbol or default
            symbol_cfg = config.SYMBOL_CONFIG.get(self.symbol, config.SYMBOL_CONFIG.get("XAUUSD" if "XAU" in self.symbol else "DEFAULT"))
            sl_pips = symbol_cfg["STOP_LOSS_PIPS"]
            tp_pips = symbol_cfg["TAKE_PROFIT_PIPS"]

            pip_size = 10 * self.point
            
            if sentiment_score > 0:
                direction = "BUY"
                price_offset = config.OFFSET_PIPS * pip_size
            else:
                direction = "SELL"
                price_offset = -config.OFFSET_PIPS * pip_size

            # Get current market price
            symbol_info = mt5.symbol_info_tick(self.symbol)
            if not symbol_info:
                logger.error(f"Failed to get current price for {self.symbol}")
                return False, None

            # Validate offset against Stops Level & Spread
            symbol_details = mt5.symbol_info(self.symbol)
            if symbol_details:
                # Stops Level: Minimum distance from current price
                stops_level_points = symbol_details.trade_stops_level
                
                # Also must be outside spread usually for pending orders
                spread_points = symbol_details.spread
                
                # Check if spread exceeds maximum allowable threshold
                # 1 Standard Pip = 10 Points (usually)
                spread_pips = spread_points / 10.0 if symbol_details.digits == 3 or symbol_details.digits == 5 else spread_points
                if spread_pips > config.MAX_SPREAD_PIPS:
                    logger.warning(f"Spread {spread_pips:.1f} pips exceeds maximum {config.MAX_SPREAD_PIPS:.1f} pips. Refusing trade.")
                    return False, None
                
                # Calculate minimum safe distance in points
                # Some brokers require stops_level, others just outside spread.
                # We take the maximum of stops_level and spread to be safe, plus 2 pips.
                safe_dist_points = max(stops_level_points, spread_points) + 20 
                safe_dist_price = safe_dist_points * self.point

                current_offset_price = abs(price_offset)
                
                if current_offset_price < safe_dist_price:
                    logger.warning(f"Offset {current_offset_price:.5f} too small (Req={safe_dist_price:.5f}). Adjusting.")
                    price_offset = safe_dist_price if direction == "BUY" else -safe_dist_price

            entry_price = symbol_info.ask if direction == "BUY" else symbol_info.bid
            entry_price += price_offset

            # Calculate stop loss and take profit using specific pips
            if direction == "BUY":
                stop_loss = entry_price - (sl_pips * pip_size)
                take_profit = entry_price + (tp_pips * pip_size)
            else:
                stop_loss = entry_price + (sl_pips * pip_size)
                take_profit = entry_price - (tp_pips * pip_size)

            trade_params = {
                'direction': direction,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'symbol': self.symbol,
                'volume': 0.1  # Adjusted lot size for demo
            }

            logger.info(f"Trade conditions met for '{event['name']}': {direction} at {entry_price:.3f}, SL={stop_loss:.3f}, TP={take_profit:.3f}")
            return True, trade_params

        except Exception as e:
            logger.error(f"Error checking trade conditions: {e}")
            return False, None

    def normalize_price(self, symbol, price):
        """Normalize price to the correct number of decimal places for the symbol."""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return price
        return round(price, symbol_info.digits)

    def get_filling_mode(self, symbol):
        """Determine correct filling mode for the symbol."""
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return mt5.ORDER_FILLING_RETURN
        
        filling = symbol_info.filling_mode
        # 1: FOK, 2: IOC
        if filling & 2: # SYMBOL_FILLING_IOC
            return mt5.ORDER_FILLING_IOC
        elif filling & 1: # SYMBOL_FILLING_FOK
            return mt5.ORDER_FILLING_FOK
        else:
            return mt5.ORDER_FILLING_RETURN

    def place_trade(self, trade_params):
        """Place a trade via MT5 with Market Order fallback."""
        try:
            # Normalize prices
            price = self.normalize_price(trade_params['symbol'], trade_params['entry_price'])
            sl = self.normalize_price(trade_params['symbol'], trade_params['stop_loss'])
            tp = self.normalize_price(trade_params['symbol'], trade_params['take_profit'])

            filling_mode = self.get_filling_mode(trade_params['symbol'])
            
            # --- ATTEMPT 1: Pending Order (Limit/Stop) ---
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": trade_params['symbol'],
                "volume": trade_params['volume'],
                "type": mt5.ORDER_TYPE_BUY_STOP if trade_params['direction'] == "BUY" else mt5.ORDER_TYPE_SELL_STOP,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 123456,
                "comment": "News Bot Pending",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }

            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✅ Successfully placed PENDING {trade_params['direction']} order at {price:.3f}")
                return True
            
            # --- FAILURE ANALYSIS ---
            logger.warning(f"Pending order failed: {result.comment} (retcode: {result.retcode})")
            
            # If failure is due to price/stops (10015, 10016) or generic error, TRY MARKET ORDER
            # Retcodes: 10015=Invalid Price, 10016=Invalid Stops, 10029=Order Locked, 10009=Done
            if result.retcode in [10015, 10016, 10029, 10006]:
                logger.warning("⚠️ Pending order rejected. Attempting MARKET EXECUTION immediately...")
                
                # Get fresh price
                tick = mt5.symbol_info_tick(trade_params['symbol'])
                if not tick:
                    logger.error("Failed to get tick for market fallback")
                    return False
                
                market_price = tick.ask if trade_params['direction'] == "BUY" else tick.bid
                
                # Recalculate SL/TP relative to market price
                pip_size = 10 * self.point
                if trade_params['direction'] == "BUY":
                    new_sl = market_price - (config.STOP_LOSS_PIPS * pip_size)
                    new_tp = market_price + (config.TAKE_PROFIT_PIPS * pip_size)
                    order_type = mt5.ORDER_TYPE_BUY
                else:
                    new_sl = market_price + (config.STOP_LOSS_PIPS * pip_size)
                    new_tp = market_price - (config.TAKE_PROFIT_PIPS * pip_size)
                    order_type = mt5.ORDER_TYPE_SELL
                
                # Normalize again
                new_sl = self.normalize_price(trade_params['symbol'], new_sl)
                new_tp = self.normalize_price(trade_params['symbol'], new_tp)
                
                request_market = {
                    "action": mt5.TRADE_ACTION_DEAL, # Market Execution
                    "symbol": trade_params['symbol'],
                    "volume": trade_params['volume'],
                    "type": order_type,
                    "price": market_price,
                    "sl": new_sl,
                    "tp": new_tp,
                    "deviation": 20,
                    "magic": 123456,
                    "comment": "News Bot Market Fallback",
                    "type_filling": filling_mode,
                }
                
                result_market = mt5.order_send(request_market)
                
                if result_market.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"✅ MARKET FALLBACK SUCCESS: Executed {trade_params['direction']} at {market_price:.3f}")
                    return True
                else:
                    logger.error(f"❌ Market fallback also failed: {result_market.comment} (retcode: {result_market.retcode})")
                    return False

            return False

        except Exception as e:
            logger.error(f"Error placing trade: {e}")
            return False

    def parse_numeric_value(self, value_str):
        """Parse numeric value from string (handles percentages, K, M, T, etc.)"""
        if not value_str or value_str == 'N/A' or value_str == '':
            return None
        
        try:
            # Remove common suffixes and convert
            value_str = str(value_str).strip()
            value_str = value_str.replace('%', '').replace(',', '')
            
            # Handle multipliers
            multiplier = 1
            if 'T' in value_str.upper():
                multiplier = 1000000000000
                value_str = value_str.upper().replace('T', '')
            elif 'B' in value_str.upper():
                multiplier = 1000000000
                value_str = value_str.upper().replace('B', '')
            elif 'M' in value_str.upper():
                multiplier = 1000000
                value_str = value_str.upper().replace('M', '')
            elif 'K' in value_str.upper():
                multiplier = 1000
                value_str = value_str.upper().replace('K', '')
            
            return float(value_str) * multiplier
        except:
            return None

    def compare_forecast_vs_actual(self, event):
        """Compare forecast vs actual result and determine trading signal."""
        forecast_str = event.get('forecast', '')
        actual_str = event.get('actual', '')  # New field in JSON
        
        if not actual_str or actual_str == '' or actual_str == 'N/A':
            logger.info(f"No actual result yet for '{event['name']}' - waiting for release")
            return None, None
        
        forecast_val = self.parse_numeric_value(forecast_str)
        actual_val = self.parse_numeric_value(actual_str)
        
        if forecast_val is None or actual_val is None:
            logger.warning(f"Could not parse forecast/actual for '{event['name']}'")
            return None, None
        
        # Calculate difference
        difference = actual_val - forecast_val
        percent_diff = (difference / abs(forecast_val)) * 100 if forecast_val != 0 else 0
        
        logger.info(f"📊 {event['name']}: Forecast={forecast_val}, Actual={actual_val}, Diff={difference:.2f} ({percent_diff:.1f}%)")
        
        # Determine signal based on difference
        # For most economic indicators: Better than expected = Positive, Worse = Negative
        if abs(percent_diff) < 0.5:  # Very close to forecast
            return None, "Neutral - result matches forecast"
        elif difference > 0:  # Actual better than forecast
            return "BUY", f"Positive - actual {percent_diff:.1f}% better than forecast"
        else:  # Actual worse than forecast
            return "SELL", f"Negative - actual {abs(percent_diff):.1f}% worse than forecast"

    def check_mt5_connection(self):
        """Check if MT5 is connected and reconnect if needed."""
        try:
            # Check connection status (avoid checking too frequently)
            now = time.time()
            if now - self.mt5_last_check < 5:  # Only check every 5 seconds
                return self.mt5_connected
            
            self.mt5_last_check = now
            
            # Try to get account info - this is the most reliable connection check
            account_info = mt5.account_info()
            if account_info is None:
                # Connection lost, try to reconnect
                logger.warning("MT5 connection lost. Attempting to reconnect...")
                self.mt5_connected = False
                if self.initialize_mt5():
                    logger.info("✅ MT5 reconnection successful")
                    self.mt5_connected = True
                else:
                    logger.error("❌ MT5 reconnection failed")
                    self.mt5_connected = False
            else:
                self.mt5_connected = True
            
            return self.mt5_connected
        except Exception as e:
            logger.error(f"Error checking MT5 connection: {e}")
            self.mt5_connected = False
            return False

    def execute_trade_logic(self):
        """Check upcoming events and execute trades if conditions are met."""
        try:
            # Use improved connection check
            if not self.check_mt5_connection():
                logger.warning("MT5 not connected, skipping trade logic")
                return

            now = datetime.now(timezone.utc)

            for event in self.events:
                event_time = event['time']
                
                # Safety check: Ensure event_time is timezone-aware
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)
                    event['time'] = event_time # Update event in place
                
                time_diff_seconds = (event_time - now).total_seconds()
                time_diff = time_diff_seconds / 60.0

                # Strategy 1: Trade BEFORE news for any upcoming event based on sentiment
                if time_diff >= 0:
                    # Check if we already processed this event
                    if event.get('processed', False):
                        continue

                    if time_diff > config.PRE_NEWS_WINDOW_MINUTES:
                        continue

                    logger.info(f"⏰ Event '{event['name']}' is {time_diff:.1f} minutes away - analyzing sentiment")

                    if 'cached_sentiment' in event:
                        sentiment_score = event['cached_sentiment']
                    else:
                        sentiment_score = self.analyze_event(event)
                        event['cached_sentiment'] = sentiment_score

                    if time_diff_seconds > config.EXECUTION_TOLERANCE_SECONDS:
                        logger.info(
                            f"Pre-news analysis ready for '{event['name']}' "
                            f"(sentiment={sentiment_score:.3f}), waiting for release time"
                        )
                        continue

                    # Check trade conditions
                    can_trade, trade_params = self.check_trade_conditions(event, sentiment_score)

                    if can_trade and trade_params:
                        # Place the trade
                        success = self.place_trade(trade_params)

                        if success:
                            # Record the trade
                            trade_record = {
                                'time': datetime.now(),
                                'event': event['name'],
                                'signal': trade_params['direction'],
                                'symbol': self.symbol,
                                'entry_price': trade_params['entry_price'],
                                'stop_loss': trade_params['stop_loss'],
                                'take_profit': trade_params['take_profit'],
                                'status': 'Pending',
                                'strategy': 'Pre-News Sentiment'
                            }
                            self.trade_history.append(trade_record)

                            # Mark event as processed
                            event['processed'] = True

                            logger.info(f"✅ Trade executed for event '{event['name']}' based on sentiment")
                        else:
                            logger.error(f"❌ Failed to execute trade for event '{event['name']}'")
                    else:
                        logger.info(f"⏭️ No trade conditions met for event '{event['name']}'")

                # Strategy 2: Trade AFTER news (0-2 minutes after) based on actual results
                elif -2 <= time_diff < 0:
                    if event.get('post_news_processed', False) or event.get('processed', False):
                        continue
                    
                    impact = event.get('impact', 'Low').lower()
                    if 'high' not in impact:
                        logger.info(f"Skipping '{event['name']}' post-news due to impact: {impact}")
                        continue
                    
                    logger.info(f"📰 Event '{event['name']}' was released {abs(time_diff):.1f} minutes ago - checking actual results")
                    
                    # Compare forecast vs actual
                    direction, reason = self.compare_forecast_vs_actual(event)

                    if direction is None and reason is None:
                         actual_str = event.get('actual', '')
                         if not actual_str or actual_str == 'N/A':
                             logger.info(f"Force refreshing schedule to get actual result for '{event['name']}'")
                             self.fetch_schedule(force_refresh=True)
                             break # Break loop to restart with new events
                    
                    if direction:
                        # Get current market price
                        symbol_info = mt5.symbol_info_tick(self.symbol)
                        if not symbol_info:
                            logger.error(f"Failed to get current price for {self.symbol}")
                            continue
                        
                        # Determine entry price
                        pip_size = 10 * self.point
                        if direction == "BUY":
                            entry_price = symbol_info.ask
                            price_offset = config.OFFSET_PIPS * pip_size
                            stop_loss = entry_price - (config.STOP_LOSS_PIPS * pip_size)
                            take_profit = entry_price + (config.TAKE_PROFIT_PIPS * pip_size)
                        else:
                            entry_price = symbol_info.bid
                            price_offset = -config.OFFSET_PIPS * pip_size
                            stop_loss = entry_price + (config.STOP_LOSS_PIPS * pip_size)
                            take_profit = entry_price - (config.TAKE_PROFIT_PIPS * pip_size)
                        
                        entry_price += price_offset
                        
                        trade_params = {
                            'direction': direction,
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'symbol': self.symbol,
                            'volume': 0.1
                        }
                        
                        # Place the trade
                        success = self.place_trade(trade_params)
                        
                        if success:
                            trade_record = {
                                'time': datetime.now(),
                                'event': event['name'],
                                'signal': direction,
                                'symbol': self.symbol,
                                'entry_price': entry_price,
                                'stop_loss': stop_loss,
                                'take_profit': take_profit,
                                'status': 'Pending',
                                'strategy': 'Post-News Result',
                                'reason': reason
                            }
                            self.trade_history.append(trade_record)
                            event['post_news_processed'] = True
                            logger.info(f"✅ Trade executed for '{event['name']}' based on actual result: {reason}")
                        else:
                            logger.error(f"❌ Failed to execute post-news trade for '{event['name']}'")
                    else:
                        if reason:
                            logger.info(f"⏭️ {reason} for '{event['name']}' - no trade")
                        event['post_news_processed'] = True  # Mark as checked even if no trade

        except Exception as e:
            logger.error(f"Error in trade execution logic: {e}")

    def scrape_investing_com(self):
        """Scrape economic events from Investing.com as fallback."""
        driver = None
        try:
            driver = self.setup_selenium_browser()
            if not driver:
                return []

            driver.get("https://www.investing.com/economic-calendar/")
            WebDriverWait(driver, config.FALLBACK_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".economic-calendar"))
            )
            time_module.sleep(2)

            events = []
            today_utc = datetime.now(timezone.utc).date()

            # Find economic calendar events
            rows = driver.find_elements(By.CSS_SELECTOR, ".economic-calendar tr")

            for row in rows[:20]:  # Limit to first 20 events
                try:
                    time_element = row.find_elements(By.CSS_SELECTOR, ".time")
                    currency_element = row.find_elements(By.CSS_SELECTOR, ".currency")
                    event_element = row.find_elements(By.CSS_SELECTOR, ".event")

                    if time_element and currency_element and event_element:
                        time_str = time_element[0].text.strip()
                        currency = currency_element[0].text.strip()
                        event_name = event_element[0].text.strip()

                        if currency == "USD" and time_str:
                            try:
                                event_time = datetime.strptime(time_str, "%H:%M").time()
                                # Use local date because event_time is scraped in local time
                                event_datetime = datetime.combine(datetime.now().date(), event_time)
                                event_datetime_utc = self.normalize_event_time(event_datetime)

                                if event_datetime_utc.date() == today_utc:
                                    events.append({
                                        'name': event_name,
                                        'time': event_datetime_utc,
                                        'forecast': 'N/A',
                                        'headline': event_name,
                                        'currency': 'USD',
                                        'source': 'Investing.com'
                                    })
                            except ValueError:
                                continue
                except:
                    continue

            logger.info(f"Extracted {len(events)} events from Investing.com")
            return events

        except Exception as e:
            logger.error(f"Investing.com scraping error: {e}")
            return []
        finally:
            if driver:
                driver.quit()

    def scrape_bloomberg(self):
        """Scrape forex news from Bloomberg as fallback."""
        driver = None
        try:
            driver = self.setup_selenium_browser()
            if not driver:
                return []

            driver.get("https://www.bloomberg.com/markets")
            WebDriverWait(driver, config.FALLBACK_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article, .story, .headline"))
            )
            time_module.sleep(2)

            events = []
            today_utc = datetime.now(timezone.utc).date()

            # Find forex/markets news
            news_elements = driver.find_elements(By.CSS_SELECTOR, "article h3, .story h3, .headline")

            for element in news_elements[:10]:  # Limit to first 10 news items
                try:
                    title = element.text.strip()
                    if any(keyword in title.lower() for keyword in ['usd', 'dollar', 'fed', 'economy', 'forex']):
                        # Create event from news headline
                        event_datetime_utc = datetime.now(timezone.utc)

                        events.append({
                            'name': title,
                            'time': event_datetime_utc,
                            'forecast': 'N/A',
                            'headline': title,
                            'currency': 'USD',
                            'source': 'Bloomberg'
                        })
                except:
                    continue

            logger.info(f"Extracted {len(events)} forex news from Bloomberg")
            return events

        except Exception as e:
            logger.error(f"Bloomberg scraping error: {e}")
            return []
        finally:
            if driver:
                driver.quit()

    def scrape_reuters(self):
        """Scrape business news from Reuters as fallback."""
        driver = None
        try:
            driver = self.setup_selenium_browser()
            if not driver:
                return []

            driver.get("https://www.reuters.com/business/")
            WebDriverWait(driver, config.FALLBACK_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article, .story, h3"))
            )
            time_module.sleep(2)

            events = []
            today_utc = datetime.now(timezone.utc).date()

            # Find business/finance news
            news_elements = driver.find_elements(By.CSS_SELECTOR, "article h3, .story h3, h3")

            for element in news_elements[:10]:  # Limit to first 10 news items
                try:
                    title = element.text.strip()
                    if any(keyword in title.lower() for keyword in ['usd', 'dollar', 'fed', 'economy', 'business']):
                        # Create event from news headline
                        event_datetime_utc = datetime.now(timezone.utc)

                        events.append({
                            'name': title,
                            'time': event_datetime_utc,
                            'forecast': 'N/A',
                            'headline': title,
                            'currency': 'USD',
                            'source': 'Reuters'
                        })
                except:
                    continue

            logger.info(f"Extracted {len(events)} business news from Reuters")
            return events

        except Exception as e:
            logger.error(f"Reuters scraping error: {e}")
            return []
        finally:
            if driver:
                driver.quit()

    def startup_checks(self):
        """Perform critical startup checks."""
        logger.info("Performing startup checks...")
        
        # Check 1: MT5 Connection
        if not mt5.initialize():
            logger.error("MT5 initialization failed")
            return False

        # Check 2: Account Type Safety Lock
        account_info = mt5.account_info()
        if account_info:
            is_demo = (account_info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO)
            logger.info(f"Account Mode: {'DEMO' if is_demo else 'REAL'}")
            
            # --- SAFETY LOCK ---
            # If running simulation script, FORCE demo only
            import sys
            if 'test_bot_simulation.py' in sys.argv[0] and not is_demo:
                logger.critical("⛔ SAFETY STOP: Attempted to run SIMULATION on REAL ACCOUNT! Aborting.")
                print("⛔ SAFETY STOP: Attempted to run SIMULATION on REAL ACCOUNT! Aborting.")
                return False
        else:
            logger.error("Failed to get account info")
            return False

        # Check 3: Algo Trading Permission
        terminal_info = mt5.terminal_info()
        if not terminal_info:
            logger.error("Failed to get terminal info")
            return False
            
        if not terminal_info.trade_allowed:
            logger.critical("❌ ALGO TRADING IS DISABLED! Please click the 'Algo Trading' button in MT5 to enable it.")
            logger.critical("The bot cannot place trades until this is enabled.")
        else:
            logger.info("✅ Algo Trading is ENABLED")

        # Check 3: Symbol Validity
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            logger.error(f"Symbol {self.symbol} not found")
            return False
            
        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                logger.error(f"Failed to select symbol {self.symbol}")
                return False
        
        logger.info(f"✅ Symbol {self.symbol} is valid (Digits={symbol_info.digits}, Point={symbol_info.point})")
        return True

    def main_loop(self):
        """The main loop of the bot, runs in a background thread."""
        logger.info("Trading bot main loop started.")
        self.initialize()
        
        # Run startup checks
        self.startup_checks()
        
        while self.running:
            if self.paused:
                time.sleep(0.1)  # Fast pause check: 100ms
                continue
            
            # Periodic Algo Trading Check (every 10 seconds approx)
            if int(time.time()) % 10 == 0:
                term_info = mt5.terminal_info()
                if term_info and not term_info.trade_allowed:
                     logger.warning("⚠️ ALGO TRADING IS DISABLED - Please Enable it in MT5 Toolbar!")

            # Check for upcoming events and execute trades
            self.execute_trade_logic()

            # Update account stats (events are maintained by background scraper)
            self.update_account_stats()
            time.sleep(0.01)  # Ultra-fast: 10ms loop for sub-second execution
        
        mt5.shutdown()
        logger.info("Trading bot main loop stopped and MT5 connection shut down.")
        
    def start_scraper(self):
        """Start the background scraper thread."""
        if self.scraper_running:
            return
        self.scraper_running = True
        self.scraper_thread = threading.Thread(target=self.scraper_loop, daemon=True)
        self.scraper_thread.start()
        logger.info("Background scraper started.")

    def scraper_loop(self):
        """Background thread for continuous event scraping."""
        logger.info("Scraper loop started.")
        while self.scraper_running:
            try:
                self.fetch_schedule()
                time.sleep(60)  # Scrape every minute in background
            except Exception as e:
                logger.error(f"Scraper loop error: {e}")
                time.sleep(30)  # Retry after 30 seconds on error

    def start(self):
        if self.running:
            logger.warning("Bot is already running.")
            return
        self.running = True
        self.paused = False

        # Start background scraper first
        self.start_scraper()

        # Start main trading thread
        self.thread = threading.Thread(target=self.main_loop, daemon=True)
        self.thread.start()
        logger.info("Bot started in a background thread.")

    def stop(self):
        self.running = False
        logger.info("Bot stop signal sent.")
        if self.thread: self.thread.join(timeout=5)

    def pause(self):
        self.paused = True
        logger.info("Bot paused.")

    def resume(self):
        self.paused = False
        logger.info("Bot resumed.")
        
    def update_account_stats(self):
        if self.check_mt5_connection():
            info = mt5.account_info()
            if info:
                self.account_data = {
                    'equity': info.equity,
                    'balance': info.balance,
                    'profit': info.profit,
                    'performance': {
                        'avg_analysis_time': round(self.avg_analysis_time, 4),
                        'total_analyses': self.total_analysis_count,
                        'main_loop_freq': 100  # 100 Hz (10ms loops)
                    }
                }

# --- FLASK APP ---
app = Flask(__name__, static_folder='templates/static')
bot = LiveTradingBot()

@app.route('/')
def dashboard():
    logger.info("Dashboard accessed")
    return render_template('dashboard.html', config=config)

@app.route('/api/status')
def get_status():
    return jsonify({
        'running': bot.running,
        'paused': bot.paused,
        'mt5_connected': bot.mt5_connected,
        'account_data': bot.account_data,
        'trade_history': bot.trade_history[-10:]
    })

@app.route('/api/events')
def get_events():
    # Helper to serialize datetime objects
    events_safe = []
    # Filter out low-impact events for dashboard display
    filtered = []
    for event in bot.events:
        impact_val = str(event.get('impact', '')).lower()
        if ('high' in impact_val) or ('medium' in impact_val):
            filtered.append(event)
    for event in filtered:
        e_copy = event.copy()
        if isinstance(e_copy.get('time'), datetime):
            e_copy['time'] = e_copy['time'].isoformat()
        if isinstance(e_copy.get('date'), datetime):
            e_copy['date'] = e_copy['date'].isoformat()
        events_safe.append(e_copy)
    return jsonify({'events': events_safe})

@app.route('/api/control', methods=['POST'])
def control_bot():
    action = request.json.get('action')
    if action == 'start':
        if not bot.running:
            bot.start()
        else:
            bot.resume()
    elif action == 'stop':
        bot.stop()
    elif action == 'pause':
        bot.pause()
    elif action == 'resume':
        bot.resume()
    elif action == 'debug_6pm':
        # Debug: Search for 6:00 PM events
        six_pm_events = bot.debug_six_pm_events()
        
        # Serialize events
        events_safe = []
        for event in six_pm_events:
            e_copy = event.copy()
            if isinstance(e_copy.get('time'), datetime):
                e_copy['time'] = e_copy['time'].isoformat()
            if isinstance(e_copy.get('date'), datetime):
                e_copy['date'] = e_copy['date'].isoformat()
            events_safe.append(e_copy)

        return jsonify({
            'status': 'ok',
            'action': 'debug_6pm',
            'events_found': len(events_safe),
            'events': events_safe
        })
    return jsonify({'status': 'ok', 'action': action})

if __name__ == "__main__":
    logger.info("Initializing bot and dashboard...")
    
    ### FIX: Start the bot's main logic in a background thread ###
    # This allows the Flask app to run without being blocked.
    bot.start()
    
    # Open the browser to the dashboard after a short delay
    def open_browser():
        time.sleep(2)
        webbrowser.open('http://127.0.0.1:5000')
    
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.start()

    # Start the Flask web dashboard in the main thread
    # Threaded=True to handle multiple requests (e.g. AJAX calls from dashboard) without blocking
    # use_reloader=False to prevent starting the bot logic twice
    app.run(host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
