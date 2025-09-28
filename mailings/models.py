from django.db.models import CASCADE

from django.db import models

from config import settings


class Client(models.Model):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    comment = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='clients_as_owner')

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = 'получатель рассылки'
        verbose_name_plural = 'получатели рассылки'
        ordering = ['email',]
        permissions = [
            ("can_view_all_clients", "Может просматривать всех получателей"),
        ]


class Message(models.Model):
    subject = models.CharField(max_length=255)
    body = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='messages_as_owner')

    def __str__(self):
        return self.subject

    class Meta:
        verbose_name = 'сообщение'
        verbose_name_plural = 'сообщения'
        ordering = ['subject',]
        permissions = [
            ("can_view_all_messages", "Может просматривать все сообщения"),
        ]


class Mailing(models.Model):
    STATUS_CHOICES = [
        ('Создана', 'Создана'),
        ('Запущена', 'Запущена'),
        ('Завершена', 'Завершена'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mailings_as_user',
                             null=False)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True,)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Создана')
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    client = models.ManyToManyField(Client)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='mailings_as_owner',
                              null=False)

    def __str__(self):
        return f"Рассылка #{self.id} ({self.status})"  # По умолчанию Primary Key

    class Meta:
        verbose_name = 'рассылка'
        verbose_name_plural = 'рассылки'
        ordering = ['end_time',]
        permissions = [
            ("can_view_all_mailings", "Может просматривать все рассылки"),
        ]

    def save(self, *args, **kwargs):
        if self.status == 'Завершена' and self.end_time is None:
            from django.utils.timezone import now
            self.end_time = now()
        super().save(*args, **kwargs)


class MailingAttempt(models.Model):
    mailing = models.ForeignKey(Mailing, on_delete=models.CASCADE)
    attempt_time = models.DateTimeField(auto_now_add=True)
    status = models.BooleanField(default=False, verbose_name='успешно ли')
    server_response = models.TextField()

    def __str__(self):
        return f"{self.mailing} - {'Успешно' if self.status else 'Не успешно'}"

    class Meta:
        verbose_name = 'попытка рассылки'
        verbose_name_plural = 'попытки рассылки'
        ordering = ['-attempt_time']
