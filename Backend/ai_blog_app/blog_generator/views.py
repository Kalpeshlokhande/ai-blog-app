import json
import os
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login,logout
from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from dotenv import load_dotenv
from pytube import YouTube
from django.conf import settings
import assemblyai as aai
import openai



load_dotenv()


@login_required
def index(request):
    return render(request,'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data=json.loads(request.body)
            yt_link=data['link']
            return JsonResponse({'content':yt_link})
        except (KeyError,json.JSONDecodeError):
            return JsonResponse({'error':"Invalid data sent"},status=400)
        
        # get the title
        title= yt_title(yt_link)


        # get transcript
        transcription=get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error':'Failed to get transcript'},status=500)
        
        # use OpenAI to generate the blog



        # save blog article to database

        # return blog artcle as response

    else:
        return JsonResponse({'error':"Invalid Request method"},status=405)


def yt_title(link):
    yt=YouTube(link)
    title=yt.title
    return title

def download_audio(link):
    yt=YouTube(link)
    video=yt.streams.filter(only_audio=True).first()
    out_file=video.download(output_path=settings.MEDIA_ROOT)
    base,ext =os.path.splittext(out_file)
    new_file=base+'.mp3'
    os.rename(out_file,new_file)
    return new_file

def get_transcription(link):
        audio_file=download_audio(link)
        aai.settings.api_key=os.getenv("ASSEMBLYAI_API_KEY")
        transcriber=aai.Transcriber()
        transcript=transcriber.transcribe(audio_file)
        return transcriber.text


def generate_blog_from_transcription(transcription):
        openai.api_key=os.getenv("OPENAI_API_KEY")
        prompt=f"Based on the following  transcript from a YouTube video, write a comprehensive blog article, write it based in the transcript,but dont make it look loke a youtube video,make it like a proper blog article:\n\n{ transcription}\n\nArticle:"
        response=openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_token=1000
        ) 
        generated_content=response.choices[0].text.strip()
        return generated_content




def user_login(request):
    if request.method =='POST':
        username=request.POST['username']
        password=request.POST['password']
        
        user=authenticate(request,username=username,password=password)
        if user is not None:
            login(request,user)
            return redirect('/')
        else:
            error_message="Invalid username or password"
            return render(request,'login.html',{error_message:error_message})
    return render(request,'login.html')

def user_signup(request):
    if request.method =='POST':
        username=request.POST['username']
        email=request.POST['email']
        password=request.POST['password']
        repeatPassword=request.POST['repeatPassword']
        if password == repeatPassword:
            try:
                user=User.objects.create_user(username,email,password)
                user.save()
                login(request,user)
                return redirect('/')
            except:
                error_message='Error creating account'
                return render(request,'signup.html',{'error_message':error_message})
        else:
            error_message='Password do not match'
            return render(request,'signup.html',{'error_message':error_message})
    return render(request,'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')