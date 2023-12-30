import requests

def get_user_profile(ca_username, client_id, client_secret):

    url = f'https://api.chaster.app/users/profile/{ca_username}'
    headers = {
        'X-Chaster-Client-Id': client_id,
        'X-Chaster-Client-Secret': client_secret
    }
    response = requests.get(url, headers=headers)

    #print(response.json())
    return response.json()

def get_user_lockid(ca_userid, client_id, client_secret):

    url = f'https://api.chaster.app/locks/user/{ca_userid}'
    headers = {
        'X-Chaster-Client-Id': client_id,
        'X-Chaster-Client-Secret': client_secret
    }
    response = requests.get(url, headers=headers)

    #print(response.json())
    return response.json()

def get_user_lockinfo(ca_lockid, ca_access_token):
    url = f'https://api.chaster.app/locks/{ca_lockid}'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {ca_access_token}'
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        #print(response.json())
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None