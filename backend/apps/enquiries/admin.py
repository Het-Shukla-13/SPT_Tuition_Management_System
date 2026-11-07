from django.contrib import admin

from apps.enquiries.models import AdmissionEnquiry


@admin.register(AdmissionEnquiry)
class AdmissionEnquiryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "student_name", "parent_name", "phone", "status"]
    list_filter = ["status"]
    search_fields = ["student_name", "parent_name", "phone", "email"]
