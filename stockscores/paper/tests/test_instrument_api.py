from django.test import TestCase
from rest_framework.test import APIRequestFactory

from paper.api.views import InstrumentViewSet
from paper.models import Instrument


class InstrumentApiTests(TestCase):
    def setUp(self):
        Instrument.objects.create(symbol="AAPL", asset_class="equity")
        Instrument.objects.create(symbol="MSFT", asset_class="equity")
        self.factory = APIRequestFactory()

    def test_list_and_filter(self):
        view = InstrumentViewSet.as_view({"get": "list"})
        request = self.factory.get("/paper/instruments/?q=aap")
        response = view(request)
        self.assertEqual(response.status_code, 200)
        symbols = [row["symbol"] for row in response.data]
        self.assertIn("AAPL", symbols)
        self.assertNotIn("MSFT", symbols)
