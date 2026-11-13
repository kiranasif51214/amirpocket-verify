import unittest
from types import SimpleNamespace
from reply_matching import correlated_kind


def msg(text, mid=102, sender=50, reply_to=None):
    return SimpleNamespace(text=text, id=mid, sender_id=sender, reply_to_msg_id=reply_to)


class ReplyMatchingTests(unittest.TestCase):
    def test_actual_wrong_uid_from_railway_is_never_used(self):
        self.assertEqual(correlated_kind(msg("UID: `143331823`\nBalance: `$15.04`"), 50, 100, "140405761"), "mismatch")

    def test_matching_owner_sample_is_accepted(self):
        self.assertEqual(correlated_kind(msg("UID: 140405761\nBalance: $4.45\nSum of deposits: $517.00"), 50, 100, "140405761"), "verified")

    def test_old_messages_are_ignored_even_with_matching_uid(self):
        self.assertEqual(correlated_kind(msg("UID: 140405761", mid=99), 50, 100, "140405761"), "ignore")

    def test_replies_to_another_query_are_ignored(self):
        self.assertEqual(correlated_kind(msg("⚠️ User not found", reply_to=90), 50, 100, "140405761"), "ignore")

    def test_other_senders_are_ignored(self):
        self.assertEqual(correlated_kind(msg("UID: 140405761", sender=51), 50, 100, "140405761"), "ignore")

    def test_fresh_not_found_is_accepted(self):
        self.assertEqual(correlated_kind(msg("⚠️ User not found", reply_to=100), 50, 100, "140405761"), "not_found")

    def test_help_prompt_is_not_a_verdict(self):
        self.assertEqual(correlated_kind(msg("⚠️ Enter the UID: /user {uid}"), 50, 100, "140405761"), "command_hint")
        self.assertEqual(correlated_kind(msg("Your ID: 8506528935"), 50, 100, "140405761"), "ignore")


if __name__ == "__main__":
    unittest.main()