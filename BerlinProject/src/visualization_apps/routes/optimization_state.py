from typing import Any, Dict
import threading
import gc
from mlf_utils.singleton import Singleton


class OptimizationState(metaclass=Singleton):
    """
    Thread-safe optimization state management.

    MEMORY OPTIMIZATION: Includes explicit garbage collection on state reset
    and methods to clear heavy data structures between epochs.
    """



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
        """
        Reset optimization-specific state while preserving config paths.

        MEMORY OPTIMIZATION: Explicitly clears lists and triggers garbage collection
        to free memory from previous optimization runs.
        """
        with self._lock:
            ga_config_path_temp = self._state.get('ga_config_path_temp')
            data_config_path_temp = self._state.get('data_config_path_temp')

            # MEMORY OPTIMIZATION: Clear large lists before replacing to help GC
            if self._state.get('elites'):
                self._state['elites'].clear()
            if self._state.get('best_individuals_log'):
                self._state['best_individuals_log'].clear()
            if self._state.get('processed_indicators'):
                self._state['processed_indicators'].clear()

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

        # MEMORY OPTIMIZATION: Force garbage collection after clearing large data
        gc.collect()

    def trim_elites(self, max_elites: int = 20) -> None:
        """
        Trim elites list to keep only top N individuals.

        This prevents unbounded elite accumulation during long optimization runs.

        Args:
            max_elites: Maximum number of elites to retain (default: 20)
        """
        with self._lock:
            elites = self._state.get('elites', [])
            if len(elites) > max_elites:
                # Keep only top elites (already sorted by fitness)
                self._state['elites'] = elites[:max_elites]

    def clear_heavy_data(self) -> None:
        """
        Clear heavy data structures to free memory during optimization.

        Call this between epochs if memory pressure is high.
        """
        with self._lock:
            # Clear elites but keep the state structure
            if self._state.get('elites'):
                self._state['elites'] = []

        gc.collect()



    def is_running(self) -> bool:
        """Thread-safe check if optimization is running"""
        with self._lock:
            return self._state.get('running', False)



    def is_paused(self) -> bool:
        """Thread-safe check if optimization is paused"""
        with self._lock:
            return self._state.get('paused', False)
