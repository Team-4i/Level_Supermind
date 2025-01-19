import streamlit as st
from dotenv import load_dotenv
import os
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
from datetime import datetime
import pandas as pd
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import re

# Download NLTK data for sentiment analysis
nltk.download('vader_lexicon')

# Load environment variables and configure APIs
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

genai.configure(api_key=GOOGLE_API_KEY)
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

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
        st.error(f"Error fetching video details: {str(e)}")
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
        st.error(f"Error fetching comments: {str(e)}")
        return []

def analyze_sentiment(text):
    """Analyze sentiment of text using NLTK's VADER"""
    sia = SentimentIntensityAnalyzer()
    sentiment = sia.polarity_scores(text)
    return sentiment

def generate_content_analysis(transcript_text):
    """Generate content analysis using Gemini Pro"""
    prompt = """
    Analyze this video transcript and provide insights on:
    1. Main topics and themes
    2. Key pain points addressed
    3. Solutions offered
    4. Call to actions (CTAs) used
    5. Content style and format
    Provide the analysis in a clear, structured format.
    """
    
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt + transcript_text)
    return response.text

def search_videos(keyword, max_results=10):
    """Search YouTube videos based on keyword"""
    try:
        search_response = youtube.search().list(
            q=keyword,
            part='id,snippet',
            maxResults=max_results,
            type='video',
            relevanceLanguage='en',
            order='relevance'
        ).execute()

        videos = []
        for item in search_response['items']:
            video_data = {
                'title': item['snippet']['title'],
                'video_id': item['id']['videoId'],
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                'thumbnail': item['snippet']['thumbnails']['default']['url'],
                'description': item['snippet']['description'],
                'published_at': item['snippet']['publishedAt']
            }
            
            # Get video statistics
            stats = youtube.videos().list(
                part='statistics',
                id=item['id']['videoId']
            ).execute()
            
            if stats['items']:
                statistics = stats['items'][0]['statistics']
                video_data.update({
                    'view_count': int(statistics.get('viewCount', 0)),
                    'like_count': int(statistics.get('likeCount', 0)),
                    'comment_count': int(statistics.get('commentCount', 0))
                })
            
            videos.append(video_data)
            
        return videos
    except Exception as e:
        st.error(f"Error searching videos: {str(e)}")
        return []

def generate_ad_keywords(product_description):
    """Generate advertising-focused keywords for Indian brands using Gemini Pro"""
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

def check_transcript_availability(video_id):
    """Check if video has available transcript"""
    try:
        YouTubeTranscriptApi.get_transcript(video_id)
        return True
    except:
        return False

def search_ad_videos(keyword, max_results=10):
    """Search YouTube videos focusing on Indian ads and commercials with transcripts"""
    try:
        search_response = youtube.search().list(
            q=f"{keyword}",
            part='id,snippet',
            maxResults=max_results * 2,
            type='video',
            videoDuration='short',
            order='viewCount',  # Changed to get popular videos first
            videoDefinition='high',
            regionCode='IN',    # Changed to India
            relevanceLanguage='en'  # Include English language ads
        ).execute()

        videos = []
        for item in search_response['items']:
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
            
        return videos
    except Exception as e:
        st.error(f"Error searching videos: {str(e)}")
        return []

def collect_video_data(video_id):
    """Collect comprehensive data for a single video"""
    try:
        # Get transcript
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([i["text"] for i in transcript])
        
        # Get video details
        video_response = youtube.videos().list(
            part='snippet,statistics',
            id=video_id
        ).execute()
        
        # Get comments
        comments = []
        try:
            comment_response = youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=100,
                textFormat='plainText'
            ).execute()
            
            for item in comment_response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'text': comment['textDisplay'],
                    'likes': comment['likeCount'],
                    'sentiment': analyze_sentiment(comment['textDisplay'])
                })
        except:
            pass  # Some videos might have comments disabled
        
        return {
            'transcript': transcript_text,
            'details': video_response['items'][0],
            'comments': comments
        }
    except Exception as e:
        return None

