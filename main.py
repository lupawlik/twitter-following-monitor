import threading
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from twitter_api import TwitterApi, request_token, access_token

app = Flask(__name__)
app.config['SECRET_KEY'] = ".."
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
login_m = LoginManager()  # set flask login extension
login_m.init_app(app)
login_m.login_view = 'index'  # redirect to index when user is not authorized

from db_objects import User, SpiedUsers
from worke_monitor import Monitor

# route to main page
@app.route("/", methods=['POST', 'GET'])
def index():
    if current_user.is_authenticated:  # if user is logged in, redirect to panel
        return redirect(url_for("panel_site"))
    # check if url/token from twitter is generated if not: gen it and place in url
    if request.method == "POST":
        # create token and secret to make request when user try to login, save it in session
        session['app_key'], session['app_secret'] = request_token()
        return redirect(f"https://api.twitter.com/oauth/authorize?oauth_token={session['app_key']}")
    return render_template("index.html")

# route after auth by twitter
@app.route("/callback/", methods=['GET', 'POST'])
def callback():
    # function used after correctly login by twitter. Compares list of following from api and list of following from db and adds/delete new following if exists
    def update_following():
        # after login check if client following new person and add it to db
        # following list in db is saved int this format: "<id1> <name1>, <id2> <name2>, <id3> <name3>,"
        user_following_list = str(user.following).split(",")
        new_user_list = TwitterApi(current_user).get_following()

        # this check all following user on twitter
        if not user.following:
            new_users_to_query = ""
            for user_from_r in new_user_list['data']:
                new_users_to_query += f"{user_from_r['id']} {user_from_r['username']},"

            print(f"[{current_user.name}] added to following: {new_users_to_query}")
        else:
            # check for new following
            new_users_to_query = user.following
            users_to_add = ""
            for user_from_r in new_user_list['data']:
                user_exist_in_db = False
                if user_from_r['id'] in user.following:
                    user_exist_in_db = True

                # when in twitter api is new user but in db is not, add it
                if not user_exist_in_db:
                    users_to_add += f"{user_from_r['id']} {user_from_r['username']},"
            if users_to_add:
                print(f"[{current_user.name}] added to following: {users_to_add}")
            new_users_to_query += users_to_add

            # check for deleted following
            users_to_delete = ""
            for user_in_db in user_following_list:
                # get only id from data
                user_in_db_id = user_in_db.split(" ")[0]
                if not user_in_db_id or user_in_db_id == " ":
                    continue

                exist_on_twitter = False
                for user_from_r in new_user_list['data']:
                    if user_in_db_id == user_from_r['id']:
                        exist_on_twitter = True
                if not exist_on_twitter:
                    delete_this = f"{user_in_db},"
                    users_to_delete += delete_this
                    new_users_to_query = str(new_users_to_query).replace(delete_this, "")
            if users_to_delete:
                print(f"[{current_user.name}] deleted following: {users_to_delete}")

        conn = sqlite3.connect("database.db", check_same_thread=False)
        c = conn.cursor()
        # adds new following list to user in db
        query = f"UPDATE user SET following='{new_users_to_query}' WHERE user_id='{user.user_id}'"
        c.execute(query)
        conn.commit()

    # check if twitter authorization are ok and check is verifier in url
    if request.args.get('oauth_verifier'):
        oauth_verifier = str(request.args.get('oauth_verifier'))
        # get client authorization data
        session['data'] = access_token(session['app_key'], session['app_secret'], oauth_verifier)
        if not session['data']:  # check if user is correctly auth by twitter
            return redirect(url_for("index"))

        session['user_id'] = session['data']['user_id']
        session['screen_name'] = session['data']['screen_name']
        session['oauth_token'] = session['data']['oauth_token']
        session['oauth_token_secret'] = session['data']['oauth_token_secret']

        # check if user is already in db
        # if exist log in
        user = User.query.filter_by(name=session['screen_name']).first()
        if user:
            print(f"User {user.name} already exist")
            login_user(user)
            print(f"Log in to {current_user.name} account")
            update_following()
            session['message'] = f"Zalogowano oraz pobrano now?? list?? obserwowanych"
            return redirect(url_for("panel_site"))

        # if user is not exist
        # create new user and add to db
        user = User(session['user_id'], session['screen_name'], session['oauth_token'], session['oauth_token_secret'])
        db.session.add(user)
        db.session.commit()
        print(f"Added {session['screen_name']} user to db")
        user = User.query.filter_by(name=session['screen_name']).first()
        # log in new user redirect to panel
        login_user(user)
        update_following()
        return redirect(url_for("panel_site"))
    return redirect(url_for("index"))

