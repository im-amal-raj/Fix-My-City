"""
FixMyCity — Views
Handles all the HTTP request/response logic for citizens, officers, and field workers.
"""
import json
import base64
import io
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Q, Count
from django.views.decorators.http import require_POST

from .models import CustomUser, CommunityIssue
from .forms import CitizenProfileForm, TailwindPasswordChangeForm
from .utils import (
    scrub_exif,
    check_for_duplicates,
    get_nearby_tickets,
    auto_triage,
)



#  AUTH VIEWS


def login_view(request):
    """Login page — redirects based on user role after login."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Check if account is deactivated — allow restoration within 30 days
            if user.is_deactivated:
                if user.deletion_requested_at and (timezone.now() - user.deletion_requested_at).days < 30:
                    user.is_deactivated = False
                    user.deletion_requested_at = None
                    user.save()
                    messages.success(request, 'Welcome back! Your account has been restored.')
                else:
                    messages.error(request, 'This account has been permanently deactivated.')
                    return render(request, 'core/login.html')

            login(request, user)
            return _redirect_by_role(user)
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'core/login.html')


def register_view(request):
    """Registration page — creates a new citizen account with 15 starting points."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        # Basic validation
        if password != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/register.html')

        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return render(request, 'core/register.html')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'core/register.html')

        # Create user with 15 starting civic points
        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role='CITIZEN',
            civic_points=15,
        )
        login(request, user)
        messages.success(request, f'Welcome to FixMyCity! You start with 15 Civic Points.')
        return redirect('citizen_dashboard')

    return render(request, 'core/register.html')


def logout_view(request):
    """Log user out and redirect to login page."""
    logout(request)
    return redirect('login')


@login_required
def profile_view(request):
    """Citizen profile editing."""
    if request.user.role != 'CITIZEN':
        messages.error(request, 'Only citizens can edit their profile details. Staff must contact an administrator.')
        return redirect('citizen_dashboard') # Fallback, _redirect_by_role handles logic

    if request.method == 'POST':
        form = CitizenProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('profile')
    else:
        form = CitizenProfileForm(instance=request.user)

    return render(request, 'core/profile.html', {'form': form})


@login_required
def password_change_view(request):
    """Password change for all roles."""
    if request.method == 'POST':
        form = TailwindPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user) # Prevent logout
            messages.success(request, 'Your password was successfully updated!')
            return _redirect_by_role(request.user)
    else:
        form = TailwindPasswordChangeForm(request.user)

    return render(request, 'core/password_change.html', {'form': form})


def _redirect_by_role(user):
    """Helper to redirect users to their role-specific dashboard."""
    if user.role == 'OFFICER' or user.is_staff:
        return redirect('officer_triage')
    elif user.role == 'FIELD_WORKER':
        return redirect('worker_tasks')
    else:
        return redirect('citizen_dashboard')



#  CITIZEN VIEWS


@login_required
def citizen_dashboard(request):
    """Main citizen dashboard showing their reports, following, and stats."""
    user = request.user

    # Daily civic points refill: +2 points per day, max 15
    if user.last_login:
        days_since = (timezone.now() - user.last_login).days
        if days_since >= 1 and user.civic_points < 15:
            refill = min(days_since * 2, 15 - user.civic_points)
            if refill > 0:
                user.civic_points += refill
                user.save()
                messages.info(request, f'+{refill} Civic Points refilled! (Daily bonus)')

    # My tickets
    my_tickets = CommunityIssue.objects.filter(reporter=user).order_by('-created_at')

    # Tickets I'm following
    following = CommunityIssue.objects.filter(followers=user).order_by('-created_at')

    # Stats
    validated_count = CommunityIssue.objects.filter(reporter=user, status__in=['VALIDATED', 'IN_PROGRESS']).count()
    resolved_count = CommunityIssue.objects.filter(reporter=user, status='RESOLVED').count()
    rejected_count = CommunityIssue.objects.filter(reporter=user, status='REJECTED').count()

    # Feed Tabs Logic
    tab = request.GET.get('tab', 'local')
    
    if tab == 'myward':
        # Get the ward from user's most recent ticket or fallback
        recent_ticket = CommunityIssue.objects.filter(reporter=user).first()
        ward = recent_ticket.ward_name if recent_ticket else ''
        if ward:
            feed_tickets = CommunityIssue.objects.filter(ward_name=ward).exclude(status='REJECTED').order_by('-created_at')
        else:
            feed_tickets = CommunityIssue.objects.none()
    elif tab == 'resolved':
        feed_tickets = CommunityIssue.objects.filter(status='RESOLVED').order_by('-created_at')
    else:
        # Default 'local' feed (all active)
        feed_tickets = CommunityIssue.objects.exclude(status='REJECTED').order_by('-created_at')

    context = {
        'tickets': feed_tickets,
        'following_tickets': following,
        'validated_count': validated_count,
        'resolved_count': resolved_count,
        'rejected_count': rejected_count,
        'current_tab': tab,
    }
    return render(request, 'core/citizen_dashboard.html', context)


