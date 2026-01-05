from typing import Any, Dict
import threading
from mlf_utils.singleton import Singleton


class OptimizationState(metaclass=Singleton):
    """Thread-safe optimization state management"""



    def __init__(self):
        self._lock = threading.RLock()
        self._state = {
            'running': False,
            'paused': False,
            'current_generation': 0,
            'total_generations': 0,
            'best_individuals_log': [],
            'last_best_individual': None,
            'elites': [],
            'thread': None,
            'heartbeat_thread': None,
            'ga_instance': None,
            'io_instance': None,
            'test_name': None,
            'ga_config_path': None,
            'data_config_path_temp': None,
            'ga_config_path_temp': None,
            'timestamp': None,
            'processed_indicators': []
        }



    def get(self, key: str, default: Any = None) -> Any:
        """Thread-safe get operation"""
        with self._lock:
            return self._state.get(key, default)



    def set(self, key: str, value: Any) -> None:
        """Thread-safe set operation"""
        with self._lock:
            self._state[key] = value



    def update(self, updates: Dict[str, Any]) -> None:
        """Thread-safe bulk update operation"""
        with self._lock:
            self._state.update(updates)



    def reset_optimization_state(self) -> None:
        print("WOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO")
        """Reset optimization-specific state while preserving config paths"""
        with self._lock:
            ga_config_path_temp = self._state.get('ga_config_path_temp')
            data_config_path_temp = self._state.get('data_config_path_temp')

            self._state.update({
                'running': False,
                'paused': False,
                'current_generation': 0,
                'total_generations': 0,
                'best_individuals_log': [],
                'last_best_individual': None,
                'elites': [],
                'thread': None,
                'heartbeat_thread': None,
                'ga_instance': None,
                'io_instance': None,
                'test_name': None,
                'ga_config_path': None,
                'timestamp': None,
                'processed_indicators': []
            })

            if ga_config_path_temp:
                self._state['ga_config_path_temp'] = ga_config_path_temp
            if data_config_path_temp:
                self._state['data_config_path_temp'] = data_config_path_temp



    def is_running(self) -> bool:
        """Thread-safe check if optimization is running"""
        with self._lock:
            return self._state.get('running', False)



    def is_paused(self) -> bool:
        """Thread-safe check if optimization is paused"""
        with self._lock:
            return self._state.get('paused', False)
