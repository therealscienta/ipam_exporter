import pytest
from src.web_csv import app, get_cached_snapshot


def test_health_endpoint():
    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert 'status' in data
        assert 'count' in data
        assert 'last_updated' in data


def test_data_endpoint():
    with app.test_client() as client:
        response = client.get('/data')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)


def test_count_endpoint():
    with app.test_client() as client:
        response = client.get('/count')
        assert response.status_code == 200
        data = response.get_json()
        assert 'count' in data


def test_columns_endpoint():
    with app.test_client() as client:
        response = client.get('/columns')
        assert response.status_code == 200
        data = response.get_json()
        assert 'columns' in data


def test_csv_endpoint():
    with app.test_client() as client:
        response = client.get('/csv')
        assert response.status_code == 200
        assert 'text/csv' in response.content_type


def test_download_json_endpoint():
    with app.test_client() as client:
        response = client.get('/download.json')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert 'attachment' in response.headers.get('Content-Disposition', '')
