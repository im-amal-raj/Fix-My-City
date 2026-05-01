"""
Utility functions for the FixMyCity backend.
Handles geo lookups, simple deduplication, and rule-based triage.
"""
import math
import io
from PIL import Image




# Haversine Distance Calculator
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two GPS coordinates in meters.
    """
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


# Simple Image Save
def scrub_exif(image_file):
    """
    Simply returns the image file (advanced EXIF scrubbing removed for simplicity).
    """
    return image_file


# Simple Deduplication
def check_for_duplicates(lat, lng, landmark_text, category):
    """
    Basic duplicate check: If there's an existing ticket within 50 meters
    with the exact same category, consider it a potential duplicate.
    """
    from core.models import CommunityIssue

    # Bounding box filter (approx 500m)
    delta = 0.005
    nearby_tickets = CommunityIssue.objects.filter(
        status__in=['NEW', 'VALIDATED', 'IN_PROGRESS'],
        latitude__range=(lat - delta, lat + delta),
        longitude__range=(lng - delta, lng + delta),
        category=category  # exact category match required now
    )

    duplicates = []
    for ticket in nearby_tickets:
        distance = haversine_distance(lat, lng, ticket.latitude, ticket.longitude)
        if distance <= 50:
            duplicates.append({
                'ticket': ticket,
                'reason': 'Same category within 50m',
                'distance_m': int(round(distance)),
                'match_score': 90,
            })

    return duplicates


# Nearby Tickets for Map
def get_nearby_tickets(lat, lng, radius_m=50):
    """
    Find active tickets near a given coordinate.
    """
    from core.models import CommunityIssue

    delta = 0.005
    candidates = CommunityIssue.objects.filter(
        status__in=['NEW', 'VALIDATED', 'IN_PROGRESS'],
        latitude__range=(lat - delta, lat + delta),
        longitude__range=(lng - delta, lng + delta),
    )

    nearby = []
    for ticket in candidates:
        distance = haversine_distance(lat, lng, ticket.latitude, ticket.longitude)
        if distance <= radius_m:
            nearby.append({
                'id': ticket.id,
                'title': ticket.title,
                'category': ticket.get_category_display(),
                'status': ticket.get_status_display(),
                'distance_m': round(distance),
                'latitude': ticket.latitude,
                'longitude': ticket.longitude,
                'follower_count': ticket.followers.count(),
            })
    return nearby


# Rule-Based Triage
def auto_triage(description, category):
    """
    Simple keyword-based triage. Checks the description for
    urgent/medium keywords and assigns a priority score (1-10)
    and routes to the correct department based on category.
    """
    desc_lower = description.lower()

    # Priority: default 5, bumped by keywords
    priority_score = 5
    is_public_hazard = False

    urgent_keywords = ['urgent', 'danger', 'hazard', 'accident', 'emergency', 'fire', 'collapse']
    if any(word in desc_lower for word in urgent_keywords):
        priority_score = 9
        is_public_hazard = True

    medium_keywords = ['leak', 'broken', 'smell', 'block', 'waste', 'garbage', 'pothole']
    if any(word in desc_lower for word in medium_keywords):
        priority_score = max(priority_score, 7)

    # Department routing based on category
    departments = []
    if category == 'ROAD' or 'pothole' in desc_lower:
        departments.append('PWD_Roads')
    if category == 'WATER' or 'leak' in desc_lower or 'pipe' in desc_lower:
        departments.append('KWA_Water')
    if category in ('STREETLIGHT', 'ELECTRICAL') or 'electricity' in desc_lower:
        departments.append('KSEB_Electricity')
    if category == 'WASTE' or 'waste' in desc_lower or 'garbage' in desc_lower:
        departments.append('Health_Sanitation')

    if not departments:
        departments.append('Local_Panchayat')

    return {
        'summary': description,  # just keep original text as summary
        'priority_score': priority_score,
        'is_public_hazard': is_public_hazard,
        'departments': list(set(departments)),
    }
