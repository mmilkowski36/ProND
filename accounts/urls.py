from django.urls import path
from .views import (
    login_page, about_page, profile_view, profile_edit, profile_detail,
    skill_search, session_request_create, session_request_cancel, session_requests_inbox,
)
from .views import login_page, about_page, profile_view, profile_edit, profile_detail, profile_search, inbox, send_message

urlpatterns = [
    path('', login_page, name='login'),
    path('about/', about_page, name='about'),
    path('profile/', profile_view, name='profile_view'),
    path('profile/edit/', profile_edit, name='profile_edit'),
    path('profile/<int:user_id>/', profile_detail, name='profile_detail'),
    path('skills/search/', skill_search, name='skill_search'),
    path('skills/<int:skill_id>/request/', session_request_create, name='session_request_create'),
    path('skills/requests/<int:request_id>/cancel/', session_request_cancel, name='session_request_cancel'),
    path('skills/requests/inbox/', session_requests_inbox, name='session_requests_inbox'),
    path('search/', profile_search, name='profile_search'),
    path('inbox/', inbox, name='inbox'),
    path('messages/send/<int:receiver_id>/', send_message, name='send_message'),
    path('messages/chat/<int:receiver_id>/', send_message, name='chat_detail')
]