from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from dotenv import load_dotenv
import os
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
import json
import logging
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import traceback
from googleapiclient.http import HttpError
from time import sleep
from users.models import ART

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables and configure APIs
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    nltk.download('vader_lexicon', quiet=True)
except Exception as e:
    logger.error(f"Error initializing APIs: {str(e)}")
    raise

@ensure_csrf_cookie
@login_required
def scraper_home(request):
    # Get all user's queries, including analyzed ones
    user_queries = ART.objects.filter(user=request.user)
    return render(request, 'ytscraper/scraper_home.html', {
        'user_queries': user_queries
    })

@login_required
def search_ads(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_description = data.get('product_description')
            total_videos = int(data.get('total_videos', 10))  # This is your requested count
            
            # Generate keywords
            keywords = generate_ad_keywords(product_description)
            
            all_videos = []
            videos_data = []
            
            # Calculate videos per keyword more precisely
            videos_per_keyword = max(1, total_videos // len(keywords))
            
            for keyword in keywords:
                # Only search if we haven't reached the total
                if len(all_videos) >= total_videos:
                    break
                    
                # Calculate how many more videos we need
                remaining_needed = total_videos - len(all_videos)
                current_video_count = min(videos_per_keyword, remaining_needed)
                
                # Search for videos with exact count needed
                videos = search_ad_videos(keyword, current_video_count)
                if videos:
                    # Only take what we need
                    available_slots = total_videos - len(all_videos)
                    videos = videos[:available_slots]
                    all_videos.extend(videos)
                    
                    # Collect data for these videos
                    for video in videos:
                        video_data = collect_video_data(video['video_id'])
                        if video_data:
                            videos_data.append(video_data)
            
            if not all_videos:
                return JsonResponse({'error': 'No videos found'}, status=404)
            
            # Store in session
            request.session['all_videos'] = all_videos
            request.session['videos_data'] = videos_data
            
            return JsonResponse({
                'status': 'success',
                'keywords': keywords,
                'videos': all_videos,
                'message': f'Successfully found {len(all_videos)} videos'
            })
            
        except Exception as e:
            logger.error(f"Error in search process: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

def generate_ad_keywords(product_description):
    """Generate advertising-focused keywords for Indian brands using Gemini Pro"""
    try:
        prompt = f"""
        Based on this product/company description: "{product_description}"
        
        Generate:
        1. 5-7 specific advertising-focused keywords for Indian market that would help find:
           - Indian brand marketing campaigns
           - Popular Indian advertisements
           - Indian TV commercials
           - Brand promotions in India
           - Competitor ads in Indian market
        
        Consider:
        - Popular Indian brands in this category
        - Indian advertising styles and trends
        - Festival and cultural campaign terms
        - Regional market variations
        - Indian consumer preferences
        
        Format each keyword as: "brand/product + India + (ad OR commercial OR advertisement OR TVC)"
        Examples: 
        - "Tata tea India commercial"
        - "Flipkart Diwali ad"
        - "Amul India TVC"
        - "Indian brand advertisement"
        
        Return only the keywords, one per line, without numbering or bullets.
        Focus on popular and well-established Indian brands.
        """
        
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        keywords = response.text.strip().split('\n')
        return [k.strip() for k in keywords if k.strip()]
    except Exception as e:
        logger.error(f"Error generating keywords: {str(e)}\n{traceback.format_exc()}")
        raise

def search_ad_videos(keyword, max_results=10):
    """Search YouTube videos focusing on Indian ads and commercials with transcripts"""
    try:
        # Add timeout and retry logic
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"Attempting YouTube API request for keyword: {keyword} (attempt {retry_count + 1})")
                search_response = youtube.search().list(
                    q=f"{keyword}",
                    part='id,snippet',
                    maxResults=max_results * 2,
                    type='video',
                    videoDuration='short',
                    order='viewCount',
                    videoDefinition='high',
                    regionCode='IN',
                    relevanceLanguage='en'
                ).execute()
                
                logger.info(f"Successfully retrieved search results for: {keyword}")
                break
            
            except HttpError as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"YouTube API request failed after {max_retries} attempts: {str(e)}")
                    raise
                logger.warning(f"YouTube API request failed (attempt {retry_count}): {str(e)}")
                sleep(2 ** retry_count)  # Exponential backoff
        
        videos = []
        for item in search_response['items']:
            try:
                video_id = item['id']['videoId']
                
                # Only include videos with available transcripts
                if check_transcript_availability(video_id):
                    video_data = {
                        'title': item['snippet']['title'],
                        'video_id': video_id,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'description': item['snippet']['description'],
                        'keyword_used': keyword,
                        'published_at': item['snippet']['publishedAt']
                    }
                    
                    # Get video statistics
                    stats = youtube.videos().list(
                        part='statistics,contentDetails',
                        id=video_id
                    ).execute()
                    
                    if stats['items']:
                        statistics = stats['items'][0]['statistics']
                        video_data.update({
                            'view_count': int(statistics.get('viewCount', 0)),
                            'like_count': int(statistics.get('likeCount', 0)),
                            'duration': stats['items'][0]['contentDetails']['duration']
                        })
                    
                    videos.append(video_data)
                    
                    if len(videos) >= max_results:
                        break
            except Exception as e:
                logger.error(f"Error processing video {video_id}: {str(e)}")
                continue
                
        return videos
    except Exception as e:
        logger.error(f"Error searching videos: {str(e)}\n{traceback.format_exc()}")
        raise

def check_transcript_availability(video_id):
    """Check if a video has available transcripts"""
    try:
        YouTubeTranscriptApi.get_transcript(video_id)
        return True
    except Exception as e:
        logger.debug(f"No transcript available for video {video_id}: {str(e)}")
        return False

@login_required
def analyze_videos(request):
    if request.method == 'POST':
        videos_data = request.session.get('videos_data', [])
        analysis = generate_comprehensive_analysis(videos_data)
        request.session['comprehensive_analysis'] = analysis
        return JsonResponse({'analysis': analysis})
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def analyze_single_video(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        youtube_url = data.get('youtube_url')
        
        if not youtube_url:
            return JsonResponse({'error': 'No URL provided'}, status=400)
            
        video_id = extract_video_id(youtube_url)
        if not video_id:
            return JsonResponse({'error': 'Invalid YouTube URL'}, status=400)
            
        # Get video details
        video_details = get_video_details(video_id)
        if not video_details:
            return JsonResponse({'error': 'Could not fetch video details'}, status=400)
            
        response_data = {
            'video_details': video_details
        }
        
        try:
            # Get and analyze transcript
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            transcript_text = " ".join([i["text"] for i in transcript])
            analysis = generate_content_analysis(transcript_text)
            response_data['content_analysis'] = analysis
            
            # Get and analyze comments
            comments = get_video_comments(video_id)
            if comments:
                sentiments = []
                for comment in comments:
                    sentiment = analyze_sentiment(comment['text'])
                    sentiments.append(sentiment['compound'])
                
                avg_sentiment = sum(sentiments) / len(sentiments)
                response_data.update({
                    'comments': comments,
                    'avg_sentiment': avg_sentiment
                })
                
        except Exception as e:
            response_data['error'] = str(e)
        
        return JsonResponse(response_data)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def download_analysis(request):
    if request.method == 'GET':
        analysis = request.session.get('comprehensive_analysis')
        if analysis:
            response = HttpResponse(analysis, content_type='text/plain')
            response['Content-Disposition'] = 'attachment; filename="ad_strategy_analysis.txt"'
            return response
    return JsonResponse({'error': 'No analysis available'}, status=400)

def test_apis(request):
    try:
        # Test Google API
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content("Hello")
        
        # Test YouTube API
        youtube_response = youtube.search().list(
            part='id',
            maxResults=1
        ).execute()
        
        return HttpResponse("APIs working correctly!")
    except Exception as e:
        return HttpResponse(f"API Error: {str(e)}")

def collect_video_data(video_id):
    """Collect comprehensive data for a video including details, transcript, and comments"""
    try:
        # Get basic video details
        video_details = get_video_details(video_id)
        if not video_details:
            return None
            
        # Get transcript
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            transcript_text = " ".join([i["text"] for i in transcript])
        except Exception as e:
            logger.error(f"Error getting transcript for {video_id}: {str(e)}")
            transcript_text = ""
            
        # Get comments and analyze sentiment
        comments = get_video_comments(video_id)
        comment_analysis = []
        for comment in comments:
            sentiment = analyze_sentiment(comment['text'])
            comment_analysis.append({
                'text': comment['text'],
                'sentiment': sentiment['compound'],
                'likes': comment['likes']
            })
            
        return {
            'video_id': video_id,
            'details': video_details,
            'transcript': transcript_text,
            'comments': comment_analysis
        }
    except Exception as e:
        logger.error(f"Error collecting video data: {str(e)}")
        return None

def generate_comprehensive_analysis(videos_data):
    """Generate focused analysis with numerical metrics"""
    try:
        if not videos_data:
            return "No video data available for analysis."
            
        analysis_data = {
            'comments_analysis': [],
            'engagement_metrics': [],
            'transcripts': []
        }
        
        # Process video data
        for video in videos_data:
            if video:
                if video.get('transcript'):
                    analysis_data['transcripts'].append({
                        'text': video['transcript'],
                        'title': video['details']['title']
                    })
                
                analysis_data['engagement_metrics'].append({
                    'views': video['details']['view_count'],
                    'likes': video['details']['like_count'],
                    'title': video['details']['title']
                })
                
                if video.get('comments'):
                    analysis_data['comments_analysis'].append({
                        'comments': video['comments'],
                        'video_title': video['details']['title']
                    })

        # Calculate comment metrics
        comment_metrics = calculate_comment_metrics(analysis_data['comments_analysis'])
        
        # Generate analysis using Gemini
        model = genai.GenerativeModel('gemini-pro')
        analysis_prompt = f"""
        Analyze these Indian advertisements with focus on numerical insights.
        
        COMMENT METRICS:
        - Total Comments Analyzed: {comment_metrics['total_comments']}
        - Total Comment Likes: {comment_metrics['total_likes']}
        
        Sentiment Distribution:
        - Positive: {comment_metrics['sentiment_percentages']['positive']:.1f}%
        - Negative: {comment_metrics['sentiment_percentages']['negative']:.1f}%
        - Neutral: {comment_metrics['sentiment_percentages']['neutral']:.1f}%
        
        Engagement by Sentiment:
        - Positive Comments: {comment_metrics['engagement_by_sentiment']['positive']} likes
        - Negative Comments: {comment_metrics['engagement_by_sentiment']['negative']} likes
        - Neutral Comments: {comment_metrics['engagement_by_sentiment']['neutral']} likes

        Provide analysis in these sections:

        1. AUDIENCE INSIGHTS (with metrics)
        - Key pain points and positive triggers (with frequency)
        - Most engaged topics (by comment likes)
        - Sentiment patterns across topics
        - Common feedback themes (with percentages)
        Include specific comment quotes as examples.

        2. CONTENT EFFECTIVENESS
        - Successful messaging approaches
        - High-performing features/benefits
        - Effective emotional appeals
        - Impactful CTAs and hooks
        Use specific examples from top-performing ads.

        3. CULTURAL & MARKET ELEMENTS
        - Cultural references that resonated
        - Market positioning strategies
        - Local preferences and trends
        Support with user reactions and content examples.

        Use this data:
        
        Top Comments: 
        {[{
            'text': c['text'],
            'sentiment': c['sentiment'],
            'likes': c['likes']
        } for data in analysis_data['comments_analysis'] for c in data['comments'][:20]]}

        Best Performing Ads:
        {sorted(analysis_data['engagement_metrics'], key=lambda x: int(x['views']), reverse=True)[:3]}

        Key Transcript Elements:
        {[{
            'title': t['title'],
            'highlights': t['text'][:200] + '...'
        } for t in analysis_data['transcripts']]}

        IMPORTANT:
        - Include numerical insights where relevant
        - Focus on data-backed findings
        - Highlight engagement patterns
        - Show sentiment distribution for key topics
        """
        
        response = model.generate_content(analysis_prompt)
        
        final_analysis = f"""
        📊 AD CAMPAIGN ANALYSIS

        NUMERICAL INSIGHTS:
        Comments Overview:
        - Total Comments: {comment_metrics['total_comments']}
        - Total Engagement: {comment_metrics['total_likes']} likes
        
        Sentiment Distribution:
        - 👍 Positive: {comment_metrics['sentiment_percentages']['positive']:.1f}%
        - 👎 Negative: {comment_metrics['sentiment_percentages']['negative']:.1f}%
        - 😐 Neutral: {comment_metrics['sentiment_percentages']['neutral']:.1f}%
        
        Engagement Analysis:
        - Positive Comments: {comment_metrics['engagement_by_sentiment']['positive']} likes
        - Negative Comments: {comment_metrics['engagement_by_sentiment']['negative']} likes
        - Neutral Comments: {comment_metrics['engagement_by_sentiment']['neutral']} likes

        Videos Coverage:
        - Videos Analyzed: {len(videos_data)}
        - Average Engagement: {calculate_average_engagement(analysis_data['engagement_metrics'])}

        DETAILED ANALYSIS:
        {response.text}
        """
        
        return final_analysis
        
    except Exception as e:
        logger.error(f"Error generating analysis: {str(e)}\n{traceback.format_exc()}")
        return f"Error generating analysis: {str(e)}"

def calculate_comment_metrics(comments_analysis):
    """Calculate metrics from comments"""
    metrics = {
        'total_comments': 0,
        'total_likes': 0,
        'sentiment_counts': {'positive': 0, 'negative': 0, 'neutral': 0},
        'engagement_by_sentiment': {'positive': 0, 'negative': 0, 'neutral': 0}
    }
    
    for video_comments in comments_analysis:
        for comment in video_comments['comments']:
            metrics['total_comments'] += 1
            metrics['total_likes'] += comment['likes']
            
            if comment['sentiment'] > 0.05:
                metrics['sentiment_counts']['positive'] += 1
                metrics['engagement_by_sentiment']['positive'] += comment['likes']
            elif comment['sentiment'] < -0.05:
                metrics['sentiment_counts']['negative'] += 1
                metrics['engagement_by_sentiment']['negative'] += comment['likes']
            else:
                metrics['sentiment_counts']['neutral'] += 1
                metrics['engagement_by_sentiment']['neutral'] += comment['likes']
    
    total = sum(metrics['sentiment_counts'].values()) or 1
    metrics['sentiment_percentages'] = {
        'positive': (metrics['sentiment_counts']['positive'] / total) * 100,
        'negative': (metrics['sentiment_counts']['negative'] / total) * 100,
        'neutral': (metrics['sentiment_counts']['neutral'] / total) * 100
    }
    
    return metrics

def calculate_average_engagement(metrics):
    """Calculate average engagement from metrics"""
    if not metrics:
        return 0
    total_views = sum(int(m['views']) for m in metrics)
    total_likes = sum(int(m['likes']) for m in metrics)
    return f"{total_views/len(metrics):,.0f} views, {total_likes/len(metrics):,.0f} likes per video"

def get_video_details(video_id):
    """Get video metadata using YouTube API"""
    try:
        video_response = youtube.videos().list(
            part='snippet,statistics',
            id=video_id
        ).execute()

        if not video_response['items']:
            return None

        video_data = video_response['items'][0]
        return {
            'title': video_data['snippet']['title'],
            'description': video_data['snippet']['description'],
            'view_count': int(video_data['statistics'].get('viewCount', 0)),
            'like_count': int(video_data['statistics'].get('likeCount', 0)),
            'comment_count': int(video_data['statistics'].get('commentCount', 0)),
            'publish_date': video_data['snippet']['publishedAt']
        }
    except Exception as e:
        logger.error(f"Error fetching video details: {str(e)}")
        return None

def get_video_comments(video_id, max_comments=100):
    """Get video comments using YouTube API"""
    try:
        comments = []
        request = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            maxResults=max_comments,
            textFormat='plainText'
        )
        
        while request and len(comments) < max_comments:
            response = request.execute()
            
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'text': comment['textDisplay'],
                    'likes': comment['likeCount'],
                    'publish_date': comment['publishedAt']
                })
            
            request = youtube.commentThreads().list_next(request, response)
            
        return comments
    except Exception as e:
        logger.error(f"Error fetching comments: {str(e)}")
        return []

