# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import AbstractUser
import os
from django.conf import settings
from itsdangerous import TimedJSONWebSignatureSerializer


class User(AbstractUser):
    username = models.CharField(max_length=255, primary_key=True)
    #头像
    avatar = models.ImageField(null=True, upload_to='static/avatars')
    #用户请求了重置密码，等待点击邮箱链接的时候为true
    reset_pending = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    @property
    def avatar_url(self):
        if not self.avatar or not self.avatar.name or not os.path.exists(
                os.path.join(settings.MEDIA_ROOT, self.avatar.name)):
            return 'avatars/default.png'
        return self.avatar.name

    def generate_token(self):
        s = TimedJSONWebSignatureSerializer('THISISVERYSECRET', expires_in=600)
        payload = {'username': self.username, 'email': self.email}
        return s.dumps(payload).decode()

    @staticmethod
    def decode_token(token, email_verification):
        s = TimedJSONWebSignatureSerializer('THISISVERYSECRET', expires_in=600)
        try:
            payload = s.loads(token)
            username = payload['username']
            try:
                user = User.objects.get(username=username)
                if email_verification:
                    if user.email_verified:
                        return False
                    if payload['email'] != user.email:
                        return False
                    user.email_verified = True
                    user.save()
                    return True
                else:
                    if user.reset_pending:
                        return user
            except User.DoesNotExist:
                return False
        except Exception:
            return False


class UserTranslation(models.Model):
    class Meta:
        indexes = [models.Index(fields=['original_text']), models.Index(fields=['user'])]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    original_text = models.TextField()
    trans_text = models.TextField()
    likes = models.IntegerField(default=0)
    dislikes = models.IntegerField(default=0)
    time = models.DateTimeField(auto_now_add=True)

    def to_dict(self):
        return {'username': self.user_id, 'translation': self.trans_text, 'likes': self.likes,
                'dislikes': self.dislikes, 'id': self.pk, 'avatar_url': self.user.avatar_url,
                'time': self.time.strftime('%Y-%m-%d')}


class UserPreference(models.Model):
    class Meta:
        indexes = [models.Index(fields=['hashed'])]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hashed = models.CharField(max_length=255, primary_key=True)
    original = models.TextField()
    trans = models.TextField()
    inc = models.IntegerField(default=0)


class Vocabulary(models.Model):
    class Meta:
        indexes = [models.Index(fields=['word']), models.Index(fields=['user'])]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word = models.CharField(max_length=255)
    trans = models.CharField(max_length=255)
    time = models.DateTimeField(auto_now_add=True)
    count = models.IntegerField(default=1)
