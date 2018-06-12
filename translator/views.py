# -*- coding: utf-8 -*-

from django.shortcuts import render
from translator.utils import get_json, error_response, success
from translator.errors import ErrorEnum
from django.http import HttpRequest, HttpResponse
from translator.models import *
from django.db.models import F, Value, Q
import urllib.request
import urllib.parse
from django.shortcuts import redirect, reverse
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as django_login, logout as django_logout
import hashlib
import base64
import random
from readability import Document
from django.utils import translation
from django.http import HttpResponseRedirect
from django.conf import settings as django_settings
import re
import json
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.mail import send_mail


@login_required
def translate_page(request: HttpRequest):
    """
    翻译页面，可以使用url或file_id参数
    :param request:
    :return:
    """
    url = request.GET.get('url')
    file_id = request.GET.get('file_id')
    if url:  # 如果提供了url
        if 'http' not in url:
            url = 'http://' + url
        try:
            # 获取网页
            f = urllib.request.urlopen(url)
            text = f.read().decode()
            article = Document(text)
            article.content()
            # 抽取文本
            html = article.get_clean_html()
            # 计算hash
            m = hashlib.md5()
            m.update(html.encode('utf-8'))
            hashed = m.hexdigest()
            try:  # 如果该用户相同的文本已经存在，读取并返回
                p = UserPreference.objects.get(hashed=hashed, user=request.user)
            except UserPreference.DoesNotExist:
                p = UserPreference(user=request.user, original=text, trans=text, hashed=hashed)
                p.save()
            text = base64.b64encode(p.trans.encode('utf-8')).decode()
            return render(request, 'translate.html', context={'text': text, 'hashed': hashed, 'inc': p.inc})
        except Exception:
            return redirect('/translate_index?message=' + _("Cannot open url"))
    elif file_id:
        try:
            p = UserPreference.objects.get(pk=file_id)
            text = base64.b64encode(p.trans.encode('utf-8')).decode()
            return render(request, 'translate.html', context={'text': text, 'hashed': p.hashed, 'inc': p.inc})
        except UserPreference.DoesNotExist:
            pass
    return redirect('/')


@login_required
def translate_text(request: HttpRequest):
    """
    翻译文本，返回对应的翻译和用户的翻译列表
    :param request:
    :return:
    """
    if not request.user.is_authenticated:
        return error_response(ErrorEnum.NOT_LOGGED_IN)
    text = get_json(request, 'text')
    if is_english_now():
        if not contain_zh(text):
            return error_response(ErrorEnum.INVALID_TEXT)
    else:
        if contain_zh(text):
            return error_response(ErrorEnum.INVALID_TEXT)

    translations = UserTranslation.objects.filter(Q(original_text=text) & ~Q(user=request.user)).order_by(
        F('dislikes') - F('likes'))  # 按照评分降序排序。评分=赞数-踩数
    baidu_trans = translate_baidu(text, to_lang='en' if is_english_now() else 'zh')
    try:  # 检测是否在生词本中，如果是，查询次数+1
        vocab = Vocabulary.objects.get(user=request.user, word=text)
        vocab.count += 1
        vocab.save()
        in_vocab = True
    except Vocabulary.DoesNotExist:
        in_vocab = False
    return success({'text': baidu_trans['trans_result'][0]['dst'], 'users': [x.to_dict() for x in translations],
                    'in_vocab': in_vocab})


@login_required
def post_text(request: HttpRequest):
    """
    提交文本文件
    :param request:
    :return:
    """
    file = request.FILES.get('file')
    text = file.read()
    m = hashlib.md5()
    m.update(text)
    hashed = m.hexdigest()
    text = text.decode('utf-8')
    try:
        p = UserPreference.objects.get(hashed=hashed)
    except UserPreference.DoesNotExist:
        p = UserPreference(user=request.user, original=text, trans=text, hashed=hashed)
        p.save()
    return success({'file_id': p.hashed})


@login_required
def rate_translation(request: HttpRequest):
    """
    评价某条其他用户的翻译
    :param request:
    :return:
    """
    tid = get_json(request, 'id')
    liked = get_json(request, 'liked')
    try:
        translation = UserTranslation.objects.get(pk=tid)
    except UserTranslation.DoesNotExist:
        return error_response(ErrorEnum.NOT_FOUND)
    if liked:
        translation.likes = F('likes') + 1
    else:
        translation.dislikes = F('dislikes') + 1
    translation.save()
    translation.refresh_from_db()
    return success({'likes': translation.likes, 'dislikes': translation.dislikes})


@login_required
def submit_translation(request: HttpRequest):
    """
    提交自己的翻译
    :param request:
    :return:
    """
    original = get_json(request, 'text')
    translated = get_json(request, 'translated')
    UserTranslation(user_id='harold', trans_text=translated, original_text=original).save()
    return success()


