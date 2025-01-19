from django import forms
from .models import ScrapingTask

class ScrapingTaskForm(forms.ModelForm):
    class Meta:
        model = ScrapingTask
        fields = ['keywords']
        widgets = {
            'keywords': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter keywords (e.g., "gaming laptops under 1000")'
            })
        } 