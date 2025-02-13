from abc import ABC, abstractmethod

class AIModelStrategy(ABC):
    @abstractmethod
    def get_response(self, prompt: str) -> str | None:
        pass

    def get_image_response(self, prompt: str) -> str | None:
        pass

    @abstractmethod
    def get_current_model(self) -> str:
        pass
