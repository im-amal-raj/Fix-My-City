from django.urls import path
from core import views

urlpatterns = [
    # Auth
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('password/', views.password_change_view, name='password_change'),

    # Citizen
    path('dashboard/', views.citizen_dashboard, name='citizen_dashboard'),
    path('report/location/', views.report_location, name='report_location'),
    path('report/details/', views.citizen_intake_form, name='intake_form'),
    path('report/processing/', views.citizen_tracker, name='citizen_tracker'),
    path('community/', views.community_feed, name='community_feed'),
    path('ticket/<int:ticket_id>/follow/', views.follow_ticket, name='follow_ticket'),
    path('ticket/<int:ticket_id>/', views.ticket_detail_public, name='ticket_detail_public'),

    # API endpoints (AJAX)
    path('api/check-nearby/', views.api_check_nearby, name='api_check_nearby'),
    path('api/submit-ticket/', views.api_submit_ticket, name='api_submit_ticket'),

    # Officer
    path('officer/triage/', views.officer_triage, name='officer_triage'),
    path('officer/ticket/<int:ticket_id>/', views.officer_ticket_detail, name='officer_ticket_detail'),
    path('officer/ticket/<int:ticket_id>/validate/', views.validate_ticket, name='validate_ticket'),
    path('officer/active/', views.officer_active_work, name='officer_active_work'),


    # Worker
    path('worker/tasks/', views.worker_tasks, name='worker_tasks'),
    path('worker/resolve/<int:ticket_id>/', views.worker_resolve, name='worker_resolve'),
]
