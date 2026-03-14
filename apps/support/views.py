"""
support/views.py
HTTP views (session list, session detail for admin).
"""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

User = get_user_model()


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
def user_chat_view(request):
    """Page that bootstraps the user-side chat widget (used if JS is disabled)."""
    from apps.support.models import ChatSession
    session = ChatSession.get_or_create_open(request.user)
    return render(request, 'support/user_chat.html', {'session': session})


@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_chat_inbox(request):
    """Admin inbox — lists all open chat sessions."""
    from apps.support.models import ChatSession
    open_sessions   = ChatSession.objects.filter(status='open').select_related('user').order_by('-updated_at')
    closed_sessions = ChatSession.objects.filter(status='closed').select_related('user').order_by('-updated_at')[:20]
    return render(request, 'admin_panel/chat_inbox.html', {
        'open_sessions':   open_sessions,
        'closed_sessions': closed_sessions,
    })


@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_chat_session(request, session_id):
    """Admin chat room — real-time view of one session."""
    from apps.support.models import ChatSession
    session = get_object_or_404(ChatSession, id=session_id)
    return render(request, 'admin_panel/chat_session.html', {'session': session})


@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
@require_POST
def admin_close_session(request, session_id):
    from apps.support.models import ChatSession
    ChatSession.objects.filter(id=session_id).update(status='closed')
    return redirect('admin_chat_inbox')
