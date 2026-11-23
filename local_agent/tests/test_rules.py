import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import rules


def test_signals():
    s = rules.find_signals("We're hiring a receptionist. Call us to book.")
    names = [x["signal"] for x in s]
    assert "hiring" in names
    assert "no_online_booking" in names


def test_reply_unsubscribe():
    r = rules.classify_reply_rules("please remove me from your list")
    assert r["label"] == "unsubscribe"


def test_reply_ooo():
    r = rules.classify_reply_rules("I am out of office till Monday")
    assert r["label"] == "out_of_office"


def test_score():
    icp = {"industries": ["Dental clinic"], "company_size": {"min": 5, "max": 50}, "decision_makers": ["Owner"]}
    p = {"industry": "Dental clinic", "employees": 12, "contact_role": "Owner"}
    r = rules.score_rules(p, icp, [{"signal": "hiring"}])
    assert r["score"] == 75
