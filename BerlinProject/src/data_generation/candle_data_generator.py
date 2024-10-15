from typing import List, Dict, Any
import numpy as np
from bson import ObjectId
from pymongo import MongoClient

from models.profile import Profile


class CandleDataGenerator:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.data_profiles = []

    def generate_data(self, number_of_profiles: int, length: int, start_value: float,
                      open_factor: float, high_factor: float, low_factor: float) -> None:
        for _ in range(number_of_profiles):
            b = start_value
            profile_data = []
            for idx, section in enumerate(self.profile.definition):
                lf_var = section.length_fraction[1]
                section_length = section.length_fraction[0] + np.random.uniform(-lf_var, lf_var)
                number_of_candles = int(length * section_length)
                number_of_sections = len(self.profile.definition)
                if idx == number_of_sections - 1:
                    number_of_candles = length - len(profile_data)

                m_delta = section.trend[1]
                delta = section.trend[0] + np.random.uniform(-m_delta, m_delta)
                m = delta / (number_of_candles - 1)
                price_variability = section.price_variation

                for n in range(number_of_candles):
                    if n >= number_of_candles:
                        break

                    close = b + m * n + np.random.uniform(-price_variability, price_variability)
                    open = close * (1 + np.random.uniform(-open_factor, open_factor))
                    high = max(open, close) * (1 + np.random.uniform(0, high_factor))
                    low = min(open, close) * (1 - np.random.uniform(0, low_factor))

                    profile_data.append((open, high, low, close))

                b = profile_data[-1][3]  # Use the close price as the base for the next section

            stats = self.calculate_stats(profile_data)
            self.data_profiles.append({
                'data': profile_data,
                'stats': stats
            })

    def calculate_stats(self, profile_data: List[tuple]) -> Dict[str, Dict[str, float]]:
        stats = {}
        for i, field in enumerate(['open', 'high', 'low', 'close']):
            values = [candle[i] for candle in profile_data]
            stats[field] = {
                'min': min(values),
                'max': max(values),
                'sd': np.std(values)
            }
        return stats

    def get_profiles(self) -> List[Dict[str, Any]]:
        return self.data_profiles

    def save_to_database(self):
        raise ValueError("THIS SHOULD NOT BE USED... TODO: delete this methos and save from ProfileTools")
        client = MongoClient('mongodb://localhost:27017/')
        db = client['MTA_devel']
        collection = db['Samples']

        # Determine the profile identifier
        if hasattr(self.profile, '_id'):
            profile_id = self.profile._id
        elif hasattr(self.profile, 'document_id'):
            profile_id = self.profile.document_id
        else:
            # If we can't find an id attribute, let's print the profile object to see what attributes it has
            print("Profile attributes:", dir(self.profile))
            raise AttributeError("Unable to find id attribute in Profile object")

        for profile_data in self.data_profiles:
            document = {
                'profile_id': ObjectId(profile_id),  # Convert string ID to ObjectId
                'data': [
                    {'open': candle[0], 'high': candle[1], 'low': candle[2], 'close': candle[3]}
                    for candle in profile_data['data']
                ],
                'stats': profile_data['stats']
            }
            collection.insert_one(document)

        client.close()
        print(f"Saved {len(self.data_profiles)} documents to the database.")