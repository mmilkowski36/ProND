# TODO - delete session as host

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.formats import date_format
from django.db import transaction
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.urls import reverse
from accounts.models import Skill, PrivateMessage, SessionRequest
from .models import Session, SessionMembership, SessionMessage
from .forms import SessionForm, SessionMessageForm, SessionMessageEditForm


def notify_members_of_cancellation(session, reason):
    """
    Creates 1 PrivateMessage per member of the session (except host), sent from 
    host. Returns the number of notifications created. Snapshots session title and local date/time so
    msg survive hard-delete

    Must wrap in atomic transaction 

    """
    local_dt = timezone.localtime(session.date_time)
    when = date_format(local_dt, "M j, Y \\a\\t g:i A")
    title = session.title
    base = f'INFO: Session "{title}" ({when}) has been cancelled by the host.'
    if reason:
        body = f"{base} Reason: {reason}"
    else:
        body = base

    members = session.memberships.select_related('user').exclude(user=session.host)
    count = 0
    for membership in members:
        PrivateMessage.objects.create(
            sender=session.host,
            receiver=membership.user,
            content=body,
        )
        count += 1
    return count


@login_required
def session_list(request): # main page - list all sessions for calendar + list view
    now = timezone.now()
    all_sessions = (
        Session.objects
        .filter(is_cancelled=False)
        .order_by('date_time')
        .select_related('skill', 'host')
    )
    sessions = all_sessions.filter(date_time__gte=now)

    # session IDs the current user has joined - one query
    joined_ids = set(
        SessionMembership.objects.filter(
            user=request.user
        ).values_list('session_id', flat=True)
    )

    # build calendar event list with status for each session
    calendar_events = []
    for session in all_sessions:
        if session.date_time < now:
            status = 'past'
        elif session.host == request.user:
            status = 'hosting'
        elif session.pk in joined_ids:
            status = 'joined'
        else:
            status = 'open'

        calendar_events.append({
            'title': session.title,
            'start': session.date_time.isoformat(),
            'url': reverse('session_detail', args=[session.pk]),
            'status': status,
        })

    return render(request, 'sessions/session_list.html', {
        'sessions': sessions,
        'calendar_events': calendar_events,
        'page_title': 'Upcoming Sessions',
        'show_calendar': True,
        'empty_message': 'No upcoming sessions.',
    })


@login_required
def sharer_session_list(request, user_id):
    sharer = get_object_or_404(User, id=user_id)
    sessions = (
        Session.objects
        .filter(
            host=sharer,
            is_cancelled=False,
            date_time__gte=timezone.now(),
        )
        .order_by('date_time')
        .select_related('skill', 'host')
    )

    return render(request, 'sessions/session_list.html', {
        'sessions': sessions,
        'calendar_events': [],
        'page_title': f'Upcoming Sessions with {sharer.get_full_name() or sharer.username}',
        'show_calendar': False,
        'sharer': sharer,
        'empty_message': f'{sharer.get_full_name() or sharer.username} has no upcoming sessions right now.',
    })


