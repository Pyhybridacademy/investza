"""
support/models.py
Chat session between a user and support (admin).
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class ChatSession(models.Model):
    STATUS_OPEN   = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN,   'Open'),
        (STATUS_CLOSED, 'Closed'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Unread counts
    unread_by_admin = models.PositiveIntegerField(default=0)
    unread_by_user  = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Chat #{str(self.id)[:8]} — {self.user.get_full_name()} [{self.status}]'

    @property
    def last_message(self):
        return self.messages.order_by('-created_at').first()

    def get_or_create_open(user):
        """Return the user's existing open session or create a fresh one."""
        session = ChatSession.objects.filter(
            user=user, status=ChatSession.STATUS_OPEN
        ).first()
        if not session:
            session = ChatSession.objects.create(user=user)
        return session


class ChatMessage(models.Model):
    SENDER_USER  = 'user'
    SENDER_ADMIN = 'admin'
    SENDER_CHOICES = [
        (SENDER_USER,  'User'),
        (SENDER_ADMIN, 'Admin'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session    = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name='messages'
    )
    sender     = models.CharField(max_length=10, choices=SENDER_CHOICES)
    body       = models.TextField(max_length=2000)
    created_at = models.DateTimeField(default=timezone.now)
    read       = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.sender}] {self.body[:60]}'