@login_required
def vocabulary(request: HttpRequest):
    """
    生词表列表页面
    :param request:
    :return:
    """
    page = request.GET.get('page') or 1
    sort = request.GET.get('sort')
    if sort not in ('time', 'word', 'count'):
        sort = 'time'  # 默认按照时间排序
    asc = request.GET.get('asc')
    if asc is None:  # 默认降序排序
        asc = False
    else:
        asc = True

    vocab_list = Vocabulary.objects.all().order_by(('' if asc else '-') + sort)
    paginator = Paginator(vocab_list, 10)
    try:
        vocab_list = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        vocab_list = paginator.page(1)
    return render(request, template_name='vocabulary.html',
                  context={'vocab_list': vocab_list, 'page_count': paginator.num_pages, 'current_page': page,
                           'sort': sort, 'asc': asc})


@login_required
def settings(request: HttpRequest):
    """
    个人设置页面
    :param request:
    :return:
    """
    if request.method == 'GET':
        return render(request, template_name='settings.html')
    else:  # 如果是POST，修改email或者密码
        email = request.POST.get('email')
        if email and email != request.user.email:
            request.user.email = email
            request.user.email_verified = False
            request.user.save()
            return send_verification_email(request)
        elif email and email.strip() == '':
            return redirect('settings')
        old_password = request.POST.get('old_pwd')
        new_password = request.POST.get('new_pwd')
        confirm = request.POST.get('confirm')
        error = None
        if old_password:
            if not request.user.check_password(old_password):
                error = _("Wrong password")
            if new_password and confirm:
                if new_password != confirm:
                    error = _("Passwords are not the same")
                else:
                    request.user.set_password(new_password)
                    request.user.save()
                    django_logout(request)
                    return redirect('login')
        return render(request, template_name='settings.html', context={'error': error})


def login(request: HttpRequest):
    """
    登陆页面
    :param request:
    :return:
    """
    if request.method == 'POST':
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        if not username_or_email or not password:
            return redirect('login')
        try:
            user = User.objects.get(Q(username=username_or_email) | Q(email=username_or_email))
            if not user.check_password(password):
                return render(request, template_name='login.html',
                              context={'error': _("Wrong password"), 'username': username_or_email})
            django_login(request, user)
            return redirect(request.GET.get('next') or '/')
        except User.DoesNotExist:
            return render(request, template_name='login.html',
                          context={'error': _("User not found"), 'username': username_or_email})
    else:
        return render(request, template_name='login.html')


def logout(request: HttpRequest):
    """
    注销
    :param request:
    :return:
    """
    if request.user.is_authenticated:
        django_logout(request)
    return redirect('/')


