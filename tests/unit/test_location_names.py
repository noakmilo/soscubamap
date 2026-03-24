from app.services.location_names import (
    canonicalize_location_names,
    canonicalize_municipality_name,
    canonicalize_province_name,
    normalize_location_key,
)


class TestLocationNames:
    def test_canonicalize_compacted_province(self):
        assert canonicalize_province_name("SantiagoDeCuba") == "Santiago de Cuba"

    def test_canonicalize_historic_havana_alias(self):
        assert canonicalize_province_name("CiudadDeLaHabana") == "La Habana"

    def test_canonicalize_province_without_accents(self):
        assert canonicalize_province_name("PinarDelRio") == "Pinar del Río"

    def test_canonicalize_municipality_with_province_context(self):
        assert (
            canonicalize_municipality_name("HabanaVieja", "CiudadDeLaHabana")
            == "La Habana Vieja"
        )

    def test_unknown_values_turn_into_none(self):
        province_name, municipality_name = canonicalize_location_names(
            "N/D",
            "Desconocido",
        )
        assert province_name is None
        assert municipality_name is None

    def test_normalized_key_equivalence(self):
        assert normalize_location_key("SantiagoDeCuba") == normalize_location_key(
            "Santiago de Cuba"
        )
