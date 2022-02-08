import sqlite3
import time
from requests_oauthlib import OAuth1Session
from twitter_api import TWITTER_KEY, TWITTER_SECRET

# worker to check if users follow someone new
# gets client secrets - used to make requests
# get following from twitter api and db for given user and compare it

class Monitor(object):
    def __init__(self):
        self.conn = sqlite3.connect("database.db", check_same_thread=False)
        self.c = self.conn.cursor()

    # return secrets users of app, list of tuples
    def __get_clients(self):
        query = f"SELECT oauth_token, oauth_token_secret, name FROM user"
        self.c.execute(query)
        datas = self.c.fetchall()
        return datas

    # return list of tuples with all users to spy
    def _get_spied_users(self):
        query = f"SELECT user_id, name, following FROM spied_users"
        self.c.execute(query)
        datas = self.c.fetchall()
        return datas

    def _get_following_from_db(self):
        pass

    # takes following list of spied user from db and from api. Compare and add last_follow, last_unfollow and update following column in spied_users
    # token and secret from user table, used to make requests
    # return false if request is faile
    def check_user(self, token, secret, user_id, following_list):
        token = OAuth1Session(
            client_key=TWITTER_KEY,
            client_secret=TWITTER_SECRET,
            resource_owner_key=token,
            resource_owner_secret=secret)
        r = token.get(f"https://api.twitter.com/2/users/{user_id}/following")
        if not r.ok:
            return False
        r = r.json()

        new_users_to_query = following_list

        # check if user follow someone new
        users_to_add = ""
        for user_from_r in r['data']:
            user_exist_in_db = False
            # when user from api is in db
            if user_from_r['id'] in following_list:
                user_exist_in_db = True
            # when in twitter api is new user but in db is not, add it
            if not user_exist_in_db:
                # add this user to string that been added to old following list and saved in db
                users_to_add += f"{user_from_r['id']} {user_from_r['username']},"
        if users_to_add:
            print(f"[{user_id}] started following {users_to_add}")
            query = f"UPDATE spied_users SET last_follow='{users_to_add}' WHERE user_id='{user_id}'"
            self.c.execute(query)
            self.conn.commit()

        # check if user unfollow someone new
        users_to_delete = ""
        for user_in_db in str(following_list).split(","):
            # get only id from data
            user_in_db_id = user_in_db.split(" ")[0]
            if not user_in_db_id or user_in_db_id == " ":
                continue

            exist_on_twitter = False
            for user_from_r in r['data']:
                if user_in_db_id == user_from_r['id']:
                    exist_on_twitter = True
            if not exist_on_twitter:
                delete_this = f"{user_in_db},"
                users_to_delete += delete_this
                new_users_to_query = str(new_users_to_query).replace(delete_this, "")
        if users_to_delete:
            print(f"[{user_id}] removed from following {users_to_delete}")
            query = f"UPDATE spied_users SET last_unfollow='{users_to_delete}' WHERE user_id='{user_id}'"
            self.c.execute(query)
            self.conn.commit()

        # add to new followers in db
        new_users_to_query += users_to_add
        query = f"UPDATE spied_users SET following='{new_users_to_query}' WHERE user_id='{user_id}'"
        self.c.execute(query)
        self.conn.commit()
        return True

    def star_monitor(self):
        while True:
            print("[FOLLOWING MONITOR] Starting new monitor session...")
            secrets = self.__get_clients()
            if len(secrets) == 0:
                return None
            spied_users = self._get_spied_users()

            client_number = 0
            first = True
            for user_to_check in spied_users:
                # when uses again same client to auth
                if client_number >= len(secrets):
                    client_number = 0
                    if not first:
                        print("[FOLLOWING MONITOR] Waiting 1 minute and 1 second, client auth pool ends")
                        time.sleep(61)
                print(f"[FOLLOWING MONITOR] Checking {user_to_check[1]} using {secrets[client_number][2]} auth secrets")
                user_checked = False
                while not user_checked:
                    user_checked = self.check_user(secrets[client_number][0], secrets[client_number][1], user_to_check[0], user_to_check[2])
                    if not user_checked:
                        print("[FOLLOWING MONITOR] Too many requests... Waiting 15 minutes")
                        time.sleep(900)
                client_number += 1
                time.sleep(5)
                first = False
            print("[FOLLOWING MONITOR] Stopped monitor session.")
            time.sleep(3600)
