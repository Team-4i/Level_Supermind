from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import ScrapingTask, ScrapedPage, PageHeading, PageImage
from users.models import ART
from .forms import ScrapingTaskForm
from botasaurus import *
from botasaurus.request import request, Request
from botasaurus.soupify import soupify
from urllib.parse import urljoin, urlparse
import re
import google.generativeai as genai
from django.conf import settings
import json
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urlparse
from datetime import datetime
from googleapiclient.discovery import build
import random

# Initialize Gemini AI with your API key
genai.configure(api_key=settings.GEMINI_API_KEY)

def is_valid_url(url, base_domain):
    """Check if URL is valid and belongs to the same domain"""
    try:
        parsed = urlparse(url)
        return parsed.netloc == base_domain and bool(parsed.scheme)
    except:
        return False

def extract_text_content(element):
    """Extract clean text content from an element"""
    if not element:
        return ''
    
    # Get all text, excluding script and style content
    texts = []
    for text in element.stripped_strings:
        if text.parent.name not in ['script', 'style']:
            texts.append(text)
    
    return ' '.join(texts)

def extract_meta_tags(soup):
    """Extract all meta tags"""
    meta_tags = {}
    for meta in soup.find_all('meta'):
        name = meta.get('name', meta.get('property', ''))
        if name:
            meta_tags[name] = meta.get('content', '')
    return meta_tags

def extract_images(soup):
    """Extract all image information"""
    images = []
    for img in soup.find_all('img'):
        images.append({
            'src': img.get('src', ''),
            'alt': img.get('alt', ''),
            'title': img.get('title', '')
        })
    return images

