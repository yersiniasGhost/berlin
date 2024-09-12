import numpy as np
from .profile import Profile


class CandleDataGenerator:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.data_profiles = []

    def generate_data(self, number_of_profiles: int, length: int, start_value: float,
                      open_factor: float, high_factor: float, low_factor: float) -> None:
        for _ in range(number_of_profiles):
            b = start_value
            profile = []
            for idx, section in enumerate(self.profile.get_sections()):
                if not "trend" in section.keys():
                    raise ValueError("Section doesn't have a trend")

                lf_var = section['length_fraction'][1]
                section_length = section['length_fraction'][0] + np.random.uniform(-lf_var, lf_var)
                number_of_candles = int(length * section_length)

                if idx == self.profile.number_of_sections() - 1:
                    number_of_candles = length - len(profile)

                m_delta = section['trend'][1]
                delta = section['trend'][0] + np.random.uniform(-m_delta, m_delta)
                m = delta / (number_of_candles - 1)
                price_variability = section["price_variation"]

                for n in range(number_of_candles):
                    if n >= number_of_candles:
                        break

                    close = b + m * n + np.random.uniform(-price_variability, price_variability)
                    open = close * (1 + np.random.uniform(-open_factor, open_factor))
                    high = max(open, close) * (1 + np.random.uniform(0, high_factor))
                    low = min(open, close) * (1 - np.random.uniform(0, low_factor))

                    profile.append((open, high, low, close))

                b = profile[-1][3]  # Use the close price as the base for the next section

            self.data_profiles.append(profile)

    def get_profiles(self) -> list:
        for p in self.data_profiles:
            yield p