@login_required
def session_create(request): # create own session page - select own skill from dropdown, fill in attributes. requires 1+ skill to exist with Profile (add ability to create on the spot?)
    user_skills = Skill.objects.filter(owner=request.user)
    if not user_skills.exists():
        messages.warning(request, 'You must add a Skill before creating a Session.')
        return redirect('profile_edit')

    # Resolve a linked sr (from inbox Accept link)
    # If from a request
    sr = None
    from_request_id = request.POST.get('from_request') or request.GET.get('from_request')
    if from_request_id:
        sr = get_object_or_404(SessionRequest, id=from_request_id, skill__owner=request.user)

    if request.method == 'POST':
        form = SessionForm(request.POST)
        form.fields['skill'].queryset = user_skills
        if form.is_valid():
            session = form.save(commit=False)
            session.host = request.user
            session.save()
            if sr:
                sr.status = SessionRequest.STATUS_ACCEPTED
                sr.save()
                PrivateMessage.objects.create(
                    sender=request.user,
                    receiver=sr.requester,
                    content=(
                        f'Your session request for "{sr.skill.name}" was accepted! '
                        f'"{session.title}" is scheduled for {session.date_time.strftime("%b %d, %Y at %I:%M %p")} '
                        f'at {session.location}. Find it on the Sessions page and join. '
                        'If you cannot make the new appointment, please message me here so I can cancel it!'
                    )
                )
            messages.success(request, f'Session "{session.title}" created.')
            return redirect('session_detail', pk=session.pk)
    else:
        initial = {}
        if sr:
            if sr.skill:
                initial['skill'] = sr.skill
            if sr.proposed_title:
                initial['title'] = sr.proposed_title
            if sr.proposed_date_time:
                initial['date_time'] = sr.proposed_date_time
            if sr.proposed_duration_minutes:
                initial['duration_minutes'] = sr.proposed_duration_minutes
            if sr.proposed_location:
                initial['location'] = sr.proposed_location
            if sr.proposed_capacity:
                initial['capacity'] = sr.proposed_capacity
        form = SessionForm(initial=initial)
        form.fields['skill'].queryset = user_skills

    return render(request, 'sessions/session_create.html', {'form': form, 'sr': sr})


@login_required
def session_detail(request, pk): # view session details. conditional buttons based on host/member/joinable
    session = get_object_or_404(
        Session.objects.select_related('skill', 'host'),
        pk=pk
    )
    if session.is_cancelled:
        return render(
            request,
            'sessions/session_cancelled.html',
            {'session_title': session.title},
            status=410,
        )
    memberships = session.memberships.select_related('user')
    session_messages = session.messages.select_related('author')
    membership_count = memberships.count()

    is_host = request.user == session.host
    is_member = memberships.filter(user=request.user).exists()
    is_full = membership_count >= session.capacity
    is_past = session.date_time < timezone.now()
    can_access_chat = session.user_can_access_chat(request.user)

    message_form = None
    if can_access_chat:
        message_form = SessionMessageForm()
        if not session.user_can_post_announcement(request.user):
            message_form.fields['is_announcement'].widget = message_form.fields['is_announcement'].hidden_widget()

    return render(request, 'sessions/session_detail.html', {
        'session': session,
        'memberships': memberships,
        'session_messages': session_messages,
        'membership_count': membership_count,
        'is_host': is_host,
        'is_member': is_member,
        'is_full': is_full,
        'is_past': is_past,
        'can_access_chat': can_access_chat,
        'message_form': message_form,
    })


@login_required
def session_join(request, pk): # POST only - join session if not host, not already joined, not full, current
    session = get_object_or_404(Session, pk=pk)

    if request.method != 'POST':
        return redirect('session_detail', pk=pk)

    if session.is_cancelled:
        messages.error(request, 'This session has been cancelled.')
        return redirect('session_list')

    if request.user == session.host:
        messages.error(request, 'You cannot join your own session.')
        return redirect('session_detail', pk=pk)

    if session.date_time < timezone.now():
        messages.error(request, 'This session has already passed.')
        return redirect('session_detail', pk=pk)

    with transaction.atomic():
        membership_count = session.memberships.count()
        if membership_count >= session.capacity:
            messages.error(request, 'This session is full.')
            return redirect('session_detail', pk=pk)

        if session.memberships.filter(user=request.user).exists():
            messages.info(request, 'You are already a member of this session.')
            return redirect('session_detail', pk=pk)

        SessionMembership.objects.create(session=session, user=request.user)

    messages.success(request, f'You joined "{session.title}".')
    return redirect('session_detail', pk=pk)


