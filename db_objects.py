from __main__ import db, login_m
from flask_login import UserMixin

# create user tab
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(40), unique=True)
    name = db.Column(db.String(16), unique=True)
    oauth_token = db.Column(db.String(70))
    oauth_token_secret = db.Column(db.String(70))
    following = db.Column(db.String(200000))
    spied_users = db.Column(db.String(200000))

    def __init__(self, user_id, name, oauth_token, oauth_token_secret):
        self.user_id = user_id
        self.name = name
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret

# table with twitter users that's are spied by clients of this app
class SpiedUsers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(40), unique=True)
    name = db.Column(db.String(16), unique=True)
    screen_name = db.Column(db.String(200))
    following = db.Column(db.String(200000))
    last_follow = db.Column(db.String(20000))
    last_unfollow = db.Column(db.String(200000))

    def __init__(self, user_id, name, screen_name, following):
        self.user_id = user_id
        self.name = name
        self.screen_name = screen_name
        self.following = following


# connect flask login user with user in db model
@login_m.user_loader
def get_user(user):
    return User.query.get(int(user))