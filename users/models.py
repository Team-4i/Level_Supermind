from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .astra_utils import sync_to_astra

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    company_name = models.CharField(max_length=100, blank=True)
    website = models.URLField(max_length=200, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    research_interests = models.TextField(blank=True)
    preferred_platforms = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        sync_to_astra(self)

class ART(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='art_requests')
    analysis_query = models.TextField(
        help_text="Enter your product analysis query",
        default="Default product analysis query",
        blank=False,
    )
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Generated keywords for the analysis"
    )
    content = models.JSONField(
        default=dict,
        blank=True,
        help_text="Collected video content and data"
    )
    analysis_result = models.TextField(
        blank=True,
        null=True,
        help_text="Analysis results from YouTube scraper"
    )
    web_analysis_result = models.TextField(
        blank=True,
        null=True,
        help_text="Analysis results from web scraping"
    )
    overall_analysis = models.TextField(
        blank=True,
        null=True,
        help_text="Combined analysis from all sources"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        sync_to_astra(self)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Analysis Request"
        verbose_name_plural = "Analysis Requests"

    def __str__(self):
        preview = self.analysis_query[:50] + "..." if len(self.analysis_query) > 50 else self.analysis_query
        return f"Analysis Query: {preview}"

    @classmethod
    def get_previous_queries(cls, user):
        """Get all unique previous analysis queries for a user"""
        return cls.objects.filter(user=user)\
            .values_list('analysis_query', flat=True)\
            .distinct()\
            .order_by('-created_at')

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
