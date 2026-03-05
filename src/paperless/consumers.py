import json

from asgiref.sync import async_to_sync
from channels.exceptions import AcceptConnection
from channels.exceptions import DenyConnection
from channels.generic.websocket import WebsocketConsumer


class StatusConsumer(WebsocketConsumer):
    def _authenticated(self):
        return "user" in self.scope and self.scope["user"].is_authenticated

    def _can_view(self, data):
        user = self.scope.get("user") if self.scope.get("user") else None
        owner_id = data.get("owner_id")
        users_can_view = data.get("users_can_view", [])
        groups_can_view = data.get("groups_can_view", [])
        # RKC: Fix UI hang when uploading documents via web interface (AI OCR investigation)
        # Match frontend behavior: if no owner_id is set, allow all authenticated users
        # to view the message. This prevents SUCCESS messages from being silently
        # filtered out when owner_id=None, which caused the UI to hang indefinitely
        # waiting for a completion signal that never arrived.
        return (
            not owner_id
            or user.is_superuser
            or user.id == owner_id
            or user.id in users_can_view
            or any(
                user.groups.filter(pk=group_id).exists() for group_id in groups_can_view
            )
        )

    def connect(self):
        if not self._authenticated():
            raise DenyConnection
        else:
            async_to_sync(self.channel_layer.group_add)(
                "status_updates",
                self.channel_name,
            )
            raise AcceptConnection

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            "status_updates",
            self.channel_name,
        )

    def status_update(self, event):
        if not self._authenticated():
            self.close()
        else:
            if self._can_view(event["data"]):
                self.send(json.dumps(event))

    def documents_deleted(self, event):
        if not self._authenticated():
            self.close()
        else:
            self.send(json.dumps(event))
