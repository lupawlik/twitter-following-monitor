# to accessing protected resources by oa1/oa2
import requests
import yaml
from requests_oauthlib import OAuth1Session

URL = "https://api.twitter.com"

try:
    with open("pw.yaml", "r") as f:
        y = yaml.safe_load(f)
        TWITTER_KEY = y['TWITTER_KEY']
        TWITTER_SECRET = y['TWITTER_SECRET']
except Exception:
    print("Paste data in pw.yaml. Zalando login failed")


# return consumer_key and consumer_secrete to make to twitter app.
# main data to make requests to twitter
def request_token():

    # get request_token_key, request_token_secret
    token = OAuth1Session(client_key=TWITTER_KEY, client_secret=TWITTER_SECRET)

    # get oauth_token=token&oauth_token_secret=secret&oauth_callback_confirmed=true
    data = token.get(f'{URL}/oauth/request_token').text
    consumer_key, consumer_secrete, oauth_callback_confirmed = data.split('&')
    # fetch secrets and return
    return consumer_key.split('=')[1], consumer_secrete.split('=')[1]

# creates user side oauth_key and ouath_secret, used to make request from my app but with data auth from user
# takes consumer_key and secret from app and verifier token from redirect to twitter auth form
def access_token(consumer_key, consumer_secrete, oauth_verifier):
    link = f'{URL}/oauth/access_token'
    data = {
        "oauth_verifier": f"{oauth_verifier}"
    }
    token = OAuth1Session(
        client_key=TWITTER_KEY,
        client_secret=TWITTER_SECRET,
        resource_owner_key=consumer_key,
        resource_owner_secret=consumer_secrete)

    r = token.post(link, data=data)
    # check if data passed by user are valid
    if not r.ok:
        return None
    # extract data from request
    r = r.text
    oauth_token, oauth_token_secret, user_id, screen_name = r.split("&")
    data = {
        "oauth_token": oauth_token.split("=")[1],
        "oauth_token_secret": oauth_token_secret.split("=")[1],
        "user_id": user_id.split("=")[1],
        "screen_name": screen_name.split("=")[1]
    }
    return data

# takes data from current_user from db
class TwitterApi(object):
    def __init__(self, data_about_user):
        #self._key = key
        #self._secret = secret
        self.user_id = data_about_user.user_id
        self.user_name = data_about_user.name
        self.oauth_token = data_about_user.oauth_token
        self.oauth_token_secret = data_about_user.oauth_token_secret
        self.auth = OAuth1Session(
                TWITTER_KEY,
                TWITTER_SECRET,
                self.oauth_token,
                self.oauth_token_secret)

    # return following list
    def get_following(self):
        r = self.auth.get(f"{URL}/2/users/{self.user_id}/following").json()
        return r

    def get_following_by_user(self, user_id):
        r = self.auth.get(f"{URL}/2/users/{user_id}/following").json()
        return r

    # return user by username
    def get_user_by_name(self, username):
        r = self.auth.get(f"{URL}/2/users/by/username/{username}").json()
        # check if user with given name not exist
        try:
            if r['errors']:
                return None
        except:
            return r

    def follow_user(self, user_id):
        params = {
            "target_user_id": f"{user_id}"
        }
        r = self.auth.post(f"{URL}/2/users/{self.user_id}/following", json=params).json()
        return r

    def unfollow_user(self, user_id):
        r = self.auth.delete(f"{URL}/2/users/{self.user_id}/following/{user_id}").json()
        return r
