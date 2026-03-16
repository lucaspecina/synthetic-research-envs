"""Tests for DataSampler."""

from sreg.models.world import NodeType
from sreg.tools.data_sampler import DataSampler, DataSamplerConfig
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


def _make_world(num_nodes=6, template="latent_preference", seed=42):
    config = WorldGenConfig(
        template_family=template,
        num_nodes=num_nodes,
        edge_strength=0.7,
        seed=seed,
    )
    return WorldGenTool().generate(config)


# ------------------------------------------------------------------
# Original single-dataset tests (backwards compatibility)
# ------------------------------------------------------------------


def test_tabular_format():
    world = _make_world()
    sampler = DataSampler()
    config = DataSamplerConfig(num_rows=10, format="tabular", seed=0)
    assets = sampler.sample(world, config)

    assert len(assets) == 1
    asset = assets[0]
    assert asset.format == "tabular"
    assert len(asset.data) == 10
    # Should not include latent nodes
    for row in asset.data:
        assert "hidden_cause" not in row


def test_observations_format():
    world = _make_world()
    sampler = DataSampler()
    config = DataSamplerConfig(num_rows=10, format="observations", seed=0)
    assets = sampler.sample(world, config)

    assert len(assets) == 1
    asset = assets[0]
    assert asset.format == "observations"
    assert len(asset.data) > 0
    # Each observation should have variable and value
    for obs in asset.data:
        assert "variable" in obs
        assert "value" in obs


def test_both_format():
    world = _make_world()
    sampler = DataSampler()
    config = DataSamplerConfig(num_rows=10, format="both", seed=0)
    assets = sampler.sample(world, config)

    assert len(assets) == 2
    formats = {a.format for a in assets}
    assert "tabular" in formats
    assert "observations" in formats


def test_include_latent():
    world = _make_world()
    sampler = DataSampler()
    config = DataSamplerConfig(num_rows=5, format="tabular", seed=0, include_latent=True)
    assets = sampler.sample(world, config)

    asset = assets[0]
    first_row = asset.data[0]
    assert "hidden_cause" in first_row


def test_deterministic_with_seed():
    world = _make_world()
    sampler = DataSampler()
    config = DataSamplerConfig(num_rows=5, format="tabular", seed=99)

    assets1 = sampler.sample(world, config)
    assets2 = sampler.sample(world, config)

    assert assets1[0].data == assets2[0].data


# ------------------------------------------------------------------
# Multi-dataset mode
# ------------------------------------------------------------------


def test_multi_dataset_generates_two_assets():
    """multi_dataset=True produces primary + secondary datasets."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    config = DataSamplerConfig(
        num_rows=20, multi_dataset=True, seed=0,
    )
    assets = sampler.sample(world, config)

    # Should have at least 2 assets (primary + secondary)
    assert len(assets) >= 2
    assert all(a.format == "tabular" for a in assets)
    # Background has many rows (at least num_rows)
    primary = assets[0]
    assert primary.num_rows >= 20
    assert "background" in primary.name or "primary" in primary.name
    # Field survey has fewer rows
    secondary = assets[1]
    assert "survey" in secondary.name or "supplementary" in secondary.name
    assert secondary.num_rows <= primary.num_rows


def test_multi_dataset_fallback_few_visible():
    """With <4 visible nodes, multi_dataset falls back to single dataset."""
    # latent_preference with 4 nodes: 1 latent + 1 target + 2 observable = 3 visible
    world = _make_world(num_nodes=4)
    visible = [n for n in world.nodes if n.type != NodeType.LATENT]
    if len(visible) < 4:
        sampler = DataSampler()
        config = DataSamplerConfig(
            num_rows=10, format="tabular", multi_dataset=True, seed=0,
        )
        assets = sampler.sample(world, config)
        # Falls back to single dataset
        assert len(assets) == 1


def test_split_columns_target_in_primary():
    """Target variable must always be in the primary dataset."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    visible_names = [n.name for n in world.nodes if n.type != NodeType.LATENT]
    primary, secondary = sampler._split_columns(world, visible_names)

    target = next(n for n in world.nodes if n.type == NodeType.TARGET)
    assert target.name in primary


def test_split_columns_overlap():
    """Primary and secondary share at least 1 column (join key)."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    visible_names = [n.name for n in world.nodes if n.type != NodeType.LATENT]
    primary, secondary = sampler._split_columns(world, visible_names)

    overlap = set(primary) & set(secondary)
    assert len(overlap) >= 1, f"No overlap: primary={primary}, secondary={secondary}"


def test_split_columns_secondary_has_min_columns():
    """Secondary dataset has at least 2 columns."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    visible_names = [n.name for n in world.nodes if n.type != NodeType.LATENT]
    _, secondary = sampler._split_columns(world, visible_names)

    assert len(secondary) >= 2


