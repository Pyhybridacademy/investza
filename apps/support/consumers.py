"""
support/consumers.py  —  Real-time chat via Django Channels WebSockets.
"""
import json
import logging
from django.db import models as django_models
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


def _fmt(msg):
    return {
        'id':         str(msg.id),
        'sender':     msg.sender,
        'body':       msg.body,
        'created_at': msg.created_at.strftime('%H:%M'),
    }


class UserChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return
        session = await self._get_or_create_session(user)
        self.session_id = str(session.id)
        self.group_name = f'chat_session_{self.session_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        history = await self._get_history(self.session_id)
        await self.send(text_data=json.dumps({'type': 'history', 'messages': history}))
        await self._mark_admin_msgs_read(self.session_id)
        await self.channel_layer.group_send('admin_chat_inbox', {
            'type': 'session_update', 'session_id': self.session_id
        })

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or '{}')
        except json.JSONDecodeError:
            return
        body = (data.get('body') or '').strip()
        if not body:
            return
        msg = await self._save_message(self.session_id, 'user', body)
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat_message', 'message': _fmt(msg)
        })
        user_name = await self._get_user_name(self.session_id)
        await self.channel_layer.group_send('admin_chat_inbox', {
            'type': 'new_user_message',
            'session_id': self.session_id,
            'preview': body[:80],
            'user_name': user_name,
        })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def session_closed(self, event):
        await self.send(text_data=json.dumps({'type': 'session_closed'}))

    @database_sync_to_async
    def _get_or_create_session(self, user):
        from apps.support.models import ChatSession
        return ChatSession.get_or_create_open(user)

    @database_sync_to_async
    def _get_history(self, session_id):
        from apps.support.models import ChatSession
        session = ChatSession.objects.get(id=session_id)
        return [_fmt(m) for m in session.messages.order_by('created_at')[:100]]

    @database_sync_to_async
    def _save_message(self, session_id, sender, body):
        from apps.support.models import ChatSession, ChatMessage
        session = ChatSession.objects.get(id=session_id)
        msg = ChatMessage.objects.create(session=session, sender=sender, body=body)
        ChatSession.objects.filter(id=session_id).update(
            unread_by_admin=django_models.F('unread_by_admin') + 1,
            updated_at=timezone.now(),
        )
        return msg

    @database_sync_to_async
    def _mark_admin_msgs_read(self, session_id):
        from apps.support.models import ChatSession, ChatMessage
        ChatMessage.objects.filter(
            session_id=session_id, sender='admin', read=False
        ).update(read=True)
        ChatSession.objects.filter(id=session_id).update(unread_by_user=0)

    @database_sync_to_async
    def _get_user_name(self, session_id):
        from apps.support.models import ChatSession
        session = ChatSession.objects.select_related('user').get(id=session_id)
        return session.user.get_full_name() or session.user.email


class AdminChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get('user')
        if not user or not (user.is_staff or user.is_superuser):
            await self.close()
            return
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f'chat_session_{self.session_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add('admin_chat_inbox', self.channel_name)
        await self.accept()
        history = await self._get_history(self.session_id)
        await self.send(text_data=json.dumps({'type': 'history', 'messages': history}))
        await self._mark_user_msgs_read(self.session_id)
        inbox = await self._get_inbox()
        await self.send(text_data=json.dumps({'type': 'inbox_snapshot', 'sessions': inbox}))

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            await self.channel_layer.group_discard('admin_chat_inbox', self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or '{}')
        except json.JSONDecodeError:
            return
        if data.get('action') == 'close_session':
            await self._close_session(self.session_id)
            await self.channel_layer.group_send(self.group_name, {'type': 'session_closed'})
            await self.channel_layer.group_send('admin_chat_inbox', {
                'type': 'session_update', 'session_id': self.session_id
            })
            return
        body = (data.get('body') or '').strip()
        if not body:
            return
        msg = await self._save_admin_message(self.session_id, body)
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat_message', 'message': _fmt(msg)
        })
        await self._trigger_user_push(self.session_id, body)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def session_closed(self, event):
        await self.send(text_data=json.dumps({'type': 'session_closed'}))

    async def session_update(self, event):
        inbox = await self._get_inbox()
        await self.send(text_data=json.dumps({'type': 'inbox_snapshot', 'sessions': inbox}))

    async def new_user_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_user_message',
            'session_id': event['session_id'],
            'preview': event['preview'],
            'user_name': event['user_name'],
        }))

    @database_sync_to_async
    def _get_history(self, session_id):
        from apps.support.models import ChatSession
        session = ChatSession.objects.get(id=session_id)
        return [_fmt(m) for m in session.messages.order_by('created_at')[:100]]

    @database_sync_to_async
    def _save_admin_message(self, session_id, body):
        from apps.support.models import ChatSession, ChatMessage
        session = ChatSession.objects.get(id=session_id)
        msg = ChatMessage.objects.create(session=session, sender='admin', body=body)
        ChatSession.objects.filter(id=session_id).update(
            unread_by_user=django_models.F('unread_by_user') + 1,
            updated_at=timezone.now(),
        )
        return msg

    @database_sync_to_async
    def _mark_user_msgs_read(self, session_id):
        from apps.support.models import ChatSession, ChatMessage
        ChatMessage.objects.filter(
            session_id=session_id, sender='user', read=False
        ).update(read=True)
        ChatSession.objects.filter(id=session_id).update(unread_by_admin=0)

    @database_sync_to_async
    def _close_session(self, session_id):
        from apps.support.models import ChatSession
        ChatSession.objects.filter(id=session_id).update(status='closed')

    @database_sync_to_async
    def _get_inbox(self):
        from apps.support.models import ChatSession
        sessions = ChatSession.objects.filter(
            status='open'
        ).select_related('user').order_by('-updated_at')[:30]
        result = []
        for s in sessions:
            last = s.messages.order_by('-created_at').first()
            result.append({
                'session_id':   str(s.id),
                'user_name':    s.user.get_full_name() or s.user.email,
                'user_email':   s.user.email,
                'unread':       s.unread_by_admin,
                'last_message': last.body[:60] if last else '',
                'last_time':    last.created_at.strftime('%H:%M') if last else '',
            })
        return result

    @database_sync_to_async
    def _trigger_user_push(self, session_id, message_body):
        try:
            import json as _json
            from apps.support.models import ChatSession
            from apps.notifications.models import PushSubscription
            from apps.notifications.views import _send_web_push, _GoneError
            session = ChatSession.objects.select_related('user').get(id=session_id)
            subs = PushSubscription.objects.filter(user=session.user, is_active=True)
            payload = _json.dumps({
                'title': 'InvestZA Support',
                'body':  f'Support replied: {message_body[:80]}',
                'url':   '/dashboard/',
                'icon':  '/static/icons/icon-192.svg',
            })
            dead = []
            for sub in subs:
                try:
                    _send_web_push(sub.endpoint, sub.p256dh, sub.auth, payload)
                except _GoneError:
                    dead.append(sub.endpoint)
                except Exception as e:
                    logger.warning('Push to user failed: %s', e)
            if dead:
                PushSubscription.objects.filter(endpoint__in=dead).update(is_active=False)
        except Exception as e:
            logger.warning('_trigger_user_push error: %s', e)


class AdminInboxConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get('user')
        if not user or not (user.is_staff or user.is_superuser):
            await self.close()
            return
        await self.channel_layer.group_add('admin_chat_inbox', self.channel_name)
        await self.accept()
        inbox = await self._get_inbox()
        await self.send(text_data=json.dumps({'type': 'inbox_snapshot', 'sessions': inbox}))

    async def disconnect(self, code):
        if hasattr(self, 'channel_name'):
            await self.channel_layer.group_discard('admin_chat_inbox', self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def session_update(self, event):
        inbox = await self._get_inbox()
        await self.send(text_data=json.dumps({'type': 'inbox_snapshot', 'sessions': inbox}))

    async def new_user_message(self, event):
        await self.send(text_data=json.dumps({
            'type':       'new_user_message',
            'session_id': event['session_id'],
            'preview':    event['preview'],
            'user_name':  event['user_name'],
        }))

    @database_sync_to_async
    def _get_inbox(self):
        from apps.support.models import ChatSession
        sessions = ChatSession.objects.filter(
            status='open'
        ).select_related('user').order_by('-updated_at')[:30]
        result = []
        for s in sessions:
            last = s.messages.order_by('-created_at').first()
            result.append({
                'session_id':   str(s.id),
                'user_name':    s.user.get_full_name() or s.user.email,
                'user_email':   s.user.email,
                'unread':       s.unread_by_admin,
                'last_message': last.body[:60] if last else '',
                'last_time':    last.created_at.strftime('%H:%M') if last else '',
            })
        return result
