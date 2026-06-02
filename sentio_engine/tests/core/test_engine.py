import pytest
import json
import copy
import datetime
from pathlib import Path
from unittest.mock import patch

from sentio_engine.core.engine import SentioEngine
from sentio_engine.schemas.sentio_pb2 import EmotionalState, Stimulus, Report


# ---------------------------------------------------------------------------
# Constants – never mutated directly; tests that need modified copies use
# copy.deepcopy() to avoid cross-test pollution.
# ---------------------------------------------------------------------------

BASE_EMOTIONS = {
    "радость": {
        "base_intensity": 0.1,
        "decay_rate": 0.95,
        "opposite": "грусть",
        "personality_influence": {"extraversion": 1.3, "agreeableness": 1.2, "neuroticism": 0.8},
    },
    "доверие": {
        "base_intensity": 0.2,
        "decay_rate": 0.99,
        "opposite": "отвращение",
        "personality_influence": {"agreeableness": 1.4, "conscientiousness": 1.1, "neuroticism": 0.7},
    },
    "страх": {
        "base_intensity": 0.05,
        "decay_rate": 0.98,
        "opposite": "злость",
        "personality_influence": {"neuroticism": 1.5, "extraversion": 0.8},
    },
    "удивление": {
        "base_intensity": 0.05,
        "decay_rate": 0.90,
        "opposite": "ожидание",
        "personality_influence": {"openness": 1.3},
    },
    "грусть": {
        "base_intensity": 0.05,
        "decay_rate": 0.98,
        "opposite": "радость",
        "personality_influence": {"neuroticism": 1.5, "extraversion": 0.7},
    },
    "отвращение": {
        "base_intensity": 0.0,
        "decay_rate": 0.97,
        "opposite": "доверие",
        "personality_influence": {"neuroticism": 1.2, "conscientiousness": 1.1, "agreeableness": 0.7},
    },
    "злость": {
        "base_intensity": 0.0,
        "decay_rate": 0.97,
        "opposite": "страх",
        "personality_influence": {"neuroticism": 1.4, "agreeableness": 0.6},
    },
    "ожидание": {
        "base_intensity": 0.1,
        "decay_rate": 0.96,
        "opposite": "удивление",
        "personality_influence": {"openness": 1.2, "conscientiousness": 1.1},
    },
}

