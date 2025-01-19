from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    return render(request, 'home.html')

def login_view(request):
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def landing(request):
    return render(request, 'landing.html') 