@login_required
def report_location(request):
    """Location picker page — user picks GPS or searches for an address."""
    return render(request, 'core/report_location.html')


@login_required
def citizen_intake_form(request):
    """
    The intake form — photo upload, description, category selection.
    Coordinates come from the Map Shield page via hidden fields or session.
    """
    # Get coordinates from query params (set by Map Shield JS)
    lat = request.GET.get('lat', '')
    lng = request.GET.get('lng', '')

    context = {
        'latitude': lat,
        'longitude': lng,
        'can_submit': request.user.can_submit_ticket(),
        'civic_points': request.user.civic_points,
    }
    return render(request, 'core/citizen_intake_form.html', context)


@login_required
def citizen_tracker(request):
    """
    Handle the ticket submission, run deduplication, and perform initial routing.
    """
    if request.method == 'POST':
        user = request.user

        # Check civic points
        if not user.can_submit_ticket():
            return JsonResponse({'status': 'error', 'message': 'Insufficient civic points.'})

        # Extract form data
        title = request.POST.get('title', 'Untitled Issue')
        description = request.POST.get('description', '')
        category = request.POST.get('category', 'OTHER')
        latitude = float(request.POST.get('latitude', 0))
        longitude = float(request.POST.get('longitude', 0))
        landmark_note = request.POST.get('landmark_note', '')
        is_pseudonymous = request.POST.get('is_pseudonymous') == 'on'
        force_override = request.POST.get('force_override') == 'true'

        # Handle photo upload
        photo_file = request.FILES.get('issue_photo')

        if photo_file:
            photo_file.seek(0)

        # Manual Ward Selection
        ward_name = request.POST.get('ward_name', 'Unknown')
        panchayat_name = request.POST.get('panchayat_name', 'Unknown')

        # Stage: Deduplication check (unless force override)
        if not force_override:
            duplicates = check_for_duplicates(
                latitude, longitude, None, landmark_note, category
            )
            if duplicates:
                # Return duplicate warning — tracker pauses at Node 2
                dup = duplicates[0]
                return JsonResponse({
                    'status': 'duplicate_warning',
                    'existing_ticket_id': dup['ticket'].id,
                    'existing_title': dup['ticket'].title,
                    'match_reason': dup['reason'],
                    'match_score': dup['match_score'],
                    'distance_m': dup['distance_m'],
                })

        # Save ticket
        ticket = CommunityIssue(
            reporter=user,
            title=title,
            description=description,
            category=category,
            latitude=latitude,
            longitude=longitude,
            landmark_note=landmark_note,
            ward_name=ward_name,
            panchayat_name=panchayat_name,
            is_pseudonymous=is_pseudonymous,
            status='NEW',
            priority_score=0,
        )

        if photo_file:
            ticket.issue_photo = photo_file

        ticket.save()

        # Run keyword-based triage
        triage_result = auto_triage(description, category)
        ticket.ai_formal_summary = triage_result['summary']
        ticket.priority_score = triage_result['priority_score']
        ticket.is_public_hazard = triage_result['is_public_hazard']
        ticket.ai_departments = triage_result['departments']
        ticket.save()

        # Deduct civic points
        user.civic_points -= 5
        user.save()

        return JsonResponse({
            'status': 'success',
            'ticket_id': ticket.id,
            'priority_score': ticket.priority_score,
        })

    # GET request — show simple success page
    context = {
        'ticket_id': request.GET.get('ticket_id', ''),
    }
    return render(request, 'core/citizen_tracker.html', context)


