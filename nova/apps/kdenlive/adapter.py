from nova.apps.base import ApplicationAdapter, ProjectInfo

class KdenliveAdapter(ApplicationAdapter):
    app_id = "kdenlive"
    display_name = "Kdenlive"
    def detect_project(self, path=None):
        return None
    def inspect(self):
        return {"connected": False, "note": "not implemented"}