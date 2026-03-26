from django.urls import path

from .views import MacroDashboardView


urlpatterns = [
    path("macro/dashboard/", MacroDashboardView.as_view(), name="macro-dashboard"),
]
