from fastapi.testclient import TestClient
import pytest
from app.main import app, fetcher
from unittest.mock import AsyncMock, patch, MagicMock

client = TestClient(app)

def test_stock_search_endpoint():
    # Test valid stock code search
    response = client.get("/api/stocks/search?q=000725")
    assert response.status_code == 200
    res_data = response.json()
    assert "data" in res_data
    assert res_data["data"]["stock_code"] == "000725"

def test_stock_search_mocked():
    mock_client = AsyncMock()
    
    mock_suggest_resp = MagicMock()
    mock_suggest_resp.status_code = 200
    mock_suggest_resp.json.return_value = {
        "QuotationCodeTable": {
            "Data": [
                {
                    "QuoteID": "0.000725",
                    "Code": "000725",
                    "Name": "京东方A"
                }
            ]
        }
    }
    
    mock_profile_resp = MagicMock()
    mock_profile_resp.status_code = 200
    mock_profile_resp.json.return_value = {
        "data": {
            "f127": "光学光电子",
            "f129": "国企改革, OLED, 华为概念"
        }
    }
    
    mock_client.get.side_effect = [mock_suggest_resp, mock_profile_resp]
    
    fetcher.latest_data = {
        "industry": [{"code": "BK0468", "name": "光学光电子"}],
        "concept": [{"code": "BK0878", "name": "OLED"}]
    }
    
    with patch.object(fetcher, "get_client", return_value=mock_client):
        response = client.get("/api/stocks/search?q=000725")
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["code"] == 200
        assert res_data["data"]["stock_code"] == "000725"
        assert res_data["data"]["stock_name"] == "京东方A"
        assert res_data["data"]["industry"]["code"] == "BK0468"
        assert res_data["data"]["concepts"][0]["code"] == "BK0878"
