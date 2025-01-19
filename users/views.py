from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserProfileForm
from .models import ART
from .forms import ARTForm
import google.generativeai as genai
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            
    else:
        form = UserProfileForm(instance=request.user.profile)
    
    return render(request, 'users/profile_edit.html', {'form': form})

@login_required
def art_list(request):
    art_requests = ART.objects.filter(user=request.user)
    return render(request, 'users/art_list.html', {'art_requests': art_requests})

@login_required
def art_create(request):
    if request.method == 'POST':
        form = ARTForm(request.POST)
        if form.is_valid():
            art = form.save(commit=False)
            art.user = request.user
            art.save()
            messages.success(request, 'Analysis request created successfully!')
            return redirect('users:art_detail', pk=art.pk)
    else:
        form = ARTForm()
    return render(request, 'users/art_form.html', {'form': form})

@login_required
def art_detail(request, pk):
    art = ART.objects.get(pk=pk, user=request.user)
    return render(request, 'users/art_detail.html', {'art': art})

@login_required
def art_edit(request, pk):
    art = get_object_or_404(ART, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ARTForm(request.POST, instance=art)
        if form.is_valid():
            art = form.save()
            messages.success(request, 'Analysis request updated successfully!')
            return redirect('users:art_detail', pk=art.pk)
    else:
        form = ARTForm(instance=art)
    return render(request, 'users/art_form.html', {
        'form': form,
        'edit_mode': True,
        'art': art
    })

@login_required
def art_generate(request, pk):
    art = get_object_or_404(ART, pk=pk, user=request.user)
    
    # Skip if both analyses aren't complete
    if not art.analysis_result or not art.web_analysis_result:
        messages.warning(request, 'Both YouTube and Web analyses must be completed first!')
        return redirect('users:art_detail', pk=pk)

    # Check if overall analysis already exists
    if art.overall_analysis:
        messages.info(request, 'Overall analysis already exists!')
        return render(request, 'users/art_overall_analysis.html', {'art': art})

    try:
        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')

        # Create prompt for overall analysis with components
        prompt = f"""
        Analyze these two analyses about {art.analysis_query}:

        YouTube Analysis:
        {art.analysis_result}

        Web Analysis:
        {art.web_analysis_result}

        Provide a comprehensive response in this exact format:

        [SUMMARY]
        Synthesize the analyses into a cohesive summary that:
        1. Identifies key trends and patterns
        2. Highlights contradictions or confirmations
        3. Provides actionable insights
        4. Summarizes market sentiment

        [HOOKS]
        List 3-4 powerful hooks and CTAs specifically for {art.analysis_query}, each on a new line starting with •

        [SOLUTIONS]
        List 3-4 specific, actionable solutions tailored to {art.analysis_query}, each on a new line starting with •

        [TRENDS]
        List the top current and emerging trends, each on a new line starting with •

        [PAIN_POINTS]
        List key pain points and their solutions, each on a new line starting with •

        Format each section exactly as shown, with section headers in square brackets.
        """

        # Generate response
        response = model.generate_content(prompt)
        
        # Save the overall analysis
        art.overall_analysis = response.text
        art.save()
        
        messages.success(request, 'Overall analysis generated successfully!')
        return render(request, 'users/art_overall_analysis.html', {'art': art})
    except Exception as e:
        messages.error(request, f'Error generating analysis: {str(e)}')
        return redirect('users:art_detail', pk=pk)

@login_required
@require_POST
def art_analytics(request, pk):
    art = get_object_or_404(ART, pk=pk, user=request.user)
    
    try:
        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')

        # Create prompt for numerical analysis
        prompt = f"""
        Based on these analyses about {art.analysis_query}:

        YouTube Analysis:
        {art.analysis_result}

        Web Analysis:
        {art.web_analysis_result}

        Extract and provide ONLY numerical data in this exact JSON format:
        {{
            "sentiment": {{
                "positive": <number>,
                "negative": <number>,
                "neutral": <number>
            }},
            "painPoints": {{
                "point1": {{"text": "<extracted_point>", "count": <number>}},
                "point2": {{"text": "<extracted_point>", "count": <number>}},
                "point3": {{"text": "<extracted_point>", "count": <number>}}
            }},
            "contentFormats": {{
                "<format1>": <number>,
                "<format2>": <number>,
                "<format3>": <number>
            }}
        }}

        Rules:
        1. All sentiment percentages must sum to 100
        2. Pain point counts should be real numbers found in the analysis
        3. Content format percentages must sum to 100
        4. Use actual text from the analysis for pain points and formats
        5. Return ONLY the JSON, no other text
        """

        # Generate response
        response = model.generate_content(prompt)
        
        try:
            import json
            analytics_data = json.loads(response.text)
            
            # Validate structure
            required_keys = ['sentiment', 'painPoints', 'contentFormats']
            if not all(key in analytics_data for key in required_keys):
                raise ValueError("Missing required keys in response")
            
            # Normalize sentiment percentages
            sentiment_sum = sum(analytics_data['sentiment'].values())
            if sentiment_sum != 100:
                factor = 100 / sentiment_sum
                analytics_data['sentiment'] = {
                    k: round(v * factor) for k, v in analytics_data['sentiment'].items()
                }
            
            # Normalize content format percentages
            format_sum = sum(analytics_data['contentFormats'].values())
            if format_sum != 100:
                factor = 100 / format_sum
                analytics_data['contentFormats'] = {
                    k: round(v * factor) for k, v in analytics_data['contentFormats'].items()
                }
            
            return JsonResponse(analytics_data)
            
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {str(e)}\nResponse text: {response.text}")
            return JsonResponse({'error': 'Invalid response format'}, status=400)
        
    except Exception as e:
        logging.error(f"Analytics generation error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
