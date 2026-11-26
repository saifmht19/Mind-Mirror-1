"""Stub conformance always runs. Real-implementation conformance runs when VOICE_TEST_REAL lists the kind,
e.g.  VOICE_TEST_REAL=input,output pytest voice -m real -q"""
import pytest

from voice import registry
from voice.tests import conformance as c
from voice.tests.conftest import real_enabled


def test_stub_speech_input(tmp): c.check_speech_input(registry.get_speech_input("stub"), tmp)
def test_stub_synthesizer(tmp): c.check_synthesizer(registry.get_synthesizer("stub"), tmp)
def test_stub_feature_extractor(tmp): c.check_feature_extractor(registry.get_feature_extractor("stub"), tmp, strict=False)


@pytest.mark.parametrize("name", ["text", "context", "context_voice"])
def test_stub_detector(name): c.check_detector(registry.get_detector(name, "stub"))


@pytest.mark.real
@pytest.mark.skipif(not real_enabled("input"), reason="VOICE_TEST_REAL does not include 'input'")
def test_real_speech_input(tmp): c.check_speech_input(registry.get_speech_input("real"), tmp)


@pytest.mark.real
@pytest.mark.skipif(not real_enabled("output"), reason="VOICE_TEST_REAL does not include 'output'")
def test_real_synthesizer(tmp): c.check_synthesizer(registry.get_synthesizer("real"), tmp)


@pytest.mark.real
@pytest.mark.skipif(not real_enabled("features"), reason="VOICE_TEST_REAL does not include 'features'")
def test_real_feature_extractor(tmp): c.check_feature_extractor(registry.get_feature_extractor("real"), tmp, strict=True)


@pytest.mark.real
@pytest.mark.skipif(not real_enabled("detector"), reason="VOICE_TEST_REAL does not include 'detector'")
@pytest.mark.parametrize("name", ["text", "context", "context_voice"])
def test_real_detector(name): c.check_detector(registry.get_detector(name, "real"))
