from fastapi.testclient import TestClient
import pytest
from app.main import app, fetcher
from unittest.mock import AsyncMock, patch, MagicMock

client = TestClient(app)

def test_stock_search_endpoint():
    # Test valid stock code search with mock to be offline-friendly
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
            "f129": "OLED"
        }
    }
    
    mock_client.get.side_effect = [mock_suggest_resp, mock_profile_resp]
    
    orig_latest = fetcher.latest_data
    fetcher.latest_data = {
        "industry": [{"code": "BK0468", "name": "光学光电子"}],
        "concept": [{"code": "BK0878", "name": "OLED"}]
    }
    
    try:
        with patch.object(fetcher, "get_client", return_value=mock_client):
            response = client.get("/api/stocks/search?q=000725")
            assert response.status_code == 200
            res_data = response.json()
            assert "data" in res_data
            assert res_data["data"]["stock_code"] == "000725"
    finally:
        fetcher.latest_data = orig_latest

def test_stock_search_url_encoding():
    """包含 & 等特殊字符的查询必须通过 params 传递，而非拼接到 URL 字符串"""
    mock_client = AsyncMock()

    mock_suggest_resp = MagicMock()
    mock_suggest_resp.status_code = 200
    mock_suggest_resp.json.return_value = {
        "QuotationCodeTable": {
            "Data": [
                {"QuoteID": "0.000725", "Code": "000725", "Name": "京东方A"}
            ]
        }
    }

    mock_profile_resp = MagicMock()
    mock_profile_resp.status_code = 200
    mock_profile_resp.json.return_value = {"data": {"f127": "", "f129": ""}}

    mock_client.get.side_effect = [mock_suggest_resp, mock_profile_resp]

    with patch.object(fetcher, "get_client", return_value=mock_client):
        # q 值本身包含 "&type=14"，拼接 URL 时会截断查询参数
        response = client.get("/api/stocks/search", params={"q": "000725&type=14"})
        assert response.status_code == 200

        suggest_args, suggest_kwargs = mock_client.get.call_args_list[0]
        suggest_url = suggest_args[0] if suggest_args else suggest_kwargs.get("url", "")
        assert "input=" not in suggest_url, "input 不应拼接到 URL 字符串中"
        assert suggest_kwargs["params"]["input"] == "000725&type=14"
        assert suggest_kwargs["params"]["type"] == 14

        # profile 请求同样应通过 params 传参，而非拼接到 URL
        profile_args, profile_kwargs = mock_client.get.call_args_list[1]
        profile_url = profile_args[0] if profile_args else profile_kwargs.get("url", "")
        assert "secid=" not in profile_url, "secid 不应拼接到 URL 字符串中"
        assert profile_kwargs["params"]["secid"] == "0.000725"
        assert profile_kwargs["params"]["fields"] == "f127,f129"


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
    
    orig_latest = fetcher.latest_data
    fetcher.latest_data = {
        "industry": [{"code": "BK0468", "name": "光学光电子"}],
        "concept": [{"code": "BK0878", "name": "OLED"}]
    }
    
    try:
        with patch.object(fetcher, "get_client", return_value=mock_client):
            response = client.get("/api/stocks/search?q=000725")
            assert response.status_code == 200
            res_data = response.json()
            assert res_data["code"] == 200
            assert res_data["data"]["stock_code"] == "000725"
            assert res_data["data"]["stock_name"] == "京东方A"
            assert res_data["data"]["industry"]["code"] == "BK0468"
            assert res_data["data"]["concepts"][0]["code"] == "BK0878"
    finally:
        fetcher.latest_data = orig_latest
