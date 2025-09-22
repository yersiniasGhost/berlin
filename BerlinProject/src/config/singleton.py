
import threading


class Singleton(type):
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        # Use class name instead of class object to handle import path variations
        class_key = cls.__name__
        if class_key not in cls._instances:
            with cls._lock:
                if class_key not in cls._instances:
                    cls._instances[class_key] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[class_key]
