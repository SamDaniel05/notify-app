from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "preferred_language", "display_name", "created_at")
    search_fields = ("user__username", "user__email", "display_name")
