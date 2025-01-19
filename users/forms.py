from django import forms
from .models import UserProfile, ART

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['bio', 'company_name', 'website', 'industry', 
                 'research_interests', 'preferred_platforms']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'research_interests': forms.Textarea(attrs={'rows': 4}),
        } 

class ARTForm(forms.ModelForm):
    class Meta:
        model = ART
        fields = ['analysis_query']
        widgets = {
            'analysis_query': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Describe your product or service for analysis...'
            }),
        } 