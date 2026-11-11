from enum import Enum


class ApplicationState(str, Enum):
    UNKNOWN = "UNKNOWN"
    DISCOVERED = "DISCOVERED"
    INSTALLED = "INSTALLED"
    RUNNING = "RUNNING"
    CONNECTED = "CONNECTED"
    OPERATIONAL = "OPERATIONAL"