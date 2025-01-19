from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ScrapingTask(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    keywords = models.CharField(max_length=500)
    url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    urls_to_scrape = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-created_at']

class ScrapedPage(models.Model):
    task = models.ForeignKey(ScrapingTask, on_delete=models.CASCADE, related_name='pages')
    url = models.URLField()
    title = models.CharField(max_length=500, blank=True)
    full_text = models.TextField(blank=True)
    full_html = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    
    class Meta:
        unique_together = ['task', 'url']

class PageHeading(models.Model):
    page = models.ForeignKey(ScrapedPage, on_delete=models.CASCADE, related_name='headings')
    level = models.IntegerField()  # 1-6 for h1-h6
    text = models.TextField()
    html = models.TextField()

class PageImage(models.Model):
    page = models.ForeignKey(ScrapedPage, on_delete=models.CASCADE, related_name='images')
    src = models.URLField()
    alt = models.CharField(max_length=500, blank=True)
    title = models.CharField(max_length=500, blank=True)
