from django.contrib import admin
from .models import UserProfile, ART

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company_name', 'industry', 'created_at']
    search_fields = ['user__username', 'company_name', 'industry']
    list_filter = ['industry']

@admin.register(ART)
class ARTAdmin(admin.ModelAdmin):
    list_display = ['user', 'analysis_query_preview', 'created_at']
    search_fields = ['user__username', 'analysis_query']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']

    def analysis_query_preview(self, obj):
        return obj.analysis_query[:100] + '...' if len(obj.analysis_query) > 100 else obj.analysis_query
    analysis_query_preview.short_description = 'Analysis Query'
