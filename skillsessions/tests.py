# AI gen tests. add/edit/delete as needed

from datetime import datetime, timedelta, timezone as dt_timezone
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from accounts.models import Skill
from .models import Session, SessionMembership, SessionMessage


class SessionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='host', password='testpass123')
        self.skill = Skill.objects.create(owner=self.user, name='Python')

    def test_create_session(self):
        session = Session.objects.create(
            skill=self.skill,
            host=self.user,
            title='Python Basics',
            description='Intro to Python',
            location='Room 101',
            date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            capacity=10,
        )
        self.assertEqual(session.host, self.user)
        self.assertEqual(session.skill, self.skill)
        self.assertIsNotNone(session.created_at)

    def test_session_str(self):
        session = Session.objects.create(
            skill=self.skill,
            host=self.user,
            title='Python Basics',
            location='Room 101',
            date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            capacity=10,
        )
        self.assertEqual(str(session), 'Python Basics (Python)')

    def test_clean_rejects_mismatched_host_and_skill_owner(self):
        other_user = User.objects.create_user(username='other', password='testpass123')
        session = Session(
            skill=self.skill,
            host=other_user,
            title='Stolen Session',
            location='Room 101',
            date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            capacity=10,
        )
        with self.assertRaises(ValidationError):
            session.clean()

    def test_clean_accepts_matching_host_and_skill_owner(self):
        session = Session(
            skill=self.skill,
            host=self.user,
            title='Valid Session',
            location='Room 101',
            date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            capacity=10,
        )
        session.clean()  # should not raise


class SessionMembershipModelTest(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username='host', password='testpass123')
        self.learner = User.objects.create_user(username='learner', password='testpass123')
        self.skill = Skill.objects.create(owner=self.host, name='Python')
        self.session = Session.objects.create(
            skill=self.skill,
            host=self.host,
            title='Python Basics',
            location='Room 101',
            date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            capacity=10,
        )

    def test_create_membership(self):
        membership = SessionMembership.objects.create(
            session=self.session,
            user=self.learner,
        )
        self.assertEqual(membership.session, self.session)
        self.assertEqual(membership.user, self.learner)
        self.assertIsNotNone(membership.joined_at)

    def test_membership_str(self):
        membership = SessionMembership.objects.create(
            session=self.session,
            user=self.learner,
        )
        self.assertEqual(str(membership), 'learner in Python Basics')

    def test_duplicate_membership_rejected(self):
        SessionMembership.objects.create(session=self.session, user=self.learner)
        with self.assertRaises(IntegrityError):
            SessionMembership.objects.create(session=self.session, user=self.learner)

    def test_same_user_different_sessions_allowed(self):
        other_session = Session.objects.create(
            skill=self.skill,
            host=self.host,
            title='Python Advanced',
            location='Room 102',
            date_time=timezone.now() + timedelta(days=2),
            duration_minutes=60,
            capacity=5,
        )
        SessionMembership.objects.create(session=self.session, user=self.learner)
        SessionMembership.objects.create(session=other_session, user=self.learner)
        self.assertEqual(SessionMembership.objects.filter(user=self.learner).count(), 2)


class SessionMessageModelTest(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username='host', password='testpass123')
        self.member = User.objects.create_user(username='member', password='testpass123')
        self.outsider = User.objects.create_user(username='outsider', password='testpass123')
        self.skill = Skill.objects.create(owner=self.host, name='Python')
        self.session = Session.objects.create(
            skill=self.skill,
            host=self.host,
            title='Python Basics',
            location='Room 101',
            date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            capacity=10,
        )
        SessionMembership.objects.create(session=self.session, user=self.member)

    def test_member_can_send_standard_message(self):
        message = SessionMessage.objects.create(
            session=self.session,
            author=self.member,
            content='Looking forward to it',
        )
        self.assertFalse(message.is_announcement)

    def test_outsider_cannot_send_message(self):
        with self.assertRaises(ValidationError):
            SessionMessage.objects.create(
                session=self.session,
                author=self.outsider,
                content='Can I join the chat?',
            )

    def test_only_host_can_send_announcement(self):
        with self.assertRaises(ValidationError):
            SessionMessage.objects.create(
                session=self.session,
                author=self.member,
                content='Room changed',
                is_announcement=True,
            )

    def test_message_reports_edited_state(self):
        message = SessionMessage.objects.create(
            session=self.session,
            author=self.member,
            content='First draft',
        )
        message.content = 'Updated draft'
        message.save()
        message.refresh_from_db()
        self.assertTrue(message.was_edited)


class SessionListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.skill = Skill.objects.create(owner=self.user, name='Python')

    def test_session_list_requires_login(self):
        response = self.client.get(reverse('session_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_session_list_shows_future_sessions_only(self):
        self.client.login(username='testuser', password='testpass123')
        Session.objects.create(
            skill=self.skill, host=self.user, title='Future',
            location='Room 1', date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60, capacity=5,
        )
        Session.objects.create(
            skill=self.skill, host=self.user, title='Past',
            location='Room 2', date_time=timezone.now() - timedelta(days=1),
            duration_minutes=60, capacity=5,
        )
        response = self.client.get(reverse('session_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Future')
        self.assertNotContains(response, 'Past')


class SessionCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_session_create_requires_login(self):
        response = self.client.get(reverse('session_create'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_session_create_redirects_if_no_skills(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('session_create'))
        self.assertRedirects(response, reverse('profile_edit'))

    def test_session_create_success(self):
        self.client.login(username='testuser', password='testpass123')
        skill = Skill.objects.create(owner=self.user, name='Python')
        response = self.client.post(reverse('session_create'), {
            'skill': skill.id,
            'title': 'Python Basics',
            'description': 'Learn Python',
            'location': 'Room 101',
            'date_time': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 60,
            'capacity': 10,
        })
        self.assertEqual(Session.objects.count(), 1)
        session = Session.objects.first()
        self.assertEqual(session.host, self.user)
        self.assertEqual(session.title, 'Python Basics')


class SessionDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.host = User.objects.create_user(username='host', password='testpass123')
        self.learner = User.objects.create_user(username='learner', password='testpass123')
        self.skill = Skill.objects.create(owner=self.host, name='Python')
        self.session = Session.objects.create(
            skill=self.skill, host=self.host, title='Python Basics',
            location='Room 101', date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60, capacity=2,
        )

    def test_session_detail_requires_login(self):
        response = self.client.get(reverse('session_detail', args=[self.session.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_session_detail_context_for_host(self):
        self.client.login(username='host', password='testpass123')
        response = self.client.get(reverse('session_detail', args=[self.session.pk]))
        self.assertTrue(response.context['is_host'])
        self.assertFalse(response.context['is_member'])

    def test_session_detail_context_for_member(self):
        self.client.login(username='learner', password='testpass123')
        SessionMembership.objects.create(session=self.session, user=self.learner)
        response = self.client.get(reverse('session_detail', args=[self.session.pk]))
        self.assertFalse(response.context['is_host'])
        self.assertTrue(response.context['is_member'])

    def test_session_detail_context_full(self):
        self.client.login(username='learner', password='testpass123')
        user_a = User.objects.create_user(username='a', password='testpass123')
        user_b = User.objects.create_user(username='b', password='testpass123')
        SessionMembership.objects.create(session=self.session, user=user_a)
        SessionMembership.objects.create(session=self.session, user=user_b)
        response = self.client.get(reverse('session_detail', args=[self.session.pk]))
        self.assertTrue(response.context['is_full'])

    def test_session_detail_hides_chat_for_non_participants(self):
        outsider = User.objects.create_user(username='outsider', password='testpass123')
        self.client.login(username='outsider', password='testpass123')
        response = self.client.get(reverse('session_detail', args=[self.session.pk]))
        self.assertFalse(response.context['can_access_chat'])
        self.assertContains(response, 'Join this session to view and send chat messages.')

    def test_session_detail_shows_chat_for_members(self):
        self.client.login(username='learner', password='testpass123')
        SessionMembership.objects.create(session=self.session, user=self.learner)
        SessionMessage.objects.create(
            session=self.session,
            author=self.host,
            content='Bring your laptop',
            is_announcement=True,
        )
        response = self.client.get(reverse('session_detail', args=[self.session.pk]))
        self.assertTrue(response.context['can_access_chat'])
        self.assertContains(response, 'Bring your laptop')
        self.assertContains(response, 'Announcement')

    def test_session_detail_shows_edit_controls_for_author_only(self):
        SessionMembership.objects.create(session=self.session, user=self.learner)
        learner_message = SessionMessage.objects.create(
            session=self.session,
            author=self.learner,
            content='My question',
        )
        self.client.login(username='learner', password='testpass123')
        response = self.client.get(reverse('session_detail', args=[self.session.pk]))
        self.assertContains(response, reverse('session_message_edit', args=[self.session.pk, learner_message.pk]))
        self.assertContains(response, reverse('session_message_delete', args=[self.session.pk, learner_message.pk]))

        self.client.login(username='host', password='testpass123')
        response = self.client.get(reverse('session_detail', args=[self.session.pk]))
        self.assertNotContains(response, reverse('session_message_edit', args=[self.session.pk, learner_message.pk]))


class SessionJoinViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.host = User.objects.create_user(username='host', password='testpass123')
        self.learner = User.objects.create_user(username='learner', password='testpass123')
        self.skill = Skill.objects.create(owner=self.host, name='Python')
        self.session = Session.objects.create(
            skill=self.skill, host=self.host, title='Python Basics',
            location='Room 101', date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60, capacity=2,
        )

    def test_join_session_success(self):
        self.client.login(username='learner', password='testpass123')
        response = self.client.post(reverse('session_join', args=[self.session.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SessionMembership.objects.filter(
            session=self.session, user=self.learner
        ).exists())

    def test_join_via_get_redirects_without_joining(self):
        self.client.login(username='learner', password='testpass123')
        response = self.client.get(reverse('session_join', args=[self.session.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SessionMembership.objects.filter(
            session=self.session, user=self.learner
        ).exists())

    def test_join_own_session_rejected(self):
        self.client.login(username='host', password='testpass123')
        response = self.client.post(reverse('session_join', args=[self.session.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SessionMembership.objects.filter(
            session=self.session, user=self.host
        ).exists())

    def test_join_full_session_rejected(self):
        self.client.login(username='learner', password='testpass123')
        user_a = User.objects.create_user(username='a', password='testpass123')
        user_b = User.objects.create_user(username='b', password='testpass123')
        SessionMembership.objects.create(session=self.session, user=user_a)
        SessionMembership.objects.create(session=self.session, user=user_b)
        response = self.client.post(reverse('session_join', args=[self.session.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SessionMembership.objects.filter(
            session=self.session, user=self.learner
        ).exists())

    def test_join_past_session_rejected(self):
        self.client.login(username='learner', password='testpass123')
        self.session.date_time = timezone.now() - timedelta(days=1)
        self.session.save()
        response = self.client.post(reverse('session_join', args=[self.session.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SessionMembership.objects.filter(
            session=self.session, user=self.learner
        ).exists())

    def test_join_already_joined_does_not_duplicate(self):
        self.client.login(username='learner', password='testpass123')
        SessionMembership.objects.create(session=self.session, user=self.learner)
        response = self.client.post(reverse('session_join', args=[self.session.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SessionMembership.objects.filter(
            session=self.session, user=self.learner
        ).count(), 1)


class SessionLeaveViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.host = User.objects.create_user(username='host', password='testpass123')
        self.learner = User.objects.create_user(username='learner', password='testpass123')
        self.skill = Skill.objects.create(owner=self.host, name='Python')
        self.session = Session.objects.create(
            skill=self.skill, host=self.host, title='Python Basics',
            location='Room 101', date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60, capacity=5,
        )

    def test_leave_session_success(self):
        self.client.login(username='learner', password='testpass123')
        SessionMembership.objects.create(session=self.session, user=self.learner)
        response = self.client.post(reverse('session_leave', args=[self.session.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SessionMembership.objects.filter(
            session=self.session, user=self.learner
        ).exists())

    def test_leave_when_not_a_member(self):
        self.client.login(username='learner', password='testpass123')
        response = self.client.post(reverse('session_leave', args=[self.session.pk]))
        self.assertEqual(response.status_code, 302)


class SessionMessageCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.host = User.objects.create_user(username='host', password='testpass123')
        self.member = User.objects.create_user(username='member', password='testpass123')
        self.outsider = User.objects.create_user(username='outsider', password='testpass123')
        self.skill = Skill.objects.create(owner=self.host, name='Python')
        self.session = Session.objects.create(
            skill=self.skill,
            host=self.host,
            title='Python Basics',
            location='Room 101',
            date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            capacity=10,
        )
        SessionMembership.objects.create(session=self.session, user=self.member)

    def test_member_can_post_chat_message(self):
        self.client.login(username='member', password='testpass123')
        response = self.client.post(reverse('session_message_create', args=[self.session.pk]), {
            'content': 'Excited for the session',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SessionMessage.objects.filter(
            session=self.session,
            author=self.member,
            content='Excited for the session',
            is_announcement=False,
        ).exists())

    def test_host_can_post_announcement(self):
        self.client.login(username='host', password='testpass123')
        response = self.client.post(reverse('session_message_create', args=[self.session.pk]), {
            'content': 'Please arrive 10 minutes early',
            'is_announcement': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SessionMessage.objects.filter(
            session=self.session,
            author=self.host,
            is_announcement=True,
        ).exists())

    def test_member_cannot_escalate_message_to_announcement(self):
        self.client.login(username='member', password='testpass123')
        self.client.post(reverse('session_message_create', args=[self.session.pk]), {
            'content': 'This should not become an announcement',
            'is_announcement': 'on',
        })
        message = SessionMessage.objects.get(author=self.member)
        self.assertFalse(message.is_announcement)

    def test_outsider_cannot_post_message(self):
        self.client.login(username='outsider', password='testpass123')
        response = self.client.post(reverse('session_message_create', args=[self.session.pk]), {
            'content': 'Let me in',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SessionMessage.objects.filter(content='Let me in').exists())


class SessionMessageManageViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.host = User.objects.create_user(username='host', password='testpass123')
        self.member = User.objects.create_user(username='member', password='testpass123')
        self.other_member = User.objects.create_user(username='othermember', password='testpass123')
        self.skill = Skill.objects.create(owner=self.host, name='Python')
        self.session = Session.objects.create(
            skill=self.skill,
            host=self.host,
            title='Python Basics',
            location='Room 101',
            date_time=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            capacity=10,
        )
        SessionMembership.objects.create(session=self.session, user=self.member)
        SessionMembership.objects.create(session=self.session, user=self.other_member)
        self.message = SessionMessage.objects.create(
            session=self.session,
            author=self.member,
            content='Original message',
        )

    def test_author_can_edit_message(self):
        self.client.login(username='member', password='testpass123')
        response = self.client.post(reverse('session_message_edit', args=[self.session.pk, self.message.pk]), {
            'content': 'Edited message',
        })
        self.assertEqual(response.status_code, 302)
        self.message.refresh_from_db()
        self.assertEqual(self.message.content, 'Edited message')
        self.assertTrue(self.message.was_edited)

    def test_non_author_cannot_edit_message(self):
        self.client.login(username='othermember', password='testpass123')
        response = self.client.post(reverse('session_message_edit', args=[self.session.pk, self.message.pk]), {
            'content': 'Hijacked edit',
        })
        self.assertEqual(response.status_code, 403)
        self.message.refresh_from_db()
        self.assertEqual(self.message.content, 'Original message')

    def test_author_can_delete_message(self):
        self.client.login(username='member', password='testpass123')
        response = self.client.post(reverse('session_message_delete', args=[self.session.pk, self.message.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SessionMessage.objects.filter(pk=self.message.pk).exists())

    def test_non_author_cannot_delete_message(self):
        self.client.login(username='othermember', password='testpass123')
        response = self.client.post(reverse('session_message_delete', args=[self.session.pk, self.message.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(SessionMessage.objects.filter(pk=self.message.pk).exists())

    def test_host_can_edit_own_announcement(self):
        announcement = SessionMessage.objects.create(
            session=self.session,
            author=self.host,
            content='Initial announcement',
            is_announcement=True,
        )
        self.client.login(username='host', password='testpass123')
        response = self.client.post(reverse('session_message_edit', args=[self.session.pk, announcement.pk]), {
            'content': 'Updated announcement',
            'is_announcement': 'on',
        })
        self.assertEqual(response.status_code, 302)
        announcement.refresh_from_db()
        self.assertEqual(announcement.content, 'Updated announcement')
        self.assertTrue(announcement.is_announcement)


class TimezoneHandlingTest(TestCase):
    """Exercises UserTimezoneMiddleware end-to-end via ingestion and display."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tzuser', password='testpass123')
        self.skill = Skill.objects.create(owner=self.user, name='Python')
        self.client.login(username='tzuser', password='testpass123')

    def _post_session(self, naive_datetime_str):
        return self.client.post(reverse('session_create'), {
            'skill': self.skill.id,
            'title': 'TZ Test Session',
            'description': 'Timezone check',
            'location': 'Room TZ',
            'date_time': naive_datetime_str,
            'duration_minutes': 60,
            'capacity': 5,
        })

    def test_ingest_uses_cookie_timezone(self):
        # July 15 → PDT (UTC-7). 14:30 Los Angeles → 21:30 UTC.
        # Using LA (not ET) specifically so a broken cookie path would produce
        # the wrong UTC value and fail this assertion.
        self.client.cookies['tz'] = 'America/Los_Angeles'
        response = self._post_session('2026-07-15T14:30')
        self.assertEqual(response.status_code, 302)
        session = Session.objects.latest('id')
        expected = datetime(2026, 7, 15, 21, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(session.date_time, expected)

    def test_ingest_fallback_without_cookie(self):
        # No cookie set → middleware falls back to America/New_York.
        # July 15 → EDT (UTC-4). 14:30 ET → 18:30 UTC.
        response = self._post_session('2026-07-15T14:30')
        self.assertEqual(response.status_code, 302)
        session = Session.objects.latest('id')
        expected = datetime(2026, 7, 15, 18, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(session.date_time, expected)

    def test_ingest_fallback_on_invalid_cookie(self):
        # Malformed path-like value exercises the ValueError branch of
        # ZoneInfo() rather than ZoneInfoNotFoundError. Must not 500; must
        # fall back to America/New_York.
        self.client.cookies['tz'] = '/etc/passwd'
        response = self._post_session('2026-07-15T14:30')
        self.assertEqual(response.status_code, 302)
        session = Session.objects.latest('id')
        expected = datetime(2026, 7, 15, 18, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(session.date_time, expected)

    def test_display_uses_cookie_timezone(self):
        # Stored as 18:30 UTC; with America/New_York active it should render
        # as 2:30 p.m. (EDT) on the session_detail page.
        session = Session.objects.create(
            skill=self.skill,
            host=self.user,
            title='Display TZ Session',
            location='Room TZ',
            date_time=datetime(2026, 7, 15, 18, 30, tzinfo=dt_timezone.utc),
            duration_minutes=60,
            capacity=5,
        )
        self.client.cookies['tz'] = 'America/New_York'
        response = self.client.get(reverse('session_detail', args=[session.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2:30')
        self.assertNotContains(response, '18:30')

    def test_dst_boundary_january(self):
        # January 15 → PST (UTC-8), not PDT. 14:30 LA → 22:30 UTC.
        # Confirms zoneinfo is actually picking the correct DST offset by date.
        self.client.cookies['tz'] = 'America/Los_Angeles'
        response = self._post_session('2026-01-15T14:30')
        self.assertEqual(response.status_code, 302)
        session = Session.objects.latest('id')
        expected = datetime(2026, 1, 15, 22, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(session.date_time, expected)
