import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from youth_policies import age_on, candidate, new_matches, save_seen


class YouthPolicyTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2026, 9, 28)
        self.policy = {
            "plcyNo": "20260928001", "plcyNm": "서울 청년 공공임대주택",
            "plcyAprvSttsCd": "0044002", "lclsfNm": "주거", "zipCd": "11000",
            "sprtTrgtMinAge": "19", "sprtTrgtMaxAge": "29", "schoolCd": "0049005",
            "aplyPrdSeCd": "0057001", "aplyYmd": "2026.09.20 ~ 2026.10.05",
        }

    def test_age_changes_on_birthday(self):
        self.assertEqual(age_on("2003-10-02", dt.date(2026, 10, 1)), 22)
        self.assertEqual(age_on("2003-10-02", dt.date(2026, 10, 2)), 23)

    def test_location_age_school_and_deadline(self):
        self.assertIsNotNone(candidate(self.policy, 23, self.today))
        self.assertIsNone(candidate({**self.policy, "zipCd": "26000"}, 23, self.today))
        self.assertIsNone(candidate(self.policy, 30, self.today))
        self.assertIsNone(candidate({**self.policy, "schoolCd": "0049007"}, 23, self.today))
        self.assertIsNone(candidate({**self.policy, "aplyYmd": "2026.09.01 ~ 2026.09.20"}, 23, self.today))
        self.assertIsNone(candidate({**self.policy, "aplyYmd": "2026.10.01 ~ 2026.10.20"}, 23, self.today))

    def test_initial_baseline_then_only_new_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "seen.json"
            first = [{"id": "a"}]
            fresh, ids = new_matches(first, state)
            self.assertEqual(fresh, [])
            save_seen(state, ids)
            fresh, ids = new_matches(first + [{"id": "b"}], state)
            self.assertEqual([item["id"] for item in fresh], ["b"])
            self.assertEqual(set(json.loads(state.read_text())["seen"]), {"a"})
            save_seen(state, ids)
            self.assertEqual(new_matches(first + [{"id": "b"}], state)[0], [])


if __name__ == "__main__":
    unittest.main()
