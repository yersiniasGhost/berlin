import os


def get_environment_variable(varname: str) -> str:
    return os.environ.get(varname)


def get_required_env_var(varname: str) -> str:
    value = os.environ.get(varname)
    if not value:
        raise ValueError(f"Environment variable is not set: {varname}")
    return value
