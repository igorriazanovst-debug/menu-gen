from django.urls import path

from .views import FamilyAttachAccountView  # MG_MANAGEDMEMBER
from .views import FamilyChoicesView  # MG_ACTIVEFAMILY
from .views import FamilyCreateManagedMemberView  # MG_MANAGEDMEMBER
from .views import FamilyInviteCancelView  # MG_FAMINVITE
from .views import FamilyInviteRespondView  # MG_FAMINVITE
from .views import FamilyInvitesView  # MG_FAMINVITE
from .views import FamilySwitchView  # MG_ACTIVEFAMILY
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
    # MG_ACTIVEFAMILY: где я состою и за каким столом сижу сейчас.
    path("choices/", FamilyChoicesView.as_view(), name="family-choices"),
    path("switch/", FamilySwitchView.as_view(), name="family-switch"),
    # MG_FAMINVITE: приглашение, на которое отвечают.
    path("invites/", FamilyInvitesView.as_view(), name="family-invites"),
    path("invites/<int:invite_id>/respond/", FamilyInviteRespondView.as_view(), name="family-invite-respond"),
    path("invites/<int:invite_id>/", FamilyInviteCancelView.as_view(), name="family-invite-cancel"),
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
