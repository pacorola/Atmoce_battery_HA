"""Tests for the shared storage-model redaction."""
from custom_components.atmoce.redact import REDACTED, redact_model


class TestIdentifyingFields:
    """Anything naming the owner or locating the site has to go."""

    def test_owner_and_site_fields_are_blanked(self):
        model = redact_model(
            {
                "ownerMail": "me@example.com",
                "stationName": "Casa de Pablo",
                "latitude": 40.41,
                "longitude": -3.70,
                "userAccount": "pablo",
                "token": "abc",
            }
        )

        assert all(value == REDACTED for value in model.values())

    def test_nested_structures_are_walked(self):
        model = redact_model(
            {"stations": [{"stationAddress": "Calle Mayor 1", "workModel": 1}]}
        )

        assert model["stations"][0]["stationAddress"] == REDACTED
        assert model["stations"][0]["workModel"] == 1


class TestCoordinateAbbreviations:
    """"lat" as a bare substring would also swallow latestVersion."""

    def test_abbreviations_are_redacted_as_whole_words(self):
        model = redact_model({"stationLat": 40.41, "station_lng": -3.70, "lat": 1.0})

        assert model["stationLat"] == REDACTED
        assert model["station_lng"] == REDACTED
        assert model["lat"] == REDACTED

    def test_unrelated_fields_keeping_the_letters_survive(self):
        model = redact_model(
            {
                "latestVersion": "1.2.3",
                "translationKey": "grid_charge",
                "longRunAverage": 42,
            }
        )

        assert model["latestVersion"] == "1.2.3"
        assert model["translationKey"] == "grid_charge"
        assert model["longRunAverage"] == 42


class TestValuesAreLeftAlone:
    """Only field names decide; settings values must survive intact."""

    def test_settings_are_untouched(self):
        model = redact_model({"storageChargeCutoffSoc": 90, "workModel": "1"})

        assert model == {"storageChargeCutoffSoc": 90, "workModel": "1"}
