from nova.apps.base import ApplicationAdapter, ProjectInfo

class FLStudioAdapter(ApplicationAdapter):
    app_id = "flstudio"
    display_name = "FL Studio"
    def detect_project(self, path=None):
        return None
    def inspect(self):
        return {"connected": False, "note": "not implemented"}