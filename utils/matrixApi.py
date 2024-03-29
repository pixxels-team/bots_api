import logging
import random
import os
import hmac, hashlib
from io import BytesIO

import requests
from nio import AsyncClient
from nio.responses import ProfileSetAvatarError


MATRIX_API_URL = os.environ["MATRIX_URL"]
SHARED_SECRET = os.environ["SHARED_SECRET"]


def generatePassword(n):
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ123456789!@#$%^&*()"
    password = ""

    for i in range(n):
        password += random.choice(characters)

    # finally returning the randomly generated password.
    return password


def register_bot(username, password, display_name, device_id):
    body = {
        "auth": {
            "type": "m.login.dummy"
        },
        "device_id": device_id,
        "initial_device_display_name": display_name,
        "password": password,
        "username": username
    }
    url = f"{MATRIX_API_URL}/_matrix/client/v3/register"
    response = requests.post(url, json=body)
    if (response.status_code == 200):
        return response.json()
    else:
        return {"status": response.status_code}



def generate_mac(nonce, user, password, admin=False, user_type=None):
    shared_secret = bytes(SHARED_SECRET, "utf-8")
    mac = hmac.new(
      key=shared_secret,
      digestmod=hashlib.sha1,
    )

    mac.update(nonce.encode('utf8'))
    mac.update(b"\x00")
    mac.update(user.encode('utf8'))
    mac.update(b"\x00")
    mac.update(password.encode('utf8'))
    mac.update(b"\x00")
    mac.update(b"admin" if admin else b"notadmin")
    if user_type:
        mac.update(b"\x00")
        mac.update(user_type.encode('utf8'))

    return mac.hexdigest()

def register_user(username, password, display_name, device_id=None):
    auth_token = os.environ["AUTH_TOKEN"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    nonce = requests.get(f'{MATRIX_API_URL}/_synapse/admin/v1/register', headers=headers)
    gen_hmac = generate_mac(nonce.json()["nonce"], username, password)
    body = {
        "nonce": nonce.json()["nonce"],
        "username": username,
        "displayname": display_name,
        "password": password,
        "admin": False,
        "mac": gen_hmac
    }
    req = requests.post(
        f'{MATRIX_API_URL}/_synapse/admin/v1/register', headers=headers, json=body)
    if (req.status_code == 200):
        return req.json()
    else:
        return {"status": req.status_code}


def get_email_from_username(username):
    auth_token = os.environ["AUTH_TOKEN"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    req = requests.get(
        f'{MATRIX_API_URL}/_synapse/admin/v2/users/{username}', headers=headers)
    if req.status_code == 200:
        data = req.json()
        if data["threepids"] is not []:
            return data["threepids"][0]["address"]
    return None


def get_access_token(username, password):
    body = {
        "identifier": {"type": "m.id.user", "user": username},

        "password": password,

        "type": "m.login.password",
        "device_id": "deployer"
    }
    url = f"{MATRIX_API_URL}/_matrix/client/r0/login"
    response = requests.post(url, json=body)
    if response.status_code == 200:
        return response.json()['access_token']


async def set_profile(password, homeserver, user_id, profile_url):
    client = AsyncClient(homeserver, user_id)
    await client.login(password)
    data = requests.get(profile_url)
    upload_img = BytesIO(data.content)
    profile_mxc = await client.upload(upload_img, content_type=data.headers['Content-Type'])
    response = await client.set_avatar(profile_mxc[0].content_uri)
    if type(response) == ProfileSetAvatarError:
        logging.error(response)
        return None
    await client.close()
    return profile_mxc[0].content_uri

async def set_display_name(password, homeserver, user_id, name):
    client = AsyncClient(homeserver, user_id)
    await client.login(password)
    await client.set_displayname(name)
    await client.close()
    return True