def calculate_comment_metrics(comments_data):
    """Calculate numerical metrics from comments"""
    metrics = {
        'sentiment_stats': {'positive': 0, 'negative': 0, 'neutral': 0},
        'engagement_by_sentiment': {'positive': 0, 'negative': 0, 'neutral': 0},
        'total_likes': 0,
        'total_comments': 0
    }
    
    for video_data in comments_data:
        for comment in video_data['comments']:
            metrics['total_comments'] += 1
            metrics['total_likes'] += comment['likes']
            
            # Categorize sentiment
            sentiment_score = comment['sentiment']['compound']
            if sentiment_score >= 0.05:
                metrics['sentiment_stats']['positive'] += 1
                metrics['engagement_by_sentiment']['positive'] += comment['likes']
            elif sentiment_score <= -0.05:
                metrics['sentiment_stats']['negative'] += 1
                metrics['engagement_by_sentiment']['negative'] += comment['likes']
            else:
                metrics['sentiment_stats']['neutral'] += 1
                metrics['engagement_by_sentiment']['neutral'] += comment['likes']
    
    # Calculate percentages
    total = metrics['total_comments']
    if total > 0:
        metrics['sentiment_percentages'] = {
            'positive': (metrics['sentiment_stats']['positive'] / total) * 100,
            'negative': (metrics['sentiment_stats']['negative'] / total) * 100,
            'neutral': (metrics['sentiment_stats']['neutral'] / total) * 100
        }
    
    return metrics