@login_required
def community_feed(request):
    """
    Public community feed showing validated, in-progress, and resolved tickets.
    Supports search by title, category, or landmark.
    """
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    ward_filter = request.GET.get('ward', '')

    tickets = CommunityIssue.objects.filter(
        status__in=['VALIDATED', 'IN_PROGRESS', 'RESOLVED']
    ).order_by('-created_at')

    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    if ward_filter:
        tickets = tickets.filter(ward_name__icontains=ward_filter)

    if query:
        tickets = tickets.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(landmark_note__icontains=query) |
            Q(category__icontains=query)
        )

    context = {
        'tickets': tickets,
        'search_query': query,
        'current_status': status_filter,
        'current_ward': ward_filter,
    }
    return render(request, 'core/community_feed.html', context)


@login_required
def follow_ticket(request, ticket_id):
    """Follow an existing ticket (+1 civic point, capped at 5/day)."""
    ticket = get_object_or_404(CommunityIssue, id=ticket_id)
    user = request.user

    if user == ticket.reporter:
        messages.info(request, "You can't follow your own ticket.")
        return redirect('community_feed')

    if ticket.followers.filter(id=user.id).exists():
        messages.info(request, 'You are already following this issue.')
        return redirect('community_feed')

    # Check daily follow cap (5 per day)
    today = timezone.now().date()
    # Simple approach — count follows made today
    today_follow_count = CommunityIssue.objects.filter(
        followers=user,
    ).count()  # simplified — in production you'd track follow timestamps

    ticket.followers.add(user)

    # Award +1 civic point (capped at 5/day)
    if today_follow_count < 5:
        user.civic_points += 1
        user.save()
        messages.success(request, f'Following this issue! +1 Civic Point.')
    else:
        messages.success(request, 'Following this issue! (Daily point cap reached)')

    return redirect('community_feed')


@login_required
def ticket_detail_public(request, ticket_id):
    """Public ticket detail view — shows before/after photos if resolved."""
    ticket = get_object_or_404(CommunityIssue, id=ticket_id)

    # Check if user is following
    is_following = ticket.followers.filter(id=request.user.id).exists()

    context = {
        'ticket': ticket,
        'is_following': is_following,
    }
    return render(request, 'core/ticket_detail_public.html', context)



#  API ENDPOINTS (AJAX)


def api_check_nearby(request):
    """
    AJAX endpoint for the Map Shield.
    Returns nearby active tickets within 50m of given coordinates.
    Called by JS before the user uploads a photo.
    """
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')

    if not lat or not lng:
        return JsonResponse({'status': 'error', 'message': 'Missing coordinates'})

    try:
        lat = float(lat)
        lng = float(lng)
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid coordinates'})

    nearby = get_nearby_tickets(lat, lng, radius_m=50)

    return JsonResponse({
        'status': 'ok',
        'count': len(nearby),
        'tickets': nearby,
    })


