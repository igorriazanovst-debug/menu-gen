from django.urls import path

from .views import FamilyDetailView, FamilyInviteView, FamilyRemoveMemberView, FamilyMemberUpdateView

urlpatterns = [
    path("", FamilyDetailView.as_view(), name="family-detail"),
    path("invite/", FamilyInviteView.as_view(), name="family-invite"),
    path("members/<int:member_id>/", FamilyRemoveMemberView.as_view(), name="family-remove-member"),
    path("members/<int:member_id>/update/", FamilyMemberUpdateView.as_view(), name="family-update-member"),
]
