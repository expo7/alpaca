# project/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from paper.api.api_urls import router as paper_router

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("ranker.urls")),
    path("api/", include(paper_router.urls)),
    # JWT
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
