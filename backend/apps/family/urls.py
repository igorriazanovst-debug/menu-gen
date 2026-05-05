from django.urls import path

from .views import FamilyDetailView, FamilyInviteView, FamilyRemoveMemberView, FamilyMemberUpdateView, FamilyMemberTargetHistoryView, FamilyMemberTargetResetView

urlpatterns = [
    path("", FamilyDetailView.as_view(), name="family-detail"),
    path("invite/", FamilyInviteView.as_view(), name="family-invite"),
    path("members/<int:member_id>/", FamilyRemoveMemberView.as_view(), name="family-remove-member"),
    path("members/<int:member_id>/update/", FamilyMemberUpdateView.as_view(), name="family-update-member"),
    # MG_205UI_V_family_urls = 1
    path("members/<int:member_id>/targets/<str:field>/history/",
         FamilyMemberTargetHistoryView.as_view(),
         name="family-member-target-history"),
    path("members/<int:member_id>/targets/<str:field>/reset/",
         FamilyMemberTargetResetView.as_view(),
         name="family-member-target-reset"),

]
