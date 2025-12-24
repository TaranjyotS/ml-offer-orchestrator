from fastapi import FastAPI


class BaseApplication(FastAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_api_route("/health", self.health, methods=["GET"])

    def health(self):
        return {"status": "ok"}
