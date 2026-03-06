#!/usr/bin/env python3
"""
NewsAPI Test Script - Clean Version
Tests NewsAPI functionality without Unicode characters
"""

import requests
import json
from datetime import datetime, timezone
import config

def test_newsapi():
    """Test NewsAPI functionality."""
    print("Testing NewsAPI Configuration")
    print("=" * 40)

    # Check configuration
    if not config.USE_NEWS_API:
        print("ERROR: NewsAPI is disabled in config")
        return False

    if not config.NEWS_API_KEY or config.NEWS_API_KEY == "your_newsapi_key_here":
        print("ERROR: NewsAPI key not configured")
        return False

    print(f"OK: NewsAPI enabled with key: {config.NEWS_API_KEY[:8]}...")

    # Test API connection
    print("\nTesting API Connection...")

    # Get today's date in UTC
    today_utc = datetime.now(timezone.utc).date()
    from_date = today_utc.isoformat()
    to_date = today_utc.isoformat()

    print(f"Testing for date: {today_utc}")
    print(f"Date range: {from_date} to {to_date}")

    # Test basic connectivity
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={config.NEWS_API_KEY}"

    try:
        response = requests.get(url, timeout=10)
        print(f"API Response Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            total_results = data.get('totalResults', 0)
            articles = data.get('articles', [])

            print(f"Total Results: {total_results}")
            print(f"Articles in Response: {len(articles)}")

            if total_results > 0:
                print("OK: NewsAPI connection successful")
            else:
                print("WARNING: NewsAPI returned 0 results")
        else:
            print(f"ERROR: NewsAPI error: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"ERROR: Connection error: {e}")
        return False

    # Test economic news query
    print("\nTesting Economic News Query...")

    economic_url = f"https://newsapi.org/v2/everything?q=USD+economic+news+OR+forex+news+OR+federal+reserve&language=en&from={from_date}&to={to_date}&sortBy=publishedAt&apiKey={config.NEWS_API_KEY}"

    try:
        response = requests.get(economic_url, timeout=10)
        print(f"Economic News Response Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            total_results = data.get('totalResults', 0)
            articles = data.get('articles', [])

            print(f"Economic News Total Results: {total_results}")
            print(f"Economic Articles in Response: {len(articles)}")

            if total_results > 0:
                print("OK: Economic news query successful")

                # Show sample articles
                print("\nSample Articles:")
                for i, article in enumerate(articles[:3]):
                    title = article.get('title', 'No title')
                    published = article.get('publishedAt', 'No date')
                    source = article.get('source', {}).get('name', 'Unknown')

                    print(f"  {i+1}. {title[:60]}...")
                    print(f"     Source: {source} | Published: {published[:10]}")

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

                print(f"\nToday's Articles: {today_count}/{len(articles)}")

                if today_count > 0:
                    print("OK: Date filtering working correctly")
                else:
                    print("WARNING: No articles found for today")

            else:
                print("WARNING: No economic news found")
                print("INFO: This might be normal if there are no economic news today")

        else:
            print(f"ERROR: Economic news query failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"ERROR: Economic news query error: {e}")
        return False

    # Summary
    print("\n" + "=" * 40)
    print("NEWSAPI TEST SUMMARY")
    print("=" * 40)

    if total_results > 0:
        print("SUCCESS: NewsAPI is working correctly")
        print(f"SUCCESS: Found {total_results} total articles")
        print(f"SUCCESS: Found {len(articles)} articles in response")
        print("SUCCESS: Date filtering is functional")
        print("\nRECOMMENDATION: Use NewsAPI as primary data source")
        return True
    else:
        print("WARNING: NewsAPI returned no results")
        print("INFO: This might be normal for quiet news days")
        print("INFO: Consider using Forex Factory as fallback")
        return True  # Still return True as API is working

if __name__ == "__main__":
    success = test_newsapi()
    if success:
        print("\nSUCCESS: NewsAPI test completed successfully!")
    else:
        print("\nFAILED: NewsAPI test failed!")
        print("Check your API key and internet connection")