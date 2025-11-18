class _BaseRouter:
    def __init__(self, *args, **kwargs):
        self._urls = []

    def register(self, *args, **kwargs):
        return None

    @property
    def urls(self):
        return self._urls


class SimpleRouter(_BaseRouter):
    pass


class NestedSimpleRouter(_BaseRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