# site to logout
@app.route("/logout/")
@login_required
def logout_page():
    logout_user()
    return redirect(url_for("index"))

# site when user log in
@app.route("/panel/", methods=['POST', 'GET'])
@app.route("/panel/<user_data>", methods=['POST', 'GET'])
@login_required
def panel_site(user_data='', data=''):
    conn = sqlite3.connect("database.db", check_same_thread=False)
    c = conn.cursor()

    # return messages from url_for - pass to jinja2 and print it
    try:
        message = session['message']
    except:
        message = None
    # return list of following from current_user, display it on main page
    following_list = str(current_user.following).split(",")
    # return list of monitoring users
    monitoring_list = str(current_user.spied_users).split(",")
    # remove last element from list (its empty)
    following_list = following_list[:-1]
    monitoring_list = monitoring_list[:-1]
    # return number of days - used to takes data from reports tab until thats days
    number_of_days = int(current_user.days_to_report)

    # get last follow updates and name from report table, searching by monitoring_ids and date > now-number_of_days
    # used to print in html
    # return id and None if last_follow/last_unfollow is empty
    # if user is monitoring more than one user - get list of monitoring users and last updates
    # else get user id - string
    # list of last follows or list of last unfollow it's in string format separated with , (split it and save back in users_with_updates)
    # users_with_updates[0][2] it is last follow info. users_with_updates[0][3] it is last unfollow info
    list_of_all_spied_datas = []#  stores list of list. First list contains list of data of each spied user, second contains [id, name, last_follow, last_unfollow]

    # when is monitored one person or more
    if len(monitoring_list) > 0:

        # get now time
        now = datetime.now()
        # get time to take reports
        time_to_reports = now - timedelta(days=number_of_days)

        monitoring_ids = tuple(x.split(" ")[0] for x in monitoring_list)

        # get data from report table, if in report table record with given id is not exist, set last follow/unfollow to None
        for i in monitoring_ids:
            query = f"SELECT user_id, name, last_follow, last_unfollow FROM reports WHERE user_id is {i} AND date(date) >= date('{time_to_reports}')"
            c.execute(query)
            users_with_updates = list(c.fetchall())

            # get last update date (from spied_user table)
            query = f"SELECT last_update_date FROM spied_users WHERE user_id ={i}"
            c.execute(query)
            last_update_date = c.fetchall()[0][0]

            # when record not exist for this user, get only name and id
            if not users_with_updates:
                query = f"SELECT user_id, name, last_follow, last_unfollow FROM spied_users WHERE user_id is {i}"
                c.execute(query)
                users_with_updates = list(c.fetchall())
                #print(users_with_updates)
                end_single_user_data = (users_with_updates[0][0], users_with_updates[0][1], None, None, last_update_date)
                out_datas = list(end_single_user_data)

            else:
                # join records for same user, and save data for singe spied user in list [id, name, followed, unfollowed]
                end_single_user_data = users_with_updates
                followed = ""
                unfollowed = ""
                for spied_user in end_single_user_data:
                    followed += spied_user[2]
                    unfollowed += spied_user[3]
                out_datas = [end_single_user_data[0][0], end_single_user_data[0][1], followed.split(",")[:-1], unfollowed.split(",")[:-1], last_update_date]
            list_of_all_spied_datas.append(out_datas)

    # if user is not monitoring anyone
    else:
        list_of_all_spied_datas = None

    if request.method == "POST":
        req = request.form
        session['username'] = req.get('username')
        session['button_data'] = req.get('button_panel')

        # if user is searching for user_name in html form
        if session['button_data'] == "search":
            # returns data about user
            searched_user = TwitterApi(current_user).get_user_by_name(session['username'])
            # if user_name exist on twitter redirerct to same site but with user data in url
            if searched_user:
                user_data = f"{searched_user['data']['id']}-{searched_user['data']['name']}-{searched_user['data']['username']}"
                session['message'] = "Znaleziono u??ytkownika"
                return redirect(url_for("panel_site", user_data=user_data))
            session['message'] = "Nie znaleziono u??ytkownika"
            return redirect(url_for("panel_site"))

    # handle form from settings tab
    if request.method == "POST":
        req = request.form
        session['button_data'] = req.get('settings_button')

        # when user changed number of days in settings change days_to_report in table user
        if session['button_data'] == "set_days":
            session['number_of_days'] = req.get('number_of_days')
            query = f"UPDATE user SET days_to_report={session['number_of_days']} WHERE user_id='{current_user.user_id}'"
            c.execute(query)
            conn.commit()
            print(f"[{current_user.name}] Changed nubmer of days to report to {session['number_of_days']}")
            session['message'] = f"Zmieniono ilo???? dni dla kt??rej s?? brane raporty na: {session['number_of_days']}"
            return redirect(url_for("panel_site"))

    # when user_data in url and user send post, follow/start monitoring user from user_data
    if user_data:
        if request.method == "POST":
            req = request.form
            session['button_data'] = req.get('button_panel')
            # when user want to follow searched user, get id from user_data from url
            if session['button_data'] == "follow":
                user_id = user_data.split("-")[0]
                user_name = user_data.split("-")[2]

                # when user to follow already exist
                if f"{user_id} {user_name}," in current_user.following:
                    session['message'] = f"Ju?? obserwujesz {user_name}"
                    return redirect(url_for("panel_site"))

                # follow new user and save new follow in db
                follow_user = TwitterApi(current_user).follow_user(user_id)
                new_user_in_following = current_user.following+f"{user_id} {user_name},"
                query = f"UPDATE user SET following='{new_user_in_following}' WHERE user_id='{current_user.user_id}'"
                c.execute(query)
                conn.commit()
                print(f"[{current_user.name}] added {user_name} to following")
                session['message'] = f"Dodano {user_name} do obserwowanych"
                return redirect(url_for("panel_site"))

            # when user add user to monitor
            # 1) add to user db id of user to monitor
            # 2) add to spied_user user
            # 3) add to spied_user table following list
            if session['button_data'] == "monitoruj":
                user_id = user_data.split("-")[0]
                screen_name = user_data.split("-")[1]
                user_name = user_data.split("-")[2]
                # add to user table and spied_user column format: "<id1> <name1>, <id2> <name2>, <id3> <name3>,"

                if not current_user.spied_users:
                    new_user = f"{user_id} {user_name},"
                    query = f"UPDATE user SET spied_users='{new_user}' WHERE user_id='{current_user.user_id}'"

                else:
                    # when user in monitor already exist
                    if f"{user_id} {user_name}," in current_user.spied_users:
                        session['message'] = f"Ju?? monitorujesz {user_name}"
                        return redirect(url_for("panel_site"))

                    new_user = f"{current_user.spied_users}{user_id} {user_name},"
                    query = f"UPDATE user SET spied_users='{new_user}' WHERE user_id='{current_user.user_id}'"

                # try to get data about user if to many request, run worker thats wait 15 minutes and adds user
                new_user_list = TwitterApi(current_user).get_following_by_user(user_id)
                # first try is when something with request went wrong ex. too many requests/no following list
                try:
                    new_user_list = new_user_list['data']
                    new_users_to_query = ""
                    for user_from_r in new_user_list:
                        new_users_to_query += f"{user_from_r['id']} {user_from_r['username']},"
                except:
                    # try when too many requsts
                    try:
                        if new_user_list['meta']['result_count'] == 0:
                            new_users_to_query = ""
                    except:
                        if new_user_list['status'] == 429:
                            print(f"[{current_user.name}] too many request due added new usesr to monitor. Started new worker")
                            session['message'] = f"Przepraszamy, ze wzgl??du na zbyt du???? ilo???? zapyta?? u??ytkownik {user_name} nie zosta?? dodany. Spr??buj za 15 min!"
                            return redirect(url_for("panel_site"))

                # add user to spied_users table
                spied_usr = SpiedUsers(user_id, user_name, screen_name, new_users_to_query)
                print(f"[{current_user.name}] Set's monitoring on {user_name}")
                db.session.add(spied_usr)
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                c.execute(query)
                conn.commit()
                session['message'] = f"Dodano {user_name} do monitorowanych"
                return redirect(url_for("panel_site"))
        # runs when user searched for twitter user
        return render_template("panel.html", user=current_user.name, following_list=following_list, monitoring_list=list_of_all_spied_datas, number_of_days=number_of_days, message=message, searched_user=user_data)
    # runs when url is without any parameters
    return render_template("panel.html", user=current_user.name, following_list=following_list, monitoring_list=list_of_all_spied_datas, number_of_days=number_of_days, message=message)

