from django.urls import path

from .views import (
    CancelSubscriptionView,
    CurrentSubscriptionView,
    RedeemPromoView,
    SubscribeView,
    SubscriptionPlanListView,
)

urlpatterns = [
    path("plans/", SubscriptionPlanListView.as_view(), name="subscription-plans"),
    path("current/", CurrentSubscriptionView.as_view(), name="subscription-current"),
    path("subscribe/", SubscribeView.as_view(), name="subscription-subscribe"),
    path("cancel/", CancelSubscriptionView.as_view(), name="subscription-cancel"),
    path("promo/redeem/", RedeemPromoView.as_view(), name="subscription-promo-redeem"),
]
