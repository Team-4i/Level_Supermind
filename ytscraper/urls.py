from django.urls import path
from django.views.generic import RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage
from . import views

app_name = 'ytscraper'

urlpatterns = [
    path('scraper-home/', views.scraper_home, name='scraper_home'),
    path('search-ads/', views.search_ads, name='search_ads'),
    path('analyze-videos/', views.analyze_videos, name='analyze_videos'),
    path('analyze-single-video/', views.analyze_single_video, name='analyze_single_video'),
    path('download-analysis/', views.download_analysis, name='download_analysis'),
    path('test-apis/', views.test_apis, name='test_apis'),
    path('analyze-query/<int:query_id>/', views.analyze_query, name='analyze_query'),
]

