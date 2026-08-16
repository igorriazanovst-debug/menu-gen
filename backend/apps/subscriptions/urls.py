from django.urls import path

from .views import (
    CancelSubscriptionView,
    CurrentSubscriptionView,
    PlanOfferListView,
    RedeemPromoView,
    SubscribeView,
    SubscriptionPlanListView,
)

urlpatterns = [
    path("plans/", SubscriptionPlanListView.as_view(), name="subscription-plans"),
    # MG_PAYPERIOD: периоды и цены — из чего выбирает пользователь
    path("offers/", PlanOfferListView.as_view(), name="subscription-offers"),
    path("current/", CurrentSubscriptionView.as_view(), name="subscription-current"),
    path("subscribe/", SubscribeView.as_view(), name="subscription-subscribe"),
    path("cancel/", CancelSubscriptionView.as_view(), name="subscription-cancel"),
    path("promo/redeem/", RedeemPromoView.as_view(), name="subscription-promo-redeem"),
]
