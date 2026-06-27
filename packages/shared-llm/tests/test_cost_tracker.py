from shared_llm.cost_tracker import CostTracker

def test_cost_tracker_known_model():
    tracker = CostTracker()
    cost = tracker.calculate_cost("openai", "gpt-4-turbo", 1000, 2000)
    # input = 1000 * 0.00001 = 0.01
    # output = 2000 * 0.00003 = 0.06
    # total = 0.07
    assert cost == 0.07

def test_cost_tracker_substring_match():
    tracker = CostTracker()
    cost = tracker.calculate_cost("openai", "gpt-4o-2024-05-13", 1000, 2000)
    # input = 1000 * 0.000005 = 0.005
    # output = 2000 * 0.000015 = 0.03
    # total = 0.035
    assert cost == 0.035

def test_cost_tracker_fallback():
    tracker = CostTracker()
    cost = tracker.calculate_cost("anthropic", "claude-3-unknown-model", 1000, 2000)
    # claude-3-sonnet rates: input 0.000003, output 0.000015
    # input = 1000 * 0.000003 = 0.003
    # output = 2000 * 0.000015 = 0.03
    # total = 0.033
    assert cost == 0.033