# used to unfollow user and remove from db
@app.route("/unfollow/<user_id>/<user_name>/", methods=['POST', 'GET'])
@login_required
def unfollow_user(user_id, user_name):
    # unfollow user and remove this follow from db
    TwitterApi(current_user).unfollow_user(user_id)
    remove_from_db = f"{user_id} {user_name},"
    conn = sqlite3.connect("database.db", check_same_thread=False)
    c = conn.cursor()

    # remove from string list of following user
    new_users_to_query = str(current_user.following).replace(remove_from_db, "")
    query = f"UPDATE user SET following='{new_users_to_query}' WHERE user_id='{current_user.user_id}'"
    c.execute(query)
    conn.commit()
    conn.close()
    print(f"[{current_user.name}] removed {user_name} from followers")
    session['message'] = f"Usuni??to z obserwacji {user_name}"
    return redirect(url_for("panel_site"))

# used to stop_monitoring user and remove from db
@app.route("/unmonitor/<user_id>/<user_name>/", methods=['POST', 'GET'])
@login_required
def unmonitor_user(user_id, user_name):
    # remove monitoring from user and remove this user from spied_user in user table
    remove_from_db = f"{user_id} {user_name},"
    conn = sqlite3.connect("database.db", check_same_thread=False)
    c = conn.cursor()

    # remove from string list of spied user
    new_users_to_query = str(current_user.spied_users).replace(remove_from_db, "")
    query = f"UPDATE user SET spied_users='{new_users_to_query}' WHERE user_id='{current_user.user_id}'"
    c.execute(query)
    conn.commit()

    # check all users, if anyone is monitoring this deleted user, keep them in spied_users table
    # if no one is monitoring this user, delete from db
    query = f"SELECT spied_users FROM user"
    c.execute(query)
    all_spied_users = c.fetchall()
    is_user_in_spied = False
    for spied_users in all_spied_users:
        try:
            if remove_from_db in spied_users[0]:
                is_user_in_spied = True
                break
        except:
            continue
    if not is_user_in_spied:
        print(f"Removing '{user_name}' from spied_users")
        query = f"DELETE FROM spied_users WHERE user_id='{user_id}'"
        c.execute(query)
        conn.commit()
    conn.close()
    print(f"[{current_user.name}] stopped monitoring {user_name}")
    session['message'] = f"Usuni??to z listy moniotrowanych {user_name}"
    return redirect(url_for("panel_site"))

# used when user want to monitor/follow more than twitter api rate limit can handle (too many requests)
# waits 15 minutuse, than try monitor given user
def add_to_monitor_worker(user_id, user_name, screen_name, query):
    pass

if __name__ == '__main__':
    db.create_all()  # crate tables in database
    monitor = Monitor()
    # flask app
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000, use_reloader=False)).start()
    # monitor twitter
    threading.Thread(target=monitor.star_monitor).start()

