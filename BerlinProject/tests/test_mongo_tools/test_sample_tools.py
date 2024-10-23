import unittest

from environments.tick_data import TickData

from mongo_tools.sample_tools import SampleTools


class TestSampleTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        json_profile = [{
            "profile_id": "66e3499280c8e93a7756fbd1",
            "number": 5
        },
            {
                "profile_id": "66e34a036bf640360fdd7326",
                "number": 2
            }]

        # Create SampleTools instance
        cls.sample_tools = SampleTools.get_tools(json_profile)

    # def test_tick_count_equals_700(self):
    #     """Test that the total number of ticks equals 700"""
    #     count = sum(1 for _ in self.sample_tools.serve_next_tick())
    #     self.assertEqual(count, 700, f"Expected 700 ticks, but got {count}")

    def test_tick_data_structure(self):
        """Test that each tick has the correct data structure"""
        for tick in self.sample_tools.serve_next_tick():
            self.assertIsInstance(tick, TickData)  # Assuming TickData is the class used
            self.assertTrue(hasattr(tick, 'open'))
            self.assertTrue(hasattr(tick, 'high'))
            self.assertTrue(hasattr(tick, 'low'))
            self.assertTrue(hasattr(tick, 'close'))

    def test_get_specific_sample(self):

        data = SampleTools.get_specific_sample("66e1f09f7c6789752c190ca0")
        samples = data.samples
        self.assertEqual(len(samples), 100)

    def test_get_next(self):

        data = SampleTools.get_specific_sample("66e1f09f7c6789752c190ca0")
        tick = data.get_next()
        cnt = 0
        while (tick):
            cnt += 1
            tick = data.get_next()
        self.assertEqual(cnt, len(data.samples))

    def test_get_samples2(self):

        data = {
            "profile_id": "66e34a036bf640360fdd7326",
            "number": 5
        }

        b = SampleTools.get_samples2(data)
        for i in range(3):
            cnt = 0
            tick = b.get_next2()
            while(tick):
                cnt += 1
                tick = b.get_next2()
            # assert cnt
            # print(cnt)
            b.reset_index()



    def test_get_next2(self):
        data = {
            "profile_id": "66e34a036bf640360fdd7326",
            "number": 5
        }

        sample_tools = SampleTools.get_samples2(data)

        current_sample = 1
        tick_count = 0
        total_ticks = 0

        print(f"\nStarting to process Sample {current_sample}")

        tick = sample_tools.get_next2()
        while tick is not None:
            tick_count += 1
            total_ticks += 1

            print(
                f"Sample {current_sample}, Tick {tick_count}: Open: {tick.open:.2f}, High: {tick.high:.2f}, Low: {tick.low:.2f}, Close: {tick.close:.2f}")

            next_tick = sample_tools.get_next2()

            if next_tick is None or sample_tools.sample_index != current_sample - 1:
                print(f"Finished processing Sample {current_sample} with {tick_count} ticks")
                if next_tick is not None:
                    current_sample += 1
                    tick_count = 0
                    print(f"\nStarting to process Sample {current_sample}")

            tick = next_tick

        print(f"\nTotal processed: {current_sample} samples, {total_ticks} ticks")

        self.assertEqual(current_sample, 5, "Should have processed 5 samples")
        self.assertGreater(total_ticks, 5, "Should have processed more than 5 ticks in total")
        self.assertIsNone(sample_tools.get_next2(), "Should return None after processing all ticks")

    def test_serve_next_tick(self):

