
from abc import ABC, abstractmethod


class AIProvider(ABC):

    @abstractmethod
    def list_models(self):
        """Return models supported by this provider."""
        pass

    @abstractmethod
    def generate_response(self, messages, model):
        """Generate a response using the selected model."""
        pass

    @abstractmethod
    def test_connection(self):
        """Check whether provider credentials and connection work."""
        pass
