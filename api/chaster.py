
import requests

class API_Chaster:
    def __init__(self, client_id, client_secret):
        self.base_url = 'https://api1.example.com'
        self.client_id = client_id
        self.client_secret = client_secret

    def get_data(self, endpoint):
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, auth=(self.client_id, self.client_secret))
        return response.json()
