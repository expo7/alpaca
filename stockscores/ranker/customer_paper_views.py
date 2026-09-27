from django.db import IntegrityError
from django.http import HttpResponseRedirect
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .customer_paper import CustomerPaperError, available, begin_connection, complete_connection
from .models import CustomerPaperConnection


class StaffPaperPermission(permissions.BasePermission):
    """Keep the experimental brokerage surface invisible to ordinary customers."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser))


class CustomerPaperConnectionView(APIView):
    permission_classes = [StaffPaperPermission]

    def get(self, request):
        connection = CustomerPaperConnection.objects.filter(user=request.user).first()
        return Response({
            "available": available(), "connected": connection is not None,
            "account_suffix": connection.alpaca_account_id[-4:] if connection else None,
            "execution_enabled": False,
        })

    def delete(self, request):
        CustomerPaperConnection.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerPaperConnectView(APIView):
    permission_classes = [StaffPaperPermission]

    def post(self, request):
        try:
            url = begin_connection(request.user)
        except CustomerPaperError:
            return Response({"detail": "Paper connection is not available yet."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"authorize_url": url})


class CustomerPaperCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # The one-use state ties this callback to the staff user who initiated it.
        try:
            complete_connection(request.query_params.get("code"), request.query_params.get("state"))
        except (CustomerPaperError, IntegrityError):
            return HttpResponseRedirect("/signals?alpaca=connection-failed")
        return HttpResponseRedirect("/signals?alpaca=connected")
