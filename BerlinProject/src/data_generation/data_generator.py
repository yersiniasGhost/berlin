import numpy as np
from .profile import Profile


class DataGenerator:

    def __init__(self, profile: Profile):
        self.profile = profile
        self.data_profiles = []

    # Generate the profile data from the given definitions,
    # Populates data_profiles
    def generate_data(self, number_of_profiles: int, length: int, start_value: float) -> None:

        for _ in range(number_of_profiles):
            b = start_value
            profile = []
            for idx, section in enumerate(self.profile.get_sections()):
                # We expect each section to contain:
                # trend: [ slope, stddev]
                # variation: float   # stddev or randomness to data
                # length of trend as float percentage of the profile
                if not "trend" in section.keys():
                    raise ValueError("Section doesn't have a trend")

                # Create the section of the profile.  We need a start value
                # And calculate number of candles to create.from
                lf_var = section['length_fraction'][1]
                section_length = section['length_fraction'][0] + np.random.uniform(-lf_var, lf_var)
                number_of_candles = int(length * section_length)
                # If we are the last section, ensure that we have the full number of candles
                if idx == self.profile.number_of_sections()-1:
                    number_of_candles = length - len(profile)

                # calculate a trend which is simple y = mx + b
                # m is the trend value over the number_of_candles
                m_delta = section['trend'][1]
                delta = section['trend'][0] + np.random.uniform(-m_delta, m_delta)
                m = delta / (number_of_candles-1)
                price_variability= section["price_variation"]
                for n in range(number_of_candles):
                    if n >= number_of_candles:
                        break
                    close = b + m * n + np.random.uniform(-price_variability, price_variability)
                    profile.append(close)
                b = profile[-1]

            self.data_profiles.append(profile)

    def get_profiles(self) -> list:
        for p in self.data_profiles:
            yield p