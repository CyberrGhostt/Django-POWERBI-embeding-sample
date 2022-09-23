from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from .models import * # PbiEmbedService, app_config
import json
# Create your views here.

# user = None

def home(request):
    return render(request, 'embedpbi/index.html')

def signup(request):

    if request.method == "POST":
        username = request.POST['username']
        fname = request.POST['fname']
        lname = request.POST['lname']
        email = request.POST['email']
        pass1 = request.POST['pass1']
        pass2 = request.POST['pass2']

        if User.objects.filter(username=username):
            messages.error(request, "Username already exists!")
            return redirect('home')

        # if User.objects.filter(email=email):
        #     messages.error(request, "Email already registered")
        #     return redirect('home')

        if len(username)> 10:
            messages.error(request, "Username must be less than 10 characters")
            return redirect('home')

        if pass1 != pass2 :
            messages.error(request, "Passwords didnt match!")
            return redirect('home')

        if not username.isalnum():
            messages.error(request, "Username must be alpha-numeric")
            return redirect('home')

        myuser = User.objects.create_user(username, email, pass1)
        myuser.first_name = fname
        myuser.last_name = lname

        myuser.save()

        messages.success(request, "Your account has been successfully created!")

        return redirect('signin')

    return render(request, 'embedpbi/signup.html')

def signin(request):

    if request.method == "POST":
        username = request.POST['username']
        pass1 = request.POST['pass1']

        user = authenticate(username=username, password=pass1)

        if user is not None:
            login(request, user)
            fname = user.first_name

            # return render(request, 'embedpbi/index.html', {'fname': fname})
            return redirect('report')
        else:
            messages.error(request, "Bad Credentials")
            return redirect('home')

    return render(request, 'embedpbi/signin.html')

def signout(request):
    logout(request)
    messages.success(request, "Logout successfully")
    return redirect('home')

def see_report(request):
    if request.user.is_authenticated:


        identities = [
            {'username': request.user.username, "roles": ["Regions"], 'datasets': app_config.DATASET_IDS}
        ]

        pbi_service = PbiEmbedService()
        response_get_embed_params_for_single_report = pbi_service.get_embed_params_for_single_report(workspace_id = app_config.WORKSPACE_ID,report_id = app_config.REPORT_ID, identities=identities)


        response_get_embed_params_for_single_report = json.loads(response_get_embed_params_for_single_report)

        reportConfig = response_get_embed_params_for_single_report['reportConfig'][0].copy()

        tokens ={
                    'tokenId': response_get_embed_params_for_single_report['tokenId'],
                    'accessToken': response_get_embed_params_for_single_report['accessToken'],
                    'tokenExpiry': response_get_embed_params_for_single_report['tokenExpiry'],
                }

        reportConfig.update(tokens)

        # print('Here u are :    ', response_get_embed_params_for_single_report)


        return render(request, 'embedpbi/embedreport.html', reportConfig)

    return redirect('home')
