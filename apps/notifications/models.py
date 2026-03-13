"""
notifications/models.py
Stores browser push subscriptions and provisional messages sent by admin.
"""
import uuid
from django.db import models
from django.conf import settings


class PushSubscription(models.Model):
    """
    One row per browser/device that granted push permission.
    A single user can have multiple subscriptions (phone + laptop etc).
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
        null=True, blank=True,          # Allow anonymous subscriptions
    )
    endpoint     = models.TextField(unique=True)
    p256dh       = models.TextField()   # Public key
    auth         = models.TextField()   # Auth secret
    user_agent   = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    is_active    = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Push Subscription'
        verbose_name_plural = 'Push Subscriptions'

    def __str__(self):
        owner = self.user.get_full_name() if self.user else 'Anonymous'
        return f'{owner} — {self.endpoint[:60]}…'


class ProvisionalNotification(models.Model):
    """
    A push message composed by the admin and sent to all active subscribers.
    """
    STATUS_CHOICES = [
        ('DRAFT',   'Draft'),
        ('SENT',    'Sent'),
        ('FAILED',  'Failed'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title        = models.CharField(max_length=100)
    body         = models.TextField(max_length=500)
    url          = models.CharField(max_length=255, blank=True, default='/',
                                    help_text='URL to open when user taps the notification')
    icon         = models.CharField(max_length=255, blank=True,
                                    default='/static/icons/icon-192.svg')
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    sent_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sent_notifications',
    )
    sent_at      = models.DateTimeField(null=True, blank=True)
    total_sent   = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Provisional Notification'
        verbose_name_plural = 'Provisional Notifications'

    def __str__(self):
        return f'[{self.status}] {self.title}'