def analyze_sentiment(text):
    """Analyze sentiment of text using NLTK's VADER"""
    sia = SentimentIntensityAnalyzer()
    sentiment = sia.polarity_scores(text)
    return sentiment

@login_required
def analyze_query(request, query_id):
    try:
        art = ART.objects.get(id=query_id, user=request.user)
        
        # Get the query text
        query = art.analysis_query
        
        # Generate keywords for YouTube search
        keywords = generate_ad_keywords(query)
        
        # Store the keywords
        art.keywords = keywords
        
        # Search for videos
        all_videos = []
        videos_data = []
        total_videos = 10  # Adjust as needed
        videos_per_keyword = total_videos // len(keywords)
        remaining_videos = total_videos % len(keywords)
        
        content_data = {
            'videos': [],
            'metadata': {
                'total_videos': total_videos,
                'videos_per_keyword': videos_per_keyword
            }
        }
        
        for keyword in keywords:
            try:
                videos = search_ad_videos(keyword, videos_per_keyword)
                if videos:
                    all_videos.extend(videos)
                    
                    # Collect data for each video
                    for video in videos:
                        try:
                            video_data = collect_video_data(video['video_id'])
                            if video_data:
                                videos_data.append(video_data)
                                # Store in content
                                content_data['videos'].append({
                                    'keyword': keyword,
                                    'video_data': video_data
                                })
                        except Exception as e:
                            logger.error(f"Error collecting video data: {str(e)}")
                            continue
            except Exception as e:
                logger.error(f"Error processing keyword {keyword}: {str(e)}")
                continue
        
        if not videos_data:
            raise Exception("No videos found for analysis")
            
        # Generate comprehensive analysis
        analysis_result = generate_comprehensive_analysis(videos_data)
        
        # Store all data in ART model
        art.content = content_data
        art.analysis_result = analysis_result
        art.save()
        
        return JsonResponse({
            'status': 'success',
            'result': analysis_result
        })
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