BASE_PERSONALITY = {
    "openness": {"value": 0.5, "description": "Openness"},
    "conscientiousness": {"value": 0.5, "description": "Conscientiousness"},
    "extraversion": {"value": 0.5, "description": "Extraversion"},
    "agreeableness": {"value": 0.5, "description": "Agreeableness"},
    "neuroticism": {"value": 0.5, "description": "Neuroticism"},
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config_dir(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir(parents=True, exist_ok=True)

    with open(cfg / "emotions.json", "w", encoding="utf-8") as f:
        json.dump({"definitions": BASE_EMOTIONS}, f, ensure_ascii=False)

    with open(cfg / "drives.json", "w", encoding="utf-8") as f:
        json.dump({"definitions": {}}, f, ensure_ascii=False)

    with open(cfg / "engine_settings.json", "w", encoding="utf-8") as f:
        json.dump({"simulation_tick_seconds": 60, "dominance_factor": 0.5}, f)

    with open(cfg / "feelings.json", "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False)

    with open(cfg / "BeliefSystem.json", "w", encoding="utf-8") as f:
        json.dump({"personality": BASE_PERSONALITY}, f, ensure_ascii=False)

    return cfg


@pytest.fixture
def engine(config_dir):
    return SentioEngine(config_dir)


# ---------------------------------------------------------------------------
# Engine Initialization
# ---------------------------------------------------------------------------

class TestEngineInitialization:
    def test_loads_config_successfully(self, engine):
        assert len(engine.emotion_definitions) == 8
        assert engine.engine_settings["simulation_tick_seconds"] == 60
        assert engine.engine_settings["dominance_factor"] == 0.5
        assert len(engine.belief_system) == 5

    def test_missing_config_raises(self, tmp_path):
        cfg = tmp_path / "config"
        cfg.mkdir()
        with pytest.raises(FileNotFoundError):
            SentioEngine(cfg)

    def test_invalid_json_raises(self, tmp_path):
        cfg = tmp_path / "config"
        cfg.mkdir()
        for name in ("emotions.json", "drives.json", "engine_settings.json",
                      "feelings.json", "BeliefSystem.json"):
            (cfg / name).write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            SentioEngine(cfg)


# ---------------------------------------------------------------------------
# create_initial_state
# ---------------------------------------------------------------------------

class TestCreateInitialState:
    def test_all_emotions_at_base_intensity(self, engine):
        state = engine.create_initial_state()
        for emotion, params in BASE_EMOTIONS.items():
            assert state.emotions[emotion] == pytest.approx(params["base_intensity"])

    def test_primary_mood_set_to_dominating_highest(self, engine):
        state = engine.create_initial_state()
        expected_top = max(BASE_EMOTIONS, key=lambda e: BASE_EMOTIONS[e]["base_intensity"])
        assert state.primary_mood == f"dominating {expected_top}"

    def test_cause_is_system_initialization(self, engine):
        state = engine.create_initial_state()
        assert state.cause == "System initialization."


# ---------------------------------------------------------------------------
# _update_primary_mood
# ---------------------------------------------------------------------------

class TestUpdatePrimaryMood:
    def test_empty_emotions_returns_neutral(self, engine):
        state = EmotionalState()
        engine._update_primary_mood(state)
        assert state.primary_mood == "neutral"

    def test_returns_dominating_highest_emotion(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.9
        state.emotions["грусть"] = 0.1
        engine._update_primary_mood(state)
        assert state.primary_mood == "dominating радость"

    def test_tie_returns_first_max(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.5
        state.emotions["грусть"] = 0.5
        state.emotions["страх"] = 0.5
        engine._update_primary_mood(state)
        assert state.primary_mood in ("dominating радость", "dominating грусть", "dominating страх")


# ---------------------------------------------------------------------------
# _calculate_personality_modifier
# ---------------------------------------------------------------------------

class TestCalculatePersonalityModifier:
    def test_no_personality_influence_returns_one(self, engine):
        engine.emotion_definitions["_test_no_influence"] = {}
        assert engine._calculate_personality_modifier("_test_no_influence") == 1.0

    def test_neutral_personality_all_at_0_5_returns_one(self, engine):
        mod = engine._calculate_personality_modifier("радость")
        assert mod == pytest.approx(1.0)

    def test_high_trait_increases_modifier(self, config_dir):
        personality = copy.deepcopy(BASE_PERSONALITY)
        personality["extraversion"]["value"] = 1.0
        cfg = config_dir
        with open(cfg / "BeliefSystem.json", "w", encoding="utf-8") as f:
            json.dump({"personality": personality}, f, ensure_ascii=False)
        eng = SentioEngine(cfg)
        mod = eng._calculate_personality_modifier("радость")
        expected = 1.0 + (1.0 - 0.5) * (1.3 - 1.0)
        assert mod == pytest.approx(expected)

    def test_low_trait_decreases_modifier(self, config_dir):
        personality = copy.deepcopy(BASE_PERSONALITY)
        personality["extraversion"]["value"] = 0.0
        cfg = config_dir
        with open(cfg / "BeliefSystem.json", "w", encoding="utf-8") as f:
            json.dump({"personality": personality}, f, ensure_ascii=False)
        eng = SentioEngine(cfg)
        mod = eng._calculate_personality_modifier("радость")
        expected = 1.0 + (0.0 - 0.5) * (1.3 - 1.0)
        assert mod == pytest.approx(expected)

    def test_clamps_at_minimum_0_1(self, engine):
        engine.emotion_definitions["_test_clamp"] = {
            "personality_influence": {"neuroticism": 5.0}
        }
        engine.belief_system["neuroticism"]["value"] = 0.0
        mod = engine._calculate_personality_modifier("_test_clamp")
        assert mod == pytest.approx(0.1)

    def test_missing_trait_falls_back_to_0_5(self, engine):
        del engine.belief_system["extraversion"]
        mod = engine._calculate_personality_modifier("радость")
        assert mod == pytest.approx(1.0)

    def test_multiple_traits_accumulate(self, config_dir):
        personality = copy.deepcopy(BASE_PERSONALITY)
        personality["extraversion"]["value"] = 1.0
        personality["agreeableness"]["value"] = 1.0
        personality["neuroticism"]["value"] = 0.0
        cfg = config_dir
        with open(cfg / "BeliefSystem.json", "w", encoding="utf-8") as f:
            json.dump({"personality": personality}, f, ensure_ascii=False)
        eng = SentioEngine(cfg)
        mod = eng._calculate_personality_modifier("радость")
        e = 1.0 + (1.0 - 0.5) * (1.3 - 1.0) + (1.0 - 0.5) * (1.2 - 1.0) + (0.0 - 0.5) * (0.8 - 1.0)
        assert mod == pytest.approx(e)


# ---------------------------------------------------------------------------
# _decay_emotions
# ---------------------------------------------------------------------------

class TestDecayEmotions:
    def test_decay_toward_base(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.5
        engine._decay_emotions(state)
        expected = 0.1 + (0.5 - 0.1) * 0.95
        assert state.emotions["радость"] == pytest.approx(expected)

    def test_decay_all_emotions_no_dominance_interference(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.5
        state.emotions["удовольствие"] = 0.5
        engine.emotion_definitions["удовольствие"] = {
            "base_intensity": 0.1, "decay_rate": 0.95}
        engine._decay_emotions(state)
        expected = 0.1 + (0.5 - 0.1) * 0.95
        assert state.emotions["радость"] == pytest.approx(expected)

    def test_decay_from_zero_with_zero_base(self, engine):
        state = EmotionalState()
        state.emotions["отвращение"] = 0.0
        engine._decay_emotions(state)
        assert state.emotions["отвращение"] == pytest.approx(0.0)

    def test_decay_without_opposite_does_not_clamp_above_one(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 2.0
        engine._decay_emotions(state)
        expected = 0.1 + (2.0 - 0.1) * 0.95
        assert state.emotions["радость"] == pytest.approx(expected)

    def test_decay_opposite_suppressed_by_dominance(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.8
        state.emotions["грусть"] = 0.7
        engine._decay_emotions(state)
        after_joy = 0.1 + (0.8 - 0.1) * 0.95
        after_sad = 0.05 + (0.7 - 0.05) * 0.98
        d = 0.5
        if after_joy > after_sad:
            expected_sad = max(0.0, after_sad - after_joy * d)
        else:
            expected_sad = after_sad
        assert state.emotions["грусть"] == pytest.approx(expected_sad, abs=1e-6)

    def test_decay_all_emotions_present(self, engine):
        state = engine.create_initial_state()
        state.emotions["радость"] = 0.9
        state.emotions["страх"] = 0.8
        engine._decay_emotions(state)
        assert len(state.emotions) == 8


# ---------------------------------------------------------------------------
# _apply_dominance
# ---------------------------------------------------------------------------

class TestApplyDominance:
    def test_stronger_suppresses_weaker_opposite(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.8
        state.emotions["грусть"] = 0.4
        engine._apply_dominance(state)
        suppression = 0.8 * 0.5
        assert state.emotions["грусть"] == pytest.approx(max(0.0, 0.4 - suppression))

    def test_weaker_gets_suppressed_by_stronger_opposite(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.3
        state.emotions["грусть"] = 0.9
        engine._apply_dominance(state)
        suppression = 0.9 * 0.5
        assert state.emotions["радость"] == pytest.approx(max(0.0, 0.3 - suppression))

    def test_equal_intensities_no_change(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.5
        state.emotions["грусть"] = 0.5
        engine._apply_dominance(state)
        assert state.emotions["радость"] == pytest.approx(0.5)
        assert state.emotions["грусть"] == pytest.approx(0.5)

    def test_emotion_without_opposite_unchanged(self, engine):
        del engine.emotion_definitions["радость"]["opposite"]
        state = EmotionalState()
        state.emotions["радость"] = 0.9
        state.emotions["грусть"] = 0.1
        engine._apply_dominance(state)
        assert state.emotions["радость"] == pytest.approx(0.9)

    def test_opposite_not_in_state_skipped(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.9
        engine._apply_dominance(state)
        assert state.emotions["радость"] == pytest.approx(0.9)

    def test_multiple_pairs_processed(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.9
        state.emotions["грусть"] = 0.1
        state.emotions["доверие"] = 0.8
        state.emotions["отвращение"] = 0.2
        engine._apply_dominance(state)

        s1 = 0.9 * 0.5
        assert state.emotions["грусть"] == pytest.approx(max(0.0, 0.1 - s1))

        s2 = 0.8 * 0.5
        assert state.emotions["отвращение"] == pytest.approx(max(0.0, 0.2 - s2))

    def test_dominance_factor_zero_no_suppression(self, config_dir):
        cfg = config_dir
        with open(cfg / "engine_settings.json", "w", encoding="utf-8") as f:
            json.dump({"simulation_tick_seconds": 60, "dominance_factor": 0.0}, f)
        eng = SentioEngine(cfg)

        state = EmotionalState()
        state.emotions["радость"] = 0.8
        state.emotions["грусть"] = 0.4
        eng._apply_dominance(state)
        assert state.emotions["грусть"] == pytest.approx(0.4)

    def test_dominance_factor_one_full_suppression_possible(self, config_dir):
        cfg = config_dir
        with open(cfg / "engine_settings.json", "w", encoding="utf-8") as f:
            json.dump({"simulation_tick_seconds": 60, "dominance_factor": 1.0}, f)
        eng = SentioEngine(cfg)

        state = EmotionalState()
        state.emotions["радость"] = 0.8
        state.emotions["грусть"] = 0.1
        eng._apply_dominance(state)
        assert state.emotions["грусть"] == pytest.approx(0.0)

    def test_already_processed_pair_skipped(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.8
        state.emotions["грусть"] = 0.4
        state.emotions["злость"] = 0.7
        state.emotions["страх"] = 0.3
        engine._apply_dominance(state)

        s1 = 0.8 * 0.5
        assert state.emotions["грусть"] == pytest.approx(max(0.0, 0.4 - s1))

        s2 = 0.7 * 0.5
        assert state.emotions["страх"] == pytest.approx(max(0.0, 0.3 - s2))

    def test_suppression_clamps_at_zero(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 1.0
        state.emotions["грусть"] = 0.1
        engine._apply_dominance(state)
        suppression = 1.0 * 0.5
        assert state.emotions["грусть"] == pytest.approx(max(0.0, 0.1 - suppression))


# ---------------------------------------------------------------------------
# _synchronize_decay
# ---------------------------------------------------------------------------

class TestSynchronizeDecay:
    def test_no_time_elapsed_no_decay(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.8
        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            result = engine._synchronize_decay(state, now)
        assert state.emotions["радость"] == pytest.approx(0.8)
        assert result == now

    def test_one_tick_elapsed_decay_only(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.8

        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(seconds=60)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            result = engine._synchronize_decay(state, past)

        expected = 0.1 + (0.8 - 0.1) * 0.95
        assert state.emotions["радость"] == pytest.approx(expected, abs=1e-6)
        assert result == now

    def test_multiple_ticks_idempotent_decay(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.8

        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(seconds=180)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine._synchronize_decay(state, past)

        expected = 0.8
        for _ in range(3):
            expected = 0.1 + (expected - 0.1) * 0.95
        assert state.emotions["радость"] == pytest.approx(expected, abs=1e-6)

    def test_none_last_update_returns_now(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.8
        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            result = engine._synchronize_decay(state, None)
        assert state.emotions["радость"] == pytest.approx(0.8)
        assert result == now

    def test_tick_seconds_zero_returns_now(self, config_dir):
        cfg = config_dir
        with open(cfg / "engine_settings.json", "w", encoding="utf-8") as f:
            json.dump({"simulation_tick_seconds": 0, "dominance_factor": 0.5}, f)
        eng = SentioEngine(cfg)

        state = EmotionalState()
        state.emotions["радость"] = 0.8
        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(seconds=100)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            result = eng._synchronize_decay(state, past)
        assert state.emotions["радость"] == pytest.approx(0.8)
        assert result == now

    def test_tick_seconds_negative_returns_now(self, config_dir):
        cfg = config_dir
        with open(cfg / "engine_settings.json", "w", encoding="utf-8") as f:
            json.dump({"simulation_tick_seconds": -10, "dominance_factor": 0.5}, f)
        eng = SentioEngine(cfg)

        state = EmotionalState()
        state.emotions["радость"] = 0.8
        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(seconds=100)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            result = eng._synchronize_decay(state, past)
        assert state.emotions["радость"] == pytest.approx(0.8)
        assert result == now

    def test_less_than_one_tick_no_decay(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.8
        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(seconds=30)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            result = engine._synchronize_decay(state, past)
        assert state.emotions["радость"] == pytest.approx(0.8)
        assert result == past

    def test_dominance_applied_after_decay(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.9
        state.emotions["грусть"] = 0.8
        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(seconds=60)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine._synchronize_decay(state, past)

        expected_joy = 0.1 + (0.9 - 0.1) * 0.95
        expected_sad = 0.05 + (0.8 - 0.05) * 0.98
        suppression = expected_joy * 0.5
        assert state.emotions["грусть"] == pytest.approx(max(0.0, expected_sad - suppression))


# ---------------------------------------------------------------------------
# process_stimulus
# ---------------------------------------------------------------------------

class TestProcessStimulus:
    def test_applies_stimulus_to_state(self, engine):
        state = engine.create_initial_state()
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.3

        now = datetime.datetime.now(datetime.timezone.utc)
        last_update = now - datetime.timedelta(seconds=30)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, last_update)

        assert state.emotions["радость"] > 0.1 + 0.3

    def test_clamps_emotion_to_1_0(self, engine):
        state = engine.create_initial_state()
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 10.0

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, now)

        assert state.emotions["радость"] <= 1.0

    def test_clamps_emotion_to_0_0(self, engine):
        state = engine.create_initial_state()
        stimulus = Stimulus()
        stimulus.emotions["радость"] = -10.0

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, now)

        assert state.emotions["радость"] >= 0.0

    def test_unknown_emotion_in_stimulus_ignored(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.1
        stimulus = Stimulus()
        stimulus.emotions["nonexistent_emotion"] = 0.9

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, now)

        assert state.emotions["радость"] == pytest.approx(0.1)

    def test_empty_stimulus_does_not_affect_non_opposite_emotions(self, engine):
        state = EmotionalState()
        state.emotions["радость"] = 0.3
        stimulus = Stimulus()

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, now)

        assert state.emotions["радость"] == pytest.approx(0.3)

    def test_cause_set_to_top_stimulus_emotion(self, engine):
        state = engine.create_initial_state()
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.5
        stimulus.emotions["грусть"] = 0.2

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, now)

        assert "радость" in state.cause

    def test_cause_fallback_unknown_stimulus(self, engine):
        state = engine.create_initial_state()
        stimulus = Stimulus()

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, now)

        assert state.cause == "Unknown stimulus"

    def test_decay_catchup_before_stimulus(self, engine):
        state = engine.create_initial_state()
        state.emotions["радость"] = 1.0

        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.0

        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(seconds=600)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, past)

        expected_after_decay = 1.0
        for _ in range(10):
            expected_after_decay = 0.1 + (expected_after_decay - 0.1) * 0.95
        expected_after_decay = max(0.0, min(1.0, expected_after_decay + 0.0))
        assert state.emotions["радость"] == pytest.approx(expected_after_decay, abs=1e-6)

    def test_dominance_applied_after_stimulus(self, engine):
        state = engine.create_initial_state()
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.8

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, now)

        радость = min(1.0, 0.1 + 0.8)
        грусть = BASE_EMOTIONS["грусть"]["base_intensity"]
        suppression = радость * 0.5
        expected_грусть = max(0.0, грусть - suppression)
        assert state.emotions["грусть"] == pytest.approx(expected_грусть, abs=1e-6)

    def test_personality_modifier_affects_stimulus(self, config_dir):
        personality = copy.deepcopy(BASE_PERSONALITY)
        personality["extraversion"]["value"] = 1.0
        cfg = config_dir
        with open(cfg / "BeliefSystem.json", "w", encoding="utf-8") as f:
            json.dump({"personality": personality}, f, ensure_ascii=False)
        eng = SentioEngine(cfg)

        state = eng.create_initial_state()
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.5

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            eng.process_stimulus(state, stimulus, now)

        modifier = 1.0 + (1.0 - 0.5) * (1.3 - 1.0)
        expected_joy = min(1.0, 0.1 + 0.5 * modifier)
        assert state.emotions["радость"] == pytest.approx(expected_joy, abs=1e-6)

    def test_returns_new_timestamp(self, engine):
        state = engine.create_initial_state()
        stimulus = Stimulus()

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            result = engine.process_stimulus(state, stimulus, now)

        assert result == now

    def test_returns_updated_timestamp_after_decay(self, engine):
        state = engine.create_initial_state()
        state.emotions["радость"] = 1.0
        stimulus = Stimulus()

        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(seconds=120)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            result = engine.process_stimulus(state, stimulus, past)

        assert result == now

    def test_primary_mood_updated_after_stimulus(self, engine):
        state = engine.create_initial_state()
        stimulus = Stimulus()
        stimulus.emotions["страх"] = 1.0

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, now)

        assert "страх" in state.primary_mood

    def test_multiple_emotions_in_stimulus(self, engine):
        state = engine.create_initial_state()
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.4
        stimulus.emotions["страх"] = 0.3

        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            engine.process_stimulus(state, stimulus, now)

        assert state.emotions["радость"] > BASE_EMOTIONS["радость"]["base_intensity"]
        assert state.emotions["страх"] > BASE_EMOTIONS["страх"]["base_intensity"]


# ---------------------------------------------------------------------------
# get_report
# ---------------------------------------------------------------------------

class TestGetReport:
    def test_returns_report_with_state(self, engine):
        state = engine.create_initial_state()
        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            report = engine.get_report(state, now)

        assert isinstance(report, Report)
        assert report.emotional_state.emotions["радость"] == pytest.approx(0.1)
        assert report.emotional_state.cause == "System initialization."

    def test_with_complex_states(self, engine):
        state = engine.create_initial_state()
        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            report = engine.get_report(state, now, complex_states=["депрессивное состояние"])

        assert "депрессивное состояние" in report.complex_states
        assert len(report.complex_states) == 1

    def test_multiple_complex_states(self, engine):
        state = engine.create_initial_state()
        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            report = engine.get_report(state, now,
                                       complex_states=["депрессивное состояние", "эйфория"])

        assert len(report.complex_states) == 2
        assert "депрессивное состояние" in report.complex_states
        assert "эйфория" in report.complex_states

    def test_without_complex_states(self, engine):
        state = engine.create_initial_state()
        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            report = engine.get_report(state, now)

        assert len(report.complex_states) == 0

    def test_decay_synced_before_report(self, engine):
        state = engine.create_initial_state()
        state.emotions["радость"] = 1.0

        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(seconds=120)

        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            report = engine.get_report(state, past)

        expected = 1.0
        for _ in range(2):
            expected = 0.1 + (expected - 0.1) * 0.95
        expected = max(0.0, expected)
        assert report.emotional_state.emotions["радость"] == pytest.approx(expected, abs=1e-6)

    def test_report_with_none_last_update(self, engine):
        state = engine.create_initial_state()
        state.emotions["радость"] = 0.9
        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            report = engine.get_report(state, None)

        assert report.emotional_state.emotions["радость"] == pytest.approx(0.9)

    def test_report_contains_primary_mood_from_state(self, engine):
        state = engine.create_initial_state()
        state.emotions["радость"] = 0.9
        engine._update_primary_mood(state)
        now = datetime.datetime.now(datetime.timezone.utc)
        with patch("sentio_engine.core.engine.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = now
            report = engine.get_report(state, now)

        assert "радость" in report.emotional_state.primary_mood