def get_top_indian_brands(keywords):
    """Get top Indian brands based on category using Gemini AI"""
    try:
        print(f"\n🔍 Searching for top Indian brands in category: {keywords}")
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Generate a list of top 5 Indian brands in the {keywords} category.
        For each brand, provide their official website URL.
        
        Requirements:
        1. Only include genuine Indian brands/companies
        2. Ensure the brands are currently active and significant in the market
        3. Verify the URLs are official company websites
        4. Focus on brands with strong market presence in India
        5. Use only well-established websites with valid SSL certificates
        
        Format the response as a Python list of tuples, like this:
        [
            ("Brand Name 1", "https://website1.com"),
            ("Brand Name 2", "https://website2.com"),
            ...
        ]
        
        Only return the Python list, no other text.
        """

        print("📝 Generating brand list using Gemini AI...")
        response = model.generate_content(prompt)
        brands_list = eval(response.text.strip())
        print(f"✨ Generated {len(brands_list)} brands")
        
        # Validate the format and URLs
        validated_brands = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
        
        print("\n🌐 Validating brand URLs:")
        for brand_name, url in brands_list:
            print(f"\nChecking {brand_name} ({url})")
            try:
                # Validate URL format
                parsed = urlparse(url)
                if not (parsed.scheme and parsed.netloc):
                    print(f"❌ Invalid URL format for {brand_name}")
                    continue
                
                # Check if website is accessible
                response = requests.head(
                    url, 
                    headers=headers, 
                    timeout=10, 
                    allow_redirects=True,
                    verify=False  # Disable SSL verification
                )
                
                if response.status_code == 200:
                    validated_brands.append((brand_name, url))
                    print(f"✅ Successfully validated {brand_name}")
                else:
                    print(f"❌ Invalid response code ({response.status_code}) for {brand_name}")
                    
            except requests.exceptions.SSLError as e:
                print(f"⚠️ SSL Error for {brand_name}, attempting without verification...")
                try:
                    response = requests.head(
                        url, 
                        headers=headers, 
                        timeout=10, 
                        allow_redirects=True,
                        verify=False
                    )
                    if response.status_code == 200:
                        validated_brands.append((brand_name, url))
                        print(f"✅ Successfully validated {brand_name} (SSL verification disabled)")
                except Exception as e:
                    print(f"❌ Failed to validate {brand_name}: {str(e)}")
            except Exception as e:
                print(f"❌ Error validating {brand_name}: {str(e)}")
                continue
        
        print(f"\n✅ Successfully validated {len(validated_brands)} brands")
        
        # If no valid brands found, use a backup prompt
        if not validated_brands:
            print("\n⚠️ No valid brands found, trying backup prompt...")
            backup_prompt = f"""
            List 5 major Indian companies/brands in the {keywords} sector.
            Only include brands with reliable, working websites.
            Format: [("Brand", "Website")]
            Focus on major e-commerce platforms and well-established company websites.
            """
            
            backup_response = model.generate_content(backup_prompt)
            backup_brands = eval(backup_response.text.strip())
            
            print("\n🔄 Validating backup brands:")
            for brand_name, url in backup_brands:
                try:
                    response = requests.head(
                        url, 
                        headers=headers, 
                        timeout=10, 
                        allow_redirects=True,
                        verify=False
                    )
                    if response.status_code == 200:
                        validated_brands.append((brand_name, url))
                        print(f"✅ Successfully validated backup brand: {brand_name}")
                except Exception as e:
                    print(f"❌ Failed to validate backup brand {brand_name}: {str(e)}")
                    continue
        
        if validated_brands:
            print(f"\n🎉 Final list of {len(validated_brands)} validated brands:")
            for brand, url in validated_brands:
                print(f"- {brand}: {url}")
            return validated_brands
        
        print("\n⚠️ Using default fallback brand")
        return [("Default Brand", "https://example.com")]

    except Exception as e:
        print(f"\n❌ Error in get_top_indian_brands: {str(e)}")
        print("⚠️ Using default fallback brand")
        return [("Default Brand", "https://example.com")]

def get_search_urls(keywords):
    """Get URLs for top Indian brands in the category"""
    top_brands = get_top_indian_brands(keywords)
    
    # Additional URLs for each brand
    all_urls = []
    for brand_name, brand_url in top_brands:
        # Add main brand URL
        all_urls.append(brand_url)
        
        # Add review and analysis URLs
        search_terms = f"{brand_name} {keywords} india review"
        try:
            service = build(
                "customsearch", "v1",
                developerKey=settings.GOOGLE_API_KEY
            )
            
            result = service.cse().list(
                q=search_terms,
                cx=settings.GOOGLE_CSE_ID,
                num=3,  # Get top 3 results per brand
                dateRestrict='m6',
                gl="in",
                cr="countryIN"
            ).execute()
            
            for item in result.get('items', []):
                url = item.get('link')
                if url not in all_urls:
                    all_urls.append(url)
            
            time.sleep(1)  # Respect API limits
        except Exception as e:
            print(f"Error searching for {brand_name}: {str(e)}")
            continue
    
    # Validate URLs
    valid_urls = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for url in all_urls:
        try:
            response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                valid_urls.append(url)
        except Exception as e:
            print(f"Error validating {url}: {str(e)}")
            continue
    
    return valid_urls[:20]  # Limit to top 20 URLs

def generate_content_summary(task):
    """Generate a comprehensive summary focusing on Indian brands and marketing strategies"""
    try:
        model = genai.GenerativeModel('gemini-pro')
        
        # Get the top brands for this category
        top_brands = get_top_indian_brands(task.keywords)
        brand_names = [brand[0] for brand in top_brands]
        
        prompt = f"""
        Analyze and provide a comprehensive summary of these top Indian brands and their marketing strategies in the {task.keywords} category:

        Top Brands to analyze: {', '.join(brand_names)}

        1. Brand Overview & Market Position:
           - Market share and positioning of each brand
           - Target audience and demographic focus
           - Price segments and value proposition
           - Brand identity and personality

        2. Marketing Strategies:
           - Key marketing campaigns and themes
           - Celebrity endorsements and partnerships
           - Digital presence and social media strategy
           - Festival and seasonal marketing approaches
           - Regional marketing variations

        3. Consumer Psychology & Brand Perception:
           - Brand trust factors
           - Emotional connections with consumers
           - Cultural relevance and local connect
           - Consumer pain points addressed
           - Brand loyalty programs

        4. Distribution & Market Presence:
           - Online vs offline strategy
           - Geographic presence
           - Channel partnerships
           - Retail network strength
           - E-commerce integration

        5. Competitive Analysis:
           - Unique selling propositions
           - Price positioning
           - Product portfolio
           - Innovation focus
           - Market challenges and responses

        Format Requirements:
        - Use '🎯' for key marketing strategies
        - Use '💡' for innovative approaches
        - Use '🏆' for market leadership aspects
        - Use '📈' for growth initiatives
        - Use '₹' for pricing strategies
        - Use '🤝' for partnerships
        - Include specific campaign examples
        - Highlight successful marketing hooks

        Please provide a detailed analysis focusing on these specific Indian brands and their marketing approaches.
        """

        response = model.generate_content(prompt)
        
        formatted_response = f"""
        # Indian Brands & Marketing Analysis: {task.keywords}

        {response.text}

        ---
        *Analysis of top Indian brands in the {task.keywords} segment*
        """
        
        return formatted_response

    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        return "Unable to generate summary at this time."

@login_required
def task_list(request):
    tasks = ScrapingTask.objects.filter(user=request.user)
    return render(request, 'webscraper/task_list.html', {'tasks': tasks})

@login_required
def task_detail(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    
    # Generate summary if task is completed
    summary = None
    if task.status == 'completed':
        # Make sure completed_at is timezone aware
        if task.completed_at and task.completed_at.tzinfo is None:
            task.completed_at = task.completed_at.replace(tzinfo=timezone.utc)
        
        try:
            summary = generate_content_summary(task)
            
            # Store summary in ART model
            art = ART.objects.filter(
                user=request.user,
                analysis_query=task.keywords
            ).first()
            
            if art:
                art.web_analysis_result = summary
                art.save()
                print(f"Successfully saved web analysis result for query: {task.keywords}")
            else:
                # Create new ART record if none exists
                art = ART.objects.create(
                    user=request.user,
                    analysis_query=task.keywords,
                    web_analysis_result=summary
                )
                print(f"Created new ART record for query: {task.keywords}")
        except Exception as e:
            print(f"Error generating or saving summary: {str(e)}")
            summary = "Error generating summary. Please try again later."
    
    return render(request, 'webscraper/task_detail.html', {
        'task': task,
        'summary': summary,
        'art_record': art if 'art' in locals() else None
    })

@login_required
def new_task(request):
    if request.method == 'POST':
        form = ScrapingTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            
            # Get URLs based on keywords
            keywords = form.cleaned_data['keywords']
            urls = get_search_urls(keywords)
            
            if urls:
                task.urls_to_scrape = urls
                task.url = urls[0]
                task.save()
                
                # Get or create ART record
                art = ART.objects.filter(
                    user=request.user,
                    analysis_query=keywords
                ).first()
                
                if not art:
                    art = ART.objects.create(
                        user=request.user,
                        analysis_query=keywords
                    )
                
                perform_scraping(task.id)
                return redirect('webscraper:task_detail', task_id=task.id)
            else:
                form.add_error(None, "Could not find relevant URLs for these keywords")
    else:
        form = ScrapingTaskForm()
    
    # Get previous queries for dropdown
    previous_queries = list(ART.get_previous_queries(request.user))
    
    return render(request, 'webscraper/new_task.html', {
        'form': form,
        'previous_queries': previous_queries
    })

def perform_scraping(task_id):
    """Perform scraping using Botasaurus with improved error handling and rate limiting"""
    task = ScrapingTask.objects.get(id=task_id)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

        for url in task.urls_to_scrape:
            try:
                # Add random delay between requests (2-5 seconds)
                time.sleep(random.uniform(2, 5))
                
                # Make request using Botasaurus
                req = Request()
                response = req.get(url, headers=headers)
                
                # Get the raw HTML content
                html_content = response.text
                
                # Create soup object from the HTML
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extract main article content (adjust selectors based on the website)
                article_selectors = [
                    'article',
                    '.article-content',
                    '.post-content',
                    '.entry-content',
                    '.content',
                    'main',
                    '#main-content'
                ]
                
                main_content = None
                for selector in article_selectors:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break
                
                if not main_content:
                    main_content = soup.body if soup.body else soup
                
                # Extract data
                page_data = {
                    "url": url,
                    "title": soup.title.string if soup.title else "",
                    "meta_tags": {
                        meta.get('name', meta.get('property', '')): meta.get('content', '')
                        for meta in soup.find_all('meta')
                        if meta.get('name') or meta.get('property')
                    },
                    "content": {
                        "headings": {
                            f"h{i}": [
                                {
                                    "text": h.get_text(strip=True),
                                    "html": str(h)
                                }
                                for h in main_content.find_all(f'h{i}')
                            ]
                            for i in range(1, 7)
                        },
                        "paragraphs": [
                            {
                                "text": p.get_text(strip=True),
                                "html": str(p)
                            }
                            for p in main_content.find_all('p')
                        ],
                        "images": [
                            {
                                "src": img.get('src', ''),
                                "alt": img.get('alt', ''),
                                "title": img.get('title', '')
                            }
                            for img in main_content.find_all('img')
                        ],
                        "full_text": ' '.join(
                            text.strip()
                            for text in main_content.stripped_strings
                            if text.strip()
                        ),
                        "full_html": str(main_content)
                    }
                }

                # Create ScrapedPage
                scraped_page = ScrapedPage.objects.create(
                    task=task,
                    url=url,
                    title=page_data["title"],
                    full_text=page_data["content"]["full_text"],
                    full_html=page_data["content"]["full_html"],
                    raw_data=page_data
                )
                
                # Save headings
                for level in range(1, 7):
                    heading_key = f"h{level}"
                    for heading in page_data["content"]["headings"][heading_key]:
                        PageHeading.objects.create(
                            page=scraped_page,
                            level=level,
                            text=heading["text"],
                            html=heading["html"]
                        )
                
                # Save images
                for img in page_data["content"]["images"]:
                    src = img["src"]
                    if src:
                        if not src.startswith(('http://', 'https://')):
                            src = urljoin(url, src)
                        PageImage.objects.create(
                            page=scraped_page,
                            src=src,
                            alt=img["alt"],
                            title=img["title"]
                        )
                
                print(f"Successfully scraped: {url}")
                
            except Exception as e:
                print(f"Error scraping {url}: {str(e)}")
                continue
        
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        
    except Exception as e:
        task.status = 'failed'
        task.save()
        print(f"Task failed: {str(e)}")