def generate_comprehensive_analysis(all_videos_data):
    """Generate focused analysis with numerical metrics"""
    
    analysis_data = {
        'comments_analysis': [],
        'engagement_metrics': [],
        'transcripts': []
    }
    
    # Process video data as before...
    for video in all_videos_data:
        if video:
            if video['transcript']:
                analysis_data['transcripts'].append({
                    'text': video['transcript'],
                    'title': video['details']['snippet']['title']
                })
            
            if 'statistics' in video['details']:
                analysis_data['engagement_metrics'].append({
                    'views': video['details']['statistics'].get('viewCount', 0),
                    'likes': video['details']['statistics'].get('likeCount', 0),
                    'title': video['details']['snippet']['title']
                })
            
            if video['comments']:
                analysis_data['comments_analysis'].append({
                    'comments': video['comments'],
                    'video_title': video['details']['snippet']['title']
                })

    # Calculate comment metrics
    comment_metrics = calculate_comment_metrics(analysis_data['comments_analysis'])

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
    
    model = genai.GenerativeModel('gemini-pro')
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
    - Videos Analyzed: {len(all_videos_data)}
    - Average Engagement: {calculate_average_engagement(analysis_data['engagement_metrics'])}

    DETAILED ANALYSIS:
    {response.text}
    """
    
    return final_analysis

def calculate_average_engagement(metrics):
    """Calculate average engagement from available metrics"""
    if not metrics:
        return 0
    total_views = sum(int(m['views']) for m in metrics)
    total_likes = sum(int(m['likes']) for m in metrics)
    return f"Views: {total_views/len(metrics):,.0f}, Likes: {total_likes/len(metrics):,.0f}"

def main():
    st.title("Indian Brand Ad Research Tool")
    
    # Initialize session state
    if 'videos_data' not in st.session_state:
        st.session_state.videos_data = []
    if 'all_videos' not in st.session_state:
        st.session_state.all_videos = []
    if 'comprehensive_analysis' not in st.session_state:
        st.session_state.comprehensive_analysis = None
    
    tab1, tab2 = st.tabs(["Indian Ad Research", "Video Analysis"])
    
    with tab1:
        st.subheader("Find Indian Advertising Content for Your Product/Company")
        
        product_description = st.text_area(
            "Describe your product, company, or industry:",
            help="Include: target audience, key features, industry, and Indian market competitors"
        )
        
        total_videos = st.slider(
            "Total number of ad videos to find",
            min_value=2,
            max_value=50,
            value=10,
            step=2,
            help="Total number of Indian advertisement videos to collect (must be even number)"
        )
        
        search_clicked = st.button("Find Indian Ad Content")
        
        if search_clicked and product_description:
            with st.spinner("Searching for Indian advertising content with transcripts..."):
                keywords = generate_ad_keywords(product_description)
                
                st.subheader("Generated Indian Ad Keywords:")
                for keyword in keywords:
                    st.info(f"🎯 {keyword}")
                
                # Calculate distribution
                videos_per_keyword = max(2, (total_videos // len(keywords)) // 2 * 2)
                remaining_videos = total_videos - (videos_per_keyword * len(keywords))
                
                all_videos = []
                videos_data = []
                
                for i, keyword in enumerate(keywords):
                    current_video_count = videos_per_keyword
                    if remaining_videos > 0:
                        current_video_count += 2
                        remaining_videos -= 2
                        
                    videos = search_ad_videos(keyword, current_video_count)
                    all_videos.extend(videos)
                    
                    # Collect comprehensive data for each video
                    for video in videos:
                        video_data = collect_video_data(video['video_id'])
                        if video_data:
                            videos_data.append(video_data)
                    
                    if len(all_videos) >= total_videos:
                        break
                
                # Store in session state
                st.session_state.all_videos = all_videos
                st.session_state.videos_data = videos_data
                # Reset analysis when new search is performed
                st.session_state.comprehensive_analysis = None
        
        # Display videos if they exist in session state
        if st.session_state.all_videos:
            st.subheader(f"Found Ad Content (Total: {len(st.session_state.all_videos)} videos with transcripts)")
            
            for keyword in set(v['keyword_used'] for v in st.session_state.all_videos):
                keyword_videos = [v for v in st.session_state.all_videos if v['keyword_used'] == keyword]
                if keyword_videos:
                    with st.expander(f"📺 Ads for: {keyword} ({len(keyword_videos)} videos)"):
                        for video in keyword_videos:
                            st.write("---")
                            cols = st.columns([3, 1])
                            with cols[0]:
                                st.write(f"**{video['title']}**")
                                st.write(f"🔗 [Watch Ad]({video['url']})")
                                st.write(f"📝 {video['description'][:150]}...")
                                st.write("✅ Transcript Available")
                            with cols[1]:
                                st.write(f"👀 Views: {video['view_count']:,}")
                                st.write(f"👍 Likes: {video['like_count']:,}")
            
            # Analysis section
            st.subheader("Generate Analysis")
            if st.button("Analyze All Videos", key="analyze_button"):
                with st.spinner("Generating comprehensive analysis..."):
                    st.session_state.comprehensive_analysis = generate_comprehensive_analysis(st.session_state.videos_data)
            
            # Display analysis if available
            if st.session_state.comprehensive_analysis:
                st.subheader("📊 Comprehensive Advertising Strategy Analysis")
                st.markdown(st.session_state.comprehensive_analysis)
                
                # Download button for analysis
                st.download_button(
                    "📥 Download Complete Analysis (TXT)",
                    st.session_state.comprehensive_analysis,
                    "ad_strategy_analysis.txt",
                    "text/plain",
                    key='download-analysis'
                )

    with tab2:
        # Keep existing video analysis functionality
        st.subheader("Analyze Individual Video")
        youtube_url = st.text_input("Enter YouTube Video URL:")
        if st.button("Analyze Video"):
            if youtube_url:
                video_id = extract_video_id(youtube_url)
                
                if video_id:
                    with st.spinner("Analyzing video..."):
                        # Get video details
                        video_details = get_video_details(video_id)
                        
                        if video_details:
                            # Display video metadata
                            st.subheader("Video Details")
                            st.write(f"Title: {video_details['title']}")
                            st.write(f"Views: {video_details['view_count']:,}")
                            st.write(f"Likes: {video_details['like_count']:,}")
                            st.write(f"Comments: {video_details['comment_count']:,}")
                            
                            # Get and analyze transcript
                            try:
                                transcript = YouTubeTranscriptApi.get_transcript(video_id)
                                transcript_text = " ".join([i["text"] for i in transcript])
                                
                                # Generate content analysis
                                st.subheader("Content Analysis")
                                analysis = generate_content_analysis(transcript_text)
                                st.write(analysis)
                                
                                # Get and analyze comments
                                st.subheader("Comment Analysis")
                                comments = get_video_comments(video_id)
                                
                                if comments:
                                    # Sentiment analysis of comments
                                    sentiments = []
                                    for comment in comments:
                                        sentiment = analyze_sentiment(comment['text'])
                                        sentiments.append(sentiment['compound'])
                                    
                                    # Display sentiment summary
                                    avg_sentiment = sum(sentiments) / len(sentiments)
                                    st.write(f"Average Comment Sentiment: {avg_sentiment:.2f}")
                                    
                                    # Display top comments
                                    st.write("Top Comments:")
                                    df_comments = pd.DataFrame(comments)
                                    st.dataframe(df_comments)
                                
                            except Exception as e:
                                st.error(f"Error analyzing video: {str(e)}")
                        else:
                            st.error("Could not fetch video details")
                else:
                    st.error("Invalid YouTube URL")

if __name__ == "__main__":
    main()