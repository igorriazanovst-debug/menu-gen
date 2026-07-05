from django.urls import path

from .views import FamilyAttachAccountView  # MG_MANAGEDMEMBER
from .views import FamilyCreateManagedMemberView  # MG_MANAGEDMEMBER
from .views import (
    FamilyDetailView,
    FamilyInviteView,
    FamilyMemberTargetHistoryView,
    FamilyMemberTargetResetView,
    FamilyMemberUpdateView,
    FamilyRemoveMemberView,
)

urlpatterns = [
    path("", FamilyDetailView.as_view(), name="family-detail"),
    path("invite/", FamilyInviteView.as_view(), name="family-invite"),
    # MG_MANAGEDMEMBER: add a member card without an invitation.
    path(
        "members/create-managed/",
        FamilyCreateManagedMemberView.as_view(),
        name="family-create-managed-member",
    ),
    path("members/<int:member_id>/", FamilyRemoveMemberView.as_view(), name="family-remove-member"),
    path(
        "members/<int:member_id>/attach-account/",
        FamilyAttachAccountView.as_view(),
        name="family-attach-account",
    ),
    path("members/<int:member_id>/update/", FamilyMemberUpdateView.as_view(), name="family-update-member"),
    # MG_205UI_V_family_urls = 1
    path(
        "members/<int:member_id>/targets/<str:field>/history/",
        FamilyMemberTargetHistoryView.as_view(),
        name="family-member-target-history",
    ),
    path(
        "members/<int:member_id>/targets/<str:field>/reset/",
        FamilyMemberTargetResetView.as_view(),
        name="family-member-target-reset",
    ),
]
