import re
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
from dotenv import load_dotenv
from pytube import YouTube
import os
import assemblyai as aai
import openai
from .models import BlogPost
import yt_dlp
import uuid
import os

load_dotenv()

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        # get yt title
        title = yt_title(yt_link)
        if not title:
            return JsonResponse({'error': 'Failed to fetch YouTube title. The link may be invalid or the video is restricted.'}, status=400)

        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': "Failed to get transcript. Could not download audio or transcribe."}, status=500)

        # use OpenAI to generate the blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error': "Failed to generate blog article"}, status=500)

        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        # return blog article as a response
        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

import yt_dlp

def yt_title(link):
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(link, download=False)
            return info.get('title', None)
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return None
    
def download_audio(link, output_path):
    """
    Download the audio from a YouTube video using yt-dlp, save as mp3, and return the file path.
    """
    

    # Generate a unique filename to avoid conflicts
    unique_id = uuid.uuid4().hex
    output_template = os.path.join(output_path, f"{unique_id}.%(ext)s")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            audio_path = output_template.replace('%(ext)s', 'mp3')
            if os.path.exists(audio_path):
                return audio_path
            # Sometimes yt-dlp returns another name, so use info
            downloaded_file = ydl.prepare_filename(info)
            base, ext = os.path.splitext(downloaded_file)
            new_file = base + '.mp3'
            if os.path.exists(new_file):
                return new_file
        return None
    except Exception as e:
        print(f"Error downloading YouTube audio with yt-dlp: {e}")
        return None

def get_transcription(link):
    audio_file = download_audio(link, settings.MEDIA_ROOT)
    if not audio_file:
        return None  # Ensure you handle download failure

    aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    return transcript.text if transcript and hasattr(transcript, "text") else None

def generate_blog_from_transcription(transcription):
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY")

    prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article:\n\n{transcription}\n\nArticle:"

    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",  # or "gpt-4" if you have access
        messages=[
            {"role": "system", "content": "You are a helpful assistant that writes blog articles."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1000,
        temperature=0.7,
    )

    generated_content = response.choices[0].message.content.strip()
    return generated_content

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message': error_message})

    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')