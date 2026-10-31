from fastapi.testclient import TestClient
from backend.main import app
from engine.config import load_engine_config
from engine.skills.registry import skills_registry
from engine.pipeline import run_stock_pipeline


def test_load_engine_config():
    cfg = load_engine_config()
    assert "app_name" in cfg
    assert "market" in cfg
    assert "risk" in cfg
    assert "skills" in cfg
    assert "trend_following" in cfg["skills"]["enabled"]


def test_skills_registry():
    skills = skills_registry.list_skills()
    skill_names = [s["name"] for s in skills]
    assert "trend_following" in skill_names
    assert "breakout_detection" in skill_names
    assert "mean_reversion" in skill_names

    trend_skill = skills_registry.get("trend_following")
    assert trend_skill is not None
    assert trend_skill.name == "trend_following"


def test_pipeline_execution_gp():
    res = run_stock_pipeline("GP")
    assert res["status"] == "success"
    assert res["symbol"] == "GP"
    assert "skill_findings" in res
    assert "trend_following" in res["skill_findings"]
    assert "breakout_detection" in res["skill_findings"]
    assert "mean_reversion" in res["skill_findings"]
    assert "risk_evaluation" in res


def test_api_engine_endpoints():
    with TestClient(app) as client:
        # Config endpoint
        cfg_res = client.get("/engine/config")
        assert cfg_res.status_code == 200
        assert "app_name" in cfg_res.json()

        # Skills list
        skills_res = client.get("/engine/skills")
        assert skills_res.status_code == 200
        assert len(skills_res.json()["skills"]) >= 3

        # Pipeline endpoint
        pipe_res = client.get("/engine/pipeline/GP")
        assert pipe_res.status_code == 200
        assert pipe_res.json()["symbol"] == "GP"