def register(request: HttpRequest):
    """
    注册
    :param request:
    :return:
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm = request.POST.get('confirm')

        if not username or not password or not confirm or not email:
            return redirect('register')

        if password != confirm:
            return render(request, template_name='register.html',
                          context={'error': _("Passwords are not the same"), 'username': username, 'email': email})
        try:
            User.objects.get(Q(username=username) | Q(email=email))
            return render(request, template_name='register.html',
                          context={'error': _("Username or email already exists"), 'username': username,
                                   'email': email})
        except User.DoesNotExist:
            pass
        user = User(username=username, email=email)
        user.set_password(password)
        user.save()
        return redirect('login')
    else:
        return render(request, template_name='register.html')


@login_required
def upload_avatar(request: HttpRequest):
    """
    上传头像
    :param request:
    :return:
    """
    file = request.FILES.get('file')
    user = request.user
    request.user.avatar.save(user.username + '.jpg', file)
    return success()


def verify_email(request: HttpRequest):
    """
    验证邮箱链接
    :param request:
    :return:
    """
    token = request.GET.get('token')
    if token:
        result = User.decode_token(token, email_verification=True)
        if result:
            return redirect('/?message=' + _('Email Verified!'))
    return redirect('/?message=' + _('Invalid Link'))


def reset_request(request: HttpRequest):
    """
    忘记密码页面
    :param request:
    :return:
    """
    if request.method == 'GET':
        return render(request, template_name='reset_request.html')
    else:
        email = request.POST.get('email')
        if not email:
            return render(request, template_name='reset_request.html')
        try:
            user = User.objects.get(email=email)
            if not user.email_verified:
                return render(request, template_name='reset_request.html',
                              context={'error': _("Email not verified. Please contact admin.")})

            user.reset_pending = True
            user.save()
            _send_reset_email(user)
            return redirect('/?message=' + _(
                "A reset email has been sent to %(email)s. Please click the link in it to reset your password.") % {
                                'email': user.email})
        except User.DoesNotExist:
            return render(request, template_name='reset_request.html', context={'error': _("User not found")})


def reset_password(request: HttpRequest):
    """
    验证重置密码
    :param request:
    :return:
    """
    if request.method == 'GET':
        token = request.GET.get('token')
        if token:
            result = User.decode_token(token, email_verification=False)
            if result:
                return render(request, template_name='reset_password.html', context={'token': token})
        return redirect('/?message=' + _('Invalid Link'))
    else:
        token = request.POST.get('token')
        if token:
            user = User.decode_token(token, email_verification=False)
            if user:
                new_pwd = request.POST.get('new_pwd')
                confirm = request.POST.get('confirm')
                if not new_pwd or not confirm:
                    return render(request, template_name='reset_password.html', context={'token': token})
                if new_pwd != confirm:
                    return render(request, template_name='reset_password.html',
                                  context={'token': token, 'error': _("Passwords are not the same")})
                user.set_password(new_pwd)
                user.reset_pending = False
                user.save()
                return redirect('/login?message=' + _('Password reset!'))
        return redirect('/?message=' + _('Invalid Link'))


def add_to_vocabulary(request: HttpRequest):
    """
    添加生词
    :param request:
    :return:
    """
    if not request.user.is_authenticated:
        return error_response(ErrorEnum.NOT_LOGGED_IN)
    word = get_json(request, 'word')
    trans = get_json(request, 'trans')
    if Vocabulary.objects.filter(user=request.user, word=word).count() == 0:
        Vocabulary(user=request.user, word=word, trans=trans).save()
    return success()


def delete_vocabulary(request: HttpRequest):
    """
    删除生词
    :param request:
    :return:
    """
    if not request.user.is_authenticated:
        return error_response(ErrorEnum.NOT_LOGGED_IN)
    vocab_id = get_json(request, 'vocab_id')
    Vocabulary.objects.filter(id=vocab_id).delete()
    return success()


def save_passage(request: HttpRequest):
    """
    保存用户当前文章的翻译
    :param request:
    :return:
    """
    if not request.user.is_authenticated:
        return error_response(ErrorEnum.NOT_LOGGED_IN)
    hashed = get_json(request, 'hashed')
    translated = get_json(request, 'translated')
    inc = get_json(request, 'inc')
    p = UserPreference.objects.get(hashed=hashed)
    if p.inc > inc:
        return success()
    p.trans = translated
    p.inc += 1
    p.save()
    return success()


@login_required
def translate_index(request: HttpRequest):
    return render(request, template_name='translate_index.html')


def translate_baidu(text, from_lang='auto', to_lang='zh'):
    api_url = 'http://api.fanyi.baidu.com/api/trans/vip/translate'
    q = text
    salt = random.randint(32768, 65536)
    sign = django_settings.BAIDU_API_APPID + q + str(salt) + django_settings.BAIDU_API_KEY
    m1 = hashlib.md5()
    m1.update(sign.encode('utf-8'))
    sign = m1.hexdigest()
    api_url = api_url + '?appid=' + django_settings.BAIDU_API_APPID + '&q=' + urllib.request.quote(
        q) + '&from=' + from_lang + '&to=' + to_lang + '&salt=' + str(salt) + '&sign=' + sign
    r = urllib.request.urlopen(api_url)
    return json.loads(r.read())


def set_language(request: HttpRequest):
    """
    设置语言
    :param request:
    :return:
    """
    lang = request.GET.get('lang', translation.get_language())
    if translation.check_for_language(lang):
        translation.activate(lang)
        next_page_url = request.GET.get('next', reverse('index'))
        response = HttpResponseRedirect(next_page_url)
        response.set_cookie(django_settings.LANGUAGE_COOKIE_NAME, lang)
        return response


def is_english_now():
    """
    判断当前用户语言是否是英文
    :return:
    """
    return translation.get_language() == 'en-us'


zh_pattern = re.compile(u'[\u4e00-\u9fa5]+')


def contain_zh(word):
    """
    检测某个文本是否包含中文
    :param word:
    :return:
    """
    match = zh_pattern.search(word)
    return match


@login_required
def send_verification_email(request: HttpRequest):
    """
    发送验证邮件
    :param request:
    :return:
    """
    _send_verification_email(request.user)
    return redirect('/settings?message=' + _(
        'A verification email has been sent to %(email)s. Please click the link in it to verify your email.') % {
                        'email': request.user.email})


def _send_verification_email(user: User):
    link = django_settings.SITE_ROOT_URL + '/verify_email?token=' + user.generate_token()
    send_mail(_('Verify Your Email Address'),
              _('Click the link below to verify your email address.\n%(link)s') % {'link': link},
              django_settings.DEFAULT_FROM_EMAIL, [user.email]),


def _send_reset_email(user: User):
    link = django_settings.SITE_ROOT_URL + '/reset?token=' + user.generate_token()
    send_mail(_('Reset Your Password'),
              _('Click the link below to reset your password.\n%(link)s') % {'link': link},
              django_settings.DEFAULT_FROM_EMAIL, [user.email]),