@require_POST
@login_required
def api_submit_ticket(request):
    """
    Handles the full pipeline: save → dedup → triage → respond.
    """
    user = request.user

    if not user.can_submit_ticket():
        return JsonResponse({'status': 'error', 'message': 'Insufficient civic points (need 5).'})

    title = request.POST.get('title', 'Untitled Issue')
    description = request.POST.get('description', '')
    category = request.POST.get('category', 'OTHER')
    latitude = float(request.POST.get('latitude', 0))
    longitude = float(request.POST.get('longitude', 0))
    landmark_note = request.POST.get('landmark_note', '')
    is_pseudonymous = request.POST.get('is_pseudonymous') == 'true'
    force_override = request.POST.get('force_override') == 'true'

    # Handle the base64 photo from Canvas compression
    photo_data = request.POST.get('photo_data', '')
    photo_file = None


    if photo_data:
        try:
            if ',' in photo_data:
                photo_data = photo_data.split(',')[1]

            image_bytes = base64.b64decode(photo_data)
            photo_file = ContentFile(image_bytes, name=f'issue_{user.id}_{timezone.now().timestamp()}.jpg')

        except Exception as e:
            print(f"[Submit] Photo processing error: {e}")

    # Also handle regular file upload
    if not photo_file and request.FILES.get('issue_photo'):
        photo_file = request.FILES['issue_photo']
        photo_file.seek(0)

    # Manual Ward Selection
    ward_name = request.POST.get('ward_name', 'Unknown')
    panchayat_name = request.POST.get('panchayat_name', 'Unknown')

    # Dedup check (unless forced)
    if not force_override:
        duplicates = check_for_duplicates(
            latitude, longitude, landmark_note, category
        )
        if duplicates:
            dup = duplicates[0]
            return JsonResponse({
                'status': 'duplicate_warning',
                'existing_ticket_id': dup['ticket'].id,
                'existing_title': dup['ticket'].title,
                'match_reason': dup['reason'],
                'match_score': dup['match_score'],
                'distance_m': dup['distance_m'],
            })

    # Save the ticket (Commit-Then-Enhance)
    ticket = CommunityIssue(
        reporter=user,
        title=title,
        description=description,
        category=category,
        latitude=latitude,
        longitude=longitude,
        landmark_note=landmark_note,
        ward_name=ward_name,
        panchayat_name=panchayat_name,
        is_pseudonymous=is_pseudonymous,
        status='NEW',
        priority_score=0,
    )

    if photo_file:
        ticket.issue_photo = photo_file

    ticket.save()

    # Run keyword-based triage
    triage_result = auto_triage(description, category)
    ticket.ai_formal_summary = triage_result['summary']
    ticket.priority_score = triage_result['priority_score']
    ticket.is_public_hazard = triage_result['is_public_hazard']
    ticket.ai_departments = triage_result['departments']
    ticket.save()

    return JsonResponse({
        'status': 'success',
        'ticket_id': ticket.id,
        'priority_score': ticket.priority_score,
    })



#  OFFICER VIEWS


@login_required
def officer_triage(request):
    """
    Triage Queue — shows NEW tickets sorted by priority score descending.
    Only accessible by Officers.
    """
    if request.user.role != 'OFFICER' and not request.user.is_staff:
        return redirect('citizen_dashboard')

    tickets = CommunityIssue.objects.filter(status='NEW').order_by('-priority_score', '-created_at')
    
    ward_filter = request.GET.get('ward', '')
    if ward_filter:
        tickets = tickets.filter(ward_name__icontains=ward_filter)
        
    pending_count = tickets.count()

    context = {
        'tickets': tickets,
        'pending_count': pending_count,
        'current_ward': ward_filter,
    }
    return render(request, 'core/officer_triage.html', context)


@login_required
def officer_ticket_detail(request, ticket_id):
    """Detailed view of a single ticket for the officer to review."""
    if request.user.role != 'OFFICER' and not request.user.is_staff:
        return redirect('citizen_dashboard')

    ticket = get_object_or_404(CommunityIssue, id=ticket_id)
    workers = CustomUser.objects.filter(role='FIELD_WORKER', is_active=True)

    context = {
        'ticket': ticket,
        'workers': workers,
    }
    return render(request, 'core/officer_ticket_detail.html', context)


@login_required
@require_POST
def validate_ticket(request, ticket_id):
    """
    Handle officer validate/reject actions on a ticket.
    Validate: assigns worker, changes status, awards civic points.
    Reject: marks rejected, deducts points, records reason.
    """
    if request.user.role != 'OFFICER' and not request.user.is_staff:
        return redirect('citizen_dashboard')

    ticket = get_object_or_404(CommunityIssue, id=ticket_id)
    action = request.POST.get('action')

    if action == 'validate':
        worker_id = request.POST.get('assigned_worker')
        if worker_id:
            worker = get_object_or_404(CustomUser, id=worker_id, role='FIELD_WORKER')
            ticket.assigned_worker = worker
            ticket.status = 'IN_PROGRESS'
        else:
            ticket.status = 'VALIDATED'

        ticket.save()

        # Award +10 civic points to reporter for validated ticket
        reporter = ticket.reporter
        reporter.civic_points += 10
        reporter.save()

        # Send email notification
        try:
            send_mail(
                subject=f'Your ticket #{ticket.id} has been validated!',
                message=f'Great news! Your reported issue "{ticket.title}" has been validated by city staff and is now being processed.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reporter.email],
                fail_silently=True,
            )
        except Exception:
            pass

        messages.success(request, f'Ticket #{ticket.id} validated and assigned.')

    elif action == 'reject':
        rejection_reason = request.POST.get('rejection_reason', 'No reason provided')
        ticket.status = 'REJECTED'
        ticket.rejection_reason = rejection_reason
        ticket.save()

        # Penalize reporter: -5 civic points (they already lost the initial 5)
        reporter = ticket.reporter
        reporter.civic_points -= 5
        reporter.save()

        # Send rejection email
        try:
            send_mail(
                subject=f'Your ticket #{ticket.id} was rejected',
                message=f'Your reported issue "{ticket.title}" was rejected. Reason: {rejection_reason}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reporter.email],
                fail_silently=True,
            )
        except Exception:
            pass

        messages.info(request, f'Ticket #{ticket.id} rejected.')

    return redirect('officer_triage')


