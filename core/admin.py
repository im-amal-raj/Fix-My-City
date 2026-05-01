from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, CommunityIssue


# Custom User Admin
class CustomUserAdmin(UserAdmin):
    """Admin panel for managing users, roles, and civic points."""
    model = CustomUser
    list_display = ['username', 'first_name', 'last_name', 'role', 'civic_points', 'is_active']
    list_filter = ['role', 'is_active', 'is_deactivated']
    list_editable = ['role', 'civic_points']

    # Add our custom fields to the user edit form
    fieldsets = UserAdmin.fieldsets + (
        ('FixMyCity Info', {
            'fields': ('role', 'civic_points', 'is_deactivated', 'deletion_requested_at'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('FixMyCity Info', {
            'fields': ('role', 'civic_points'),
        }),
    )


# Community Issue Admin
class CommunityIssueAdmin(admin.ModelAdmin):
    """Admin panel for managing civic issue tickets."""
    list_display = [
        'id', 'title', 'status', 'priority_score', 'category',
        'ward_name', 'reporter', 'assigned_worker', 'created_at'
    ]
    list_filter = ['status', 'category', 'is_public_hazard', 'ai_processed']
    search_fields = ['title', 'description', 'landmark_note', 'ward_name']
    list_editable = ['status', 'priority_score']
    readonly_fields = ['created_at', 'updated_at', 'image_hash']

    fieldsets = (
        ('Basic Info', {
            'fields': ('reporter', 'title', 'description', 'category', 'is_pseudonymous')
        }),
        ('Evidence', {
            'fields': ('issue_photo', 'image_hash')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'landmark_note', 'ward_name', 'panchayat_name')
        }),
        ('AI Triage Data', {
            'fields': (
                'ai_formal_summary', 'priority_score', 'is_public_hazard',
                'ai_departments', 'ai_sentiment', 'ai_seasonality', 'ai_processed'
            )
        }),
        ('Status & Assignment', {
            'fields': ('status', 'assigned_worker', 'rejection_reason')
        }),
        ('Resolution', {
            'fields': ('resolution_photo', 'worker_note')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(CommunityIssue, CommunityIssueAdmin)

# Customize the admin site header
admin.site.site_header = "FixMyCity Admin Panel"
admin.site.site_title = "FixMyCity"
admin.site.index_title = "System Administration"
