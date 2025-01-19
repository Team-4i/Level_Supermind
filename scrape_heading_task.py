from botasaurus.request import request, Request
from botasaurus.soupify import soupify
from urllib.parse import urljoin, urlparse
import re

def is_valid_url(url, base_domain):
    """Check if URL is valid and belongs to the same domain"""
    try:
        parsed = urlparse(url)
        return parsed.netloc == base_domain and bool(parsed.scheme)
    except:
        return False

def extract_text_content(element):
    """Extract clean text content from an element"""
    if element.name in ['script', 'style', 'meta', 'link']:
        return ''
    
    text = element.get_text(strip=True, separator=' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

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

def extract_meta_tags(soup):
    """Extract all meta tags"""
    meta_tags = {}
    for meta in soup.find_all('meta'):
        name = meta.get('name', meta.get('property', ''))
        if name:
            meta_tags[name] = meta.get('content', '')
    return meta_tags

@request
def scrape_heading_task(request: Request, data):
    base_url = data["link"]
    base_domain = urlparse(base_url).netloc
    
    visited_urls = set()
    website_data = {
        "pages": []
    }

    def scrape_page(url):
        # Stop if we've already scraped 10 pages
        if len(visited_urls) >= 10:
            return
            
        if url in visited_urls:
            return
        
        visited_urls.add(url)
        
        try:
            response = request.get(url)
            soup = soupify(response)
            
            page_data = {
                "url": url,
                "title": soup.title.string if soup.title else "",
                "meta_tags": extract_meta_tags(soup),
                "content": {
                    "headings": {
                        "h1": [{"text": h.get_text(strip=True), "html": str(h)} for h in soup.find_all('h1')],
                        "h2": [{"text": h.get_text(strip=True), "html": str(h)} for h in soup.find_all('h2')],
                        "h3": [{"text": h.get_text(strip=True), "html": str(h)} for h in soup.find_all('h3')],
                        "h4": [{"text": h.get_text(strip=True), "html": str(h)} for h in soup.find_all('h4')],
                        "h5": [{"text": h.get_text(strip=True), "html": str(h)} for h in soup.find_all('h5')],
                        "h6": [{"text": h.get_text(strip=True), "html": str(h)} for h in soup.find_all('h6')]
                    },
                    "paragraphs": [{"text": p.get_text(strip=True), "html": str(p)} for p in soup.find_all('p')],
                    "lists": {
                        "ordered": [{"items": [li.get_text(strip=True) for li in ol.find_all('li')], "html": str(ol)} 
                                  for ol in soup.find_all('ol')],
                        "unordered": [{"items": [li.get_text(strip=True) for li in ul.find_all('li')], "html": str(ul)} 
                                    for ul in soup.find_all('ul')]
                    },
                    "tables": [{"html": str(table), 
                              "data": [[cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])] 
                                     for row in table.find_all('tr')]}
                             for table in soup.find_all('table')],
                    "images": extract_images(soup),
                    "links": [],
                    "full_text": extract_text_content(soup.body) if soup.body else "",
                    "full_html": str(soup.body) if soup.body else ""
                }
            }
            
            # Find all links on the page
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                absolute_url = urljoin(url, href)
                
                if is_valid_url(absolute_url, base_domain):
                    link_data = {
                        "url": absolute_url,
                        "text": link.get_text(strip=True),
                        "title": link.get('title', ''),
                        "html": str(link)
                    }
                    page_data["content"]["links"].append(link_data)
                    # Only continue scraping if we haven't reached 10 pages
                    if len(visited_urls) < 10:
                        scrape_page(absolute_url)
            
            website_data["pages"].append(page_data)
            
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
    
    # Start scraping from the base URL
    scrape_page(base_url)
    
    # Add overall statistics
    website_data["total_pages"] = len(website_data["pages"])
    website_data["base_domain"] = base_domain
    
    return website_data
     