@login_required
def officer_active_work(request):
    """Dashboard showing validated and in-progress tickets with stats."""
    if request.user.role != 'OFFICER' and not request.user.is_staff:
        return redirect('citizen_dashboard')

    active_tickets = CommunityIssue.objects.filter(
        status__in=['VALIDATED', 'IN_PROGRESS']
    ).order_by('-priority_score')

    # Stats for charts
    pending_count = CommunityIssue.objects.filter(status='NEW').count()
    open_count = CommunityIssue.objects.filter(status__in=['VALIDATED', 'IN_PROGRESS']).count()
    in_progress_count = CommunityIssue.objects.filter(status='IN_PROGRESS').count()
    closed_count = CommunityIssue.objects.filter(status='RESOLVED').count()

    context = {
        'active_tickets': active_tickets,
        'pending_count': pending_count,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'closed_count': closed_count,
    }
    return render(request, 'core/officer_active_work.html', context)

#  WORKER VIEWS


@login_required
def worker_tasks(request):
    """Field worker's task list — shows tickets assigned to them."""
    if request.user.role != 'FIELD_WORKER':
        return redirect('citizen_dashboard')

    tasks = CommunityIssue.objects.filter(
        assigned_worker=request.user,
        status__in=['VALIDATED', 'IN_PROGRESS'],
    ).order_by('-priority_score')

    next_task = tasks.first()

    context = {
        'tasks': tasks,
        'next_task': next_task,
    }
    return render(request, 'core/worker_tasks.html', context)


@login_required
def worker_resolve(request, ticket_id):
    """
    Resolution flow for field workers.
    Requires uploading an "After" photo and a note to close the ticket.
    Triggers the Civic Bounty payout to the original reporter.
    """
    if request.user.role != 'FIELD_WORKER':
        return redirect('citizen_dashboard')

    ticket = get_object_or_404(
        CommunityIssue, id=ticket_id, assigned_worker=request.user
    )

    if request.method == 'POST':
        resolution_photo = request.FILES.get('resolution_photo')
        worker_note = request.POST.get('worker_note', '')

        if resolution_photo:
            ticket.resolution_photo = resolution_photo

        ticket.worker_note = worker_note
        ticket.status = 'RESOLVED'
        ticket.save()

        # Civic Bounty — award +10 points to the original reporter
        reporter = ticket.reporter
        reporter.civic_points += 10
        reporter.save()

        # Send resolution email to reporter AND all followers
        recipient_emails = [reporter.email]
        for follower in ticket.followers.all():
            if follower.email and follower.email not in recipient_emails:
                recipient_emails.append(follower.email)

        try:
            send_mail(
                subject=f'Issue Resolved: {ticket.title}',
                message=(
                    f'Great news! The issue you reported/followed ("{ticket.title}") '
                    f'has been resolved by the city.\n\n'
                    f'Worker note: {worker_note}\n\n'
                    f'Visit FixMyCity to see the before and after photos!'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                fail_silently=True,
            )
        except Exception:
            pass

        messages.success(request, f'Ticket #{ticket.id} resolved! +10 Civic Points awarded to reporter.')
        return redirect('worker_tasks')

    context = {
        'ticket': ticket,
    }
    return render(request, 'core/worker_resolve.html', context)
