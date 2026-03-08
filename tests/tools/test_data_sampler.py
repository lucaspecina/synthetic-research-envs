"""Tests for DataSampler."""

from sreg.tools.data_sampler import DataSampler, DataSamplerConfig
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


def _make_world():
    config = WorldGenConfig(
        template_family="latent_preference",
        num_nodes=6,
        edge_strength=0.7,
        seed=42,
    )
    return WorldGenTool().generate(config)


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
