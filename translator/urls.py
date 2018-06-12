"""translator URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from .views import *

urlpatterns = [
    path(r'', TemplateView.as_view(template_name='index.html'), name='index'),
    path(r'translate', translate_page, name='translate_page'),
    path(r'translation/translate', translate_text, name='translate_text'),
    path(r'translation/rate', rate_translation, name='rate'),
    path(r'translation/submit', submit_translation, name='submit'),
    path(r'vocabulary', vocabulary, name='vocabulary'),
    path(r'settings', settings, name='settings'),
    path(r'send_verification_email', send_verification_email, name='send_verification_email'),
    path(r'login', login, name='login'),
    path(r'logout', logout, name='logout'),
    path(r'register', register, name='register'),
    path(r'upload_avatar', upload_avatar, name='upload_avatar'),
    path(r'reset_request', reset_request, name='reset_request'),
    path(r'reset', reset_password, name='reset'),
    path(r'verify_email', verify_email, name='verify_email'),
    path(r'add_word', add_to_vocabulary, name='add_word'),
    path(r'delete_word', delete_vocabulary, name='delete_word'),
    path(r'translate_index', translate_index, name='translate_index'),
    path(r'post', post_text, name='post'),
    path(r'save', save_passage, name='save'),
    path(r'set_language', set_language, name='set_language'),

]
