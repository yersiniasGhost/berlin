from environments.simple_position import SimplePosition
from environments.inout_position import InoutPosition
def get_state_class(config: dict):
    state_config = config.get('state', {})
    klass = state_config.get('klass')

    if klass == "SimplePosition":
        return SimplePosition()
    elif klass == "InoutPosition":
        return InoutPosition()
    else:
        raise ValueError(f"Unknown state class: {klass}")