@login_required
def session_leave(request, pk): # POST only - leave session as member
    session = get_object_or_404(Session, pk=pk)

    if request.method != 'POST':
        return redirect('session_detail', pk=pk)

    if session.is_cancelled:
        messages.error(request, 'This session has been cancelled.')
        return redirect('session_list')

    membership = session.memberships.filter(user=request.user).first()
    if membership:
        membership.delete()
        messages.success(request, f'You left "{session.title}".')
    else:
        messages.info(request, 'You are not a member of this session.')

    return redirect('session_detail', pk=pk)


@login_required
def session_message_create(request, pk):
    session = get_object_or_404(Session.objects.select_related('host'), pk=pk)

    if request.method != 'POST':
        return redirect('session_detail', pk=pk)

    if session.is_cancelled:
        messages.error(request, 'This session has been cancelled.')
        return redirect('session_list')

    if not session.user_can_access_chat(request.user):
        messages.error(request, 'Join this session before using the chat.')
        return redirect('session_detail', pk=pk)

    form = SessionMessageForm(request.POST)
    if not session.user_can_post_announcement(request.user):
        form.data = form.data.copy()
        form.data['is_announcement'] = ''

    if form.is_valid():
        session_message = form.save(commit=False)
        session_message.session = session
        session_message.author = request.user
        session_message.save()
        if session_message.is_announcement:
            messages.success(request, 'Announcement posted.')
        else:
            messages.success(request, 'Message sent.')
    else:
        errors = ' '.join(form.errors.get('content', [])) or 'Please enter a valid message.'
        messages.error(request, errors)

    return redirect('session_detail', pk=pk)


@login_required
def session_message_edit(request, pk, message_id):
    session_message = get_object_or_404(
        SessionMessage.objects.select_related('session', 'session__host', 'author'),
        pk=message_id,
        session_id=pk,
    )

    if session_message.session.is_cancelled:
        messages.error(request, 'This session has been cancelled.')
        return redirect('session_list')

    if not session_message.user_can_manage(request.user):
        return HttpResponseForbidden('You can only edit your own messages.')

    if request.method == 'POST':
        form = SessionMessageEditForm(request.POST, instance=session_message)
        if not session_message.session.user_can_post_announcement(request.user):
            form.data = form.data.copy()
            form.data['is_announcement'] = ''

        if form.is_valid():
            form.save()
            messages.success(request, 'Message updated.')
            return redirect('session_detail', pk=pk)
    else:
        form = SessionMessageEditForm(instance=session_message)
        if not session_message.session.user_can_post_announcement(request.user):
            form.fields['is_announcement'].widget = form.fields['is_announcement'].hidden_widget()

    return render(request, 'sessions/session_message_edit.html', {
        'session': session_message.session,
        'session_message': session_message,
        'form': form,
    })


@login_required
def session_message_delete(request, pk, message_id):
    session_message = get_object_or_404(
        SessionMessage.objects.select_related('session', 'author'),
        pk=message_id,
        session_id=pk,
    )

    if session_message.session.is_cancelled:
        messages.error(request, 'This session has been cancelled.')
        return redirect('session_list')

    if not session_message.user_can_manage(request.user):
        return HttpResponseForbidden('You can only delete your own messages.')

    if request.method == 'POST':
        session_message.delete()
        messages.success(request, 'Message deleted.')

    return redirect('session_detail', pk=pk)

@login_required
@require_POST
def cancel_session(request, pk):
    session = get_object_or_404(Session, pk=pk)

    if session.host != request.user:
        return HttpResponseForbidden("You cannot cancel this session.")

    if session.is_cancelled:
        messages.info(request, "This session is already cancelled.")
        return redirect("session_list")

    reason = request.POST.get('reason', '').strip()[:500]

    with transaction.atomic():
        notified_count = notify_members_of_cancellation(session, reason)
        session.is_cancelled = True
        session.cancelled_at = timezone.now()
        session.save()

    if notified_count > 0:
        messages.success(
            request,
            f'Session cancelled. {notified_count} member(s) were notified.',
        )
    else:
        messages.success(request, 'Session cancelled.')

    return redirect("session_list")
