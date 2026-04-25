"""WebSocket URL routing for the CRM app."""

from django.urls import re_path

from crm.consumers import FirmConsumer

websocket_urlpatterns = [
    re_path(r'^ws/firms/(?P<firm_id>[^/]+)/$', FirmConsumer.as_asgi()),
]
