from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


# Custom User Model
class CustomUser(AbstractUser):
    """Extended user with role-based access and civic points economy."""

    ROLE_CHOICES = [
        ('CITIZEN', 'Citizen'),
        ('OFFICER', 'Officer'),
        ('FIELD_WORKER', 'Field Worker'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CITIZEN')
    civic_points = models.IntegerField(default=15)  # starting balance
    is_deactivated = models.BooleanField(default=False)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)

    def get_trust_badge(self):
        """Returns the trust badge based on civic points."""
        if self.civic_points >= 76:
            return 'Gold'
        elif self.civic_points >= 31:
            return 'Silver'
        else:
            return 'Bronze'

    def can_submit_ticket(self):
        """Check if user has enough points to submit a ticket."""
        return self.civic_points >= 5

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"


# Community Issue Model
class CommunityIssue(models.Model):
    """Main ticket model for civic issues reported by citizens."""

    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('VALIDATED', 'Validated'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected'),
        ('ARCHIVED', 'Archived'),
    ]

    CATEGORY_CHOICES = [
        ('ROAD', 'Road / Pothole'),
        ('ELECTRICAL', 'Electrical'),
        ('WATER', 'Water / Drainage'),
        ('SANITATION', 'Sanitation'),
        ('STREETLIGHT', 'Streetlight'),
        ('TREES', 'Trees / Environment'),
        ('OTHER', 'Other'),
    ]

    SENTIMENT_CHOICES = [
        ('Neutral', 'Neutral'),
        ('Frustrated', 'Frustrated'),
        ('Furious_Threatening', 'Furious / Threatening'),
    ]

    SEASONALITY_CHOICES = [
        ('Monsoon_Related', 'Monsoon Related'),
        ('Summer_Drought', 'Summer Drought'),
        ('Year_Round', 'Year Round'),
    ]

    # Reporter data
    reporter = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='reported_issues'
    )
    is_pseudonymous = models.BooleanField(default=False)

    # Evidence and details
    issue_photo = models.ImageField(upload_to='issue_photos/', blank=True, null=True)
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="Raw citizen text (Manglish/English/Malayalam)")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    image_hash = models.CharField(max_length=64, blank=True, default='')

    # Location data
    latitude = models.FloatField()
    longitude = models.FloatField()
    landmark_note = models.TextField(blank=True, default='')
    ward_name = models.CharField(max_length=100, blank=True, default='')
    panchayat_name = models.CharField(max_length=100, blank=True, default='')

    # Pipeline and AI metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    priority_score = models.IntegerField(default=0)
    is_public_hazard = models.BooleanField(default=False)
    ai_formal_summary = models.TextField(blank=True, default='')
    ai_departments = models.JSONField(default=list, blank=True)
    ai_sentiment = models.CharField(
        max_length=30, choices=SENTIMENT_CHOICES, blank=True, default=''
    )
    ai_seasonality = models.CharField(
        max_length=30, choices=SEASONALITY_CHOICES, blank=True, default=''
    )
    ai_processed = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True, default='')

    # Community and following
    followers = models.ManyToManyField(CustomUser, related_name='following_issues', blank=True)

    # Resolution proof
    assigned_worker = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tasks', limit_choices_to={'role': 'FIELD_WORKER'}
    )
    resolution_photo = models.ImageField(upload_to='resolution_photos/', blank=True, null=True)
    worker_note = models.TextField(blank=True, default='')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority_score', '-created_at']

    def __str__(self):
        return f"#{self.id} — {self.title} [{self.status}]"

    def get_display_reporter(self):
        """Returns 'Concerned Citizen' if pseudonymous, else real name."""
        if self.is_pseudonymous:
            return 'Concerned Citizen'
        return f"{self.reporter.first_name} {self.reporter.last_name}"