def test_secondary_default_rows():
    """Default secondary rows = max(5, num_rows // 3)."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    config = DataSamplerConfig(num_rows=30, multi_dataset=True, seed=0)
    assets = sampler.sample(world, config)

    secondary = assets[1]
    assert secondary.num_rows <= assets[0].num_rows  # survey has fewer rows than background


def test_secondary_custom_rows():
    """secondary_rows parameter overrides default."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    config = DataSamplerConfig(
        num_rows=30, multi_dataset=True, seed=0, secondary_rows=15,
    )
    assets = sampler.sample(world, config)

    secondary = assets[1]
    assert secondary.num_rows == 15


def test_metadata_fields_populated():
    """Multi-dataset assets have source, columns, num_rows filled."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    config = DataSamplerConfig(num_rows=20, multi_dataset=True, seed=0)
    assets = sampler.sample(world, config)

    for asset in assets:
        assert asset.source is not None
        assert asset.columns is not None
        assert len(asset.columns) >= 2
        assert asset.num_rows is not None
        assert asset.num_rows == len(asset.data)


# ------------------------------------------------------------------
# Missing data injection
# ------------------------------------------------------------------


def test_missing_rate_injects_not_measured():
    """missing_rate > 0 should produce 'not_measured' values."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    config = DataSamplerConfig(
        num_rows=50, multi_dataset=True, missing_rate=0.3, seed=0,
    )
    assets = sampler.sample(world, config)

    # Check primary dataset has some not_measured
    primary = assets[0]
    not_measured_count = sum(
        1 for row in primary.data
        for k, v in row.items() if k != "sample_id" and v == "not_measured"
    )
    assert not_measured_count > 0, "Expected some not_measured values with rate=0.3"


def test_missing_rate_preserves_min_columns():
    """Each row must have at least 2 real (non-missing) data columns."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    config = DataSamplerConfig(
        num_rows=50, multi_dataset=True, missing_rate=0.4, seed=0,
    )
    assets = sampler.sample(world, config)

    for asset in assets:
        for row in asset.data:
            data_keys = [k for k in row if k != "sample_id"]
            real = [k for k in data_keys if row[k] not in ("not_measured", "partial")]
            assert len(real) >= 2, f"Row has <2 real columns: {row}"


def test_missing_rate_zero_no_missing():
    """missing_rate=0 should produce no missing values."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    config = DataSamplerConfig(
        num_rows=20, multi_dataset=True, missing_rate=0.0, seed=0,
    )
    assets = sampler.sample(world, config)

    for asset in assets:
        for row in asset.data:
            for k, v in row.items():
                assert v != "not_measured", f"Found not_measured with rate=0: {row}"


# ------------------------------------------------------------------
# Narrative observations
# ------------------------------------------------------------------


def test_narrative_observations():
    """narrative_observations > 0 generates a narrative DataAsset."""
    world = _make_world(num_nodes=6)
    sampler = DataSampler()
    config = DataSamplerConfig(
        num_rows=10, format="tabular", seed=0, narrative_observations=3,
    )
    assets = sampler.sample(world, config)

    # Should have tabular + narrative
    assert len(assets) == 2
    narrative = next(a for a in assets if a.format == "narrative")
    assert narrative.name == "field_notes"
    assert len(narrative.data) == 3
    for obs in narrative.data:
        assert "observation" in obs
        assert "source" in obs
        # Each observation should be a real sentence
        assert len(obs["observation"]) > 10


def test_narrative_with_multi_dataset():
    """Narrative observations work alongside multi-dataset mode."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    config = DataSamplerConfig(
        num_rows=20, multi_dataset=True, seed=0, narrative_observations=2,
    )
    assets = sampler.sample(world, config)

    # background + survey + optional_detailed + narrative = 3-4
    assert len(assets) >= 3
    formats = [a.format for a in assets]
    assert formats.count("tabular") >= 2
    assert formats.count("narrative") == 1


def test_narrative_zero_no_extra_asset():
    """narrative_observations=0 (default) should not add a narrative asset."""
    world = _make_world(num_nodes=6)
    sampler = DataSampler()
    config = DataSamplerConfig(num_rows=10, format="tabular", seed=0)
    assets = sampler.sample(world, config)

    assert len(assets) == 1
    assert assets[0].format == "tabular"


# ------------------------------------------------------------------
# Determinism
# ------------------------------------------------------------------


def test_multi_dataset_deterministic():
    """Same seed produces identical multi-dataset output."""
    world = _make_world(num_nodes=8)
    sampler = DataSampler()
    config = DataSamplerConfig(
        num_rows=20, multi_dataset=True, missing_rate=0.2,
        narrative_observations=2, seed=42,
    )

    assets1 = sampler.sample(world, config)
    assets2 = sampler.sample(world, config)

    assert len(assets1) == len(assets2)
    for a1, a2 in zip(assets1, assets2):
        assert a1.name == a2.name
        assert a1.data == a2.data
