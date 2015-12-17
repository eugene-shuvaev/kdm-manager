#!/usr/bin/env python

from bson.objectid import ObjectId
from datetime import datetime, timedelta
from hashlib import md5
import operator
from optparse import OptionParser
import os
from validate_email import validate_email

import assets
import html
from utils import mdb, get_logger, get_user_agent, load_settings, ymdhms, hms, days_hours_minutes


logger = get_logger()
settings = load_settings()

#
#   Maintenance and administrative functions
#

def prune_sessions():
    """ Removes sessions older than 24 hours. """
    yesterday = datetime.now() - timedelta(days=1)
    logger.debug("Searching for sessions older than %s to prune..." % yesterday)
    old_sessions = mdb.sessions.find({"created_on": {"$lt": yesterday}}).sort("created_on")
    logger.debug("%s sessions found." % old_sessions.count())

    pruned_sessions = 0
    for s in old_sessions:
        s_id = s["_id"]
        logger.debug("Pruning old session '%s' (%s)" % (s_id, s["login"]))
        remove_session(s_id, "admin")
        pruned_sessions += 1

    if pruned_sessions > 0:
        logger.info("Pruned %s old sessions." % pruned_sessions)

#
#   administrative helper functions for user-land
#

def create_new_user(login, password, password_again):
    """ Creates a new user. Returns False if the passwords don't match;
    returns None if the email address is bogus. Returns True and logs a user in
    if we create a new user successfully. """

    login = login.lower()   # normalize email address on creation

    if password != password_again:
        logger.error("New user creation failed! %s %s %s" % (login, password, password_again))
        return False
    else:
        logger.debug("Creating user '%s' from %s" % (login, get_user_agent()))

        # email validation
        if settings.getboolean("users", "validate_email"):
            validated = validate_email(login, verify=True)
            if validated is None:
                logger.critical("Unable to validate email address '%s'." % login)
                logger.error(validated)
                return None
        else:
            logger.debug("Skipping email validation...")

        # create the user and update mdb
        user_dict = {
            "created_on": datetime.now(),
            "login": login,
            "password": md5(password).hexdigest(),
        }
        try:
            mdb.users.insert(user_dict)
        except Exception as e:
            logger.error("An error occurred while registering a new user!")
            logger.exception(e)
            return False
        mdb.users.create_index("login", unique=True)
        logger.info("New user '%s' created successfully!" % login)
        return True



def authenticate(login, password):
    """ Tries to authenticate a user and log him in. Returns None if the user's
    login cannot be found. Returns False if he enters a bad password.

    Logs him in and creates a session, otherwise.

    email addresses are always normalized using .lower()
    """

    user = mdb.users.find_one({"login": login})

    if user is None:
        return None

    if md5(password).hexdigest() == user["password"]:
        user["latest_sign_in"] = datetime.now()
        mdb.users.save(user)
        logger.debug("User '%s' authenticated successfully (%s)." % (login, get_user_agent()))
        prune_sessions()
        return True
    else:
        logger.debug("User '%s' FAILED to authenticate successfully." % login)
        return False


def remove_session(session_id, login):
    """ If you have a session_id (as a string or an ObjectId) and a login, you
    can remove a session from anywhere. """

    s = ObjectId(session_id)
    mdb.sessions.remove({"_id": s})
    logger.debug("User '%s' removed session '%s' successfully." % (login, session_id))



#
#   Interactive CLI admin stuff; not to be used in user-land
#



def ls_documents(collection, sort_on="created_on"):
    """ Dumps a list- or ls-style rendering of a collection's contents. """

    if collection == "users":
        sort_on = "latest_activity"

    for d in mdb[collection].find().sort(sort_on):
        output = " "
        if sort_on in d.keys():
            output += d[sort_on].strftime("%Y-%m-%d %H:%M:%S")
            output += " "
        output += str(d["_id"])
        output += " - "
        if collection == "users" or collection == "sessions":
            output += d["login"]
        else:
            output += d["name"]
            output += " <%s> " % mdb.users.find_one({"_id": d["created_by"]})["login"]
        output += " (%s)" % d["created_on"]
        print output


def rm_collection(collection):
    """ Drops an entire collection from mdb. Serious business. """

    mdb[collection].remove()


def dump_document(collection, doc_id):
    """ Prints an object to stdout in a semi-pretty way, e.g. for review or
    analysis, etc. """

    key_length = 31
    document = mdb[collection].find_one({"_id": ObjectId(doc_id)})
    print("")
    for a in sorted(document.keys()):
        print(" %s%s%s" % (a, " " * (key_length - len(a)), document[a]))
    print("")


def update_survivor(operation, s_id=None, attrib=False, attrib_value=False):
    """ """
    print("Searching for survivor _id '%s'..." % s_id)
    survivor = mdb.survivors.find_one({"_id": ObjectId(s_id)})
    if survivor is None:
        print("Could not retrieve survivor! Exiting...\n")
        return None

    print("\n\tSurvivor found!\n")
    dump_document("survivors", survivor["_id"])

    if operation == "remove":
        print(" Target attrib is '%s'" % attrib)
        print(" survivor['%s'] -> %s" % (attrib, survivor[attrib]))
        print(" Tarvet value is '%s'" % attrib_value)
        if attrib_value not in survivor[attrib]:
            print(" Target value '%s' not in attribute! Exiting...\n" % attrib_value)
            return None
        else:
            manual_approve = raw_input("\n    Remove '%s' from %s?\n\tType YES to proceed: " % (attrib_value, survivor[attrib]))
            if manual_approve == "YES":
                survivor[attrib].remove(attrib_value)
                mdb.survivors.save(survivor)
                print("\n  Survivor updated!\n")
            else:
                print("    Aborting...\n")

def remove_document(collection, doc_id):
    """ Removes a single document (by _id) from the specified collection."""

    doc_id = ObjectId(doc_id)
    if collection == "settlements":
        settlement = mdb.settlements.find_one({"_id": doc_id})
        survivors = mdb.survivors.find({"settlement": doc_id})
        death_count = 0
        for s in survivors:
            mdb.survivors.remove({"_id": s["_id"]})
            death_count += 1
        logger.info("[ADMIN] Removed %s survivors." % death_count)
    mdb[collection].remove({"_id": doc_id})
    logger.info("[ADMIN] Removed '%s' from mdb.%s" % (doc_id, collection))

def pretty_view_user(u_id):
    """ Prints a pretty summary of the user and his assets to STDOUT. """

    User = assets.User(u_id)

    if User.user is None:
        print("Could not retrieve user info from mdb.")
        return None

    print("\n\tUser Summary!\n\n _id: %s\n login: %s\n created: %s\n" % (User.user["_id"], User.user["login"], User.user["created_on"]))
    for u_key in sorted(User.user.keys()):
        if u_key not in ["_id", "login", "created_on", "activity_log"]:
            print(" %s: %s" % (u_key, User.user[u_key]))
    print("")


    def asset_repr(a, type=False):
        if type == "settlement":
            return " %s - %s - LY: %s (%s/%s)" % (a["_id"], a["name"], a["lantern_year"], a["population"], a["death_count"])
        if type == "survivor":
            return " %s - %s [%s] %s" % (a["_id"], a["name"], a["sex"], a["email"])

    if User.settlements == []:
        print(" No settlements.\n")
    else:
        print("\t%s settlements:\n" % len(User.settlements))
        for settlement in User.settlements:
            print asset_repr(settlement, "settlement")
            for survivor in mdb.survivors.find({"settlement": settlement["_id"]}):
                print "  %s" % asset_repr(survivor, "survivor")
            print("")

    if User.survivors == []:
        print(" No survivors.\n")
    else:
        print("\t%s survivors:\n" % len(User.survivors))
        for survivor in User.survivors:
            print asset_repr(survivor, "survivor")
    print("")

    if "activity_log" in User.user.keys():
        print(" Last 10 Actions:")
        for entry in User.user["activity_log"]:
            dt, action = entry
            print("   %s | %s" % (dt.strftime(ymdhms), action))
    print("")


def initialize():
    """ Completely initializes the application. Scorched earth. """
    for collection in ["users", "sessions", "survivors", "settlements"]:
        mdb[collection].remove()


def play_summary():
    """ Summarizes play sessions. """

    print("\n\t\tRecent Activity:\n")
    users = mdb.users.find({"latest_sign_in": {"$exists": True}, "latest_activity": {"$exists": True}}).sort("latest_activity", -1)
    for u in users[:5]:
        output = " "
        output += "%s - %s (%s):\n " % (u["login"], u["_id"], u["latest_user_agent"])
        duration = u["latest_activity"] - u["latest_sign_in"]
        dur_minutes = duration // 60
        output += "    %s - %s (%s)\n" % (u["latest_sign_in"].strftime(ymdhms), u["latest_activity"].strftime(ymdhms), dur_minutes)
        output += "     Latest Action: '%s' (%s minutes ago)\n" % (u["latest_action"], (datetime.now() - u["latest_activity"]).seconds // 60)
        print(output)




def get_latest_casualty(return_type=False):
    """ Returns a string of the most recently killed survivor."""

    dead_men = mdb.survivors.find({"dead": {"$exists": True}}).sort("died_on", -1)
    if dead_men.count() == 0:
        return None
    else:
        d = dead_men[0]

    settlement = mdb.settlements.find_one({"_id": d["settlement"]})
    d["settlement_name"] = settlement["name"]
    if return_type == "string":
        return "%s [%s] - XP: %s / Courage: %s / Understanding: %s" % (d["name"], d["sex"], d["hunt_xp"], d["Courage"], d["Understanding"])
    else:
        return d


def motd():
    """ Creates a CLI MoTD. """
    users = mdb.users.find()
    sessions = mdb.sessions.find()
    settlements = mdb.settlements.find()
    survivors = mdb.survivors.find()

    print("\n %s users (%s sessions)\n %s settlements\n %s survivors" % (users.count(), sessions.count(), settlements.count(), survivors.count()))

    recent_user_agents = {}
    for u in users:
        if "latest_user_agent" in u.keys():
            ua = u["latest_user_agent"]
        else:
            ua = "UNKNOWN"
        if ua not in recent_user_agents.keys():
            recent_user_agents[ua] = 1
        else:
            recent_user_agents[ua] += 1
    print("\n Recent user agent round-up (top 5):")
    sorted_ua_dict = sorted(recent_user_agents.items(), key=operator.itemgetter(1), reverse=True)
    for ua in sorted_ua_dict[:6]:
        ua_string, ua_count = ua
        if ua_string != "UNKNOWN":
            print("   %s --> %s" % (ua_string, ua_count))
    print("")


def toggle_admin_status(user_id):
    """ Makes a user an admin or, if they're already an admin, strips them of
    the attribute. """
    u_id = ObjectId(user_id)
    user = mdb.users.find_one({"_id": u_id})
    login = user["login"]
    if "admin" in user.keys():
        del user["admin"]
        print("Admin permission removed from '%s'." % login)
    else:
        user["admin"] = datetime.now()
        print("Admin permission added for '%s'." % login)
    mdb.users.save(user)


def update_user_password(user_id, password):
    u_id = ObjectId(user_id)
    User = assets.User(user_id=u_id)
    User.update_password(password)


    #
    #   Admin Panel!
    #

class Panel:
    def __init__(self):
        self.logger = get_logger()

    def get_recent_users(self):
        """ Gets users from mdb who have done stuff within our time horizon for
        'recent' sessions and returns them. """
        hours_ago = settings.getint("application", "session_horizon")
        recent_cut_off = datetime.now() - timedelta(hours=hours_ago)
        return mdb.users.find({"latest_activity": {"$gte": recent_cut_off}}).sort("latest_activity", -1)

    def get_last_n_log_lines(self, lines):
        log_path = os.path.join(settings.get("application", "log_dir"), "index.log")
        index_log = file(log_path, "r")
        return index_log.readlines()[-lines:]

    def render_html(self):
        recent_users = self.get_recent_users()

        output = html.panel.headline.safe_substitute(
            recent_users_count = recent_users.count(),
        )


        for user in recent_users:
            User = assets.User(user_id=user["_id"])
            output += html.panel.user_status_summary.safe_substitute(
                user_name = User.user["login"],
                ua = User.user["latest_user_agent"],
                latest_activity = User.user["latest_activity"].strftime(ymdhms),
                latest_action = User.user["latest_action"],
            )

        output += "<hr/><h1>index.log</h1>"

        log_lines = self.get_last_n_log_lines(15)
        for l in reversed(log_lines):
            output += html.panel.log_line.safe_substitute(line=l)

        return output




if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-c", dest="collection", help="Specify a collection to work with", metavar="settlements", default=False)

    parser.add_option("-s", dest="survivor", help="Specify a survivor to work with.", metavar="566e228654922d30c47b8704", default=False)
    parser.add_option("--survivor_attrib", dest="survivor_attrib", help="Specify a survivor attrib to modify.", metavar="attributes_and_impairments", default=False)
    parser.add_option("--remove_attrib", dest="remove_attrib", help="Remove attrib from survivor", metavar="<b>Cancer:</b> No description.", default=False)

    parser.add_option("-l", dest="list_documents", help="List documents in a collection", metavar="survivors", default=False)
    parser.add_option("-v", dest="view_document", help="View/dump a document to stdout (requires -c)", metavar="565a1829421aa96b33d1c8bb", default=False)
    parser.add_option("-r", dest="remove_document", help="Remove a single document (requires -c)", metavar="29433d1c8b56581ab21aa96b", default=False)
    parser.add_option("-R", dest="drop_collection", help="Drop all docs in a collection.", metavar="users", default=False)

    parser.add_option("--play_summary", dest="play_summary", help="Summarize play sessions for users.", action="store_true", default=False)

    parser.add_option("-u", dest="user_id", help="Specify a user to work with.", default=False)
    parser.add_option("-p", dest="user_pass", help="Update a user's password (requires -u).", default=False)

    parser.add_option("--user", dest="pretty_view_user", help="Print a pretty summary of a user", metavar="5665026954922d076285bdec", default=False)
    parser.add_option("--admin", dest="toggle_admin", help="toggle admin status for a user _id", default=False)

    parser.add_option("--initialize", dest="initialize", help="Burn it down.", action="store_true", default=False)
    (options, args) = parser.parse_args()

#    if args == []:
#        motd()

    if options.user_id and options.user_pass:
        update_user_password(options.user_id, options.user_pass)

    if options.toggle_admin:
        toggle_admin_status(options.toggle_admin)

    if options.initialize:
        manual_approve = raw_input('Initialize the project and remove all data? Type "YES" to proceed: ')
        if manual_approve == "YES":
            initialize()
        print("\nProject initialized! ALL DATA REMOVED!!\nExiting...\n")

    if options.list_documents:
        ls_documents(options.list_documents)
    if options.drop_collection:
        rm_collection(options.drop_collection)

    if options.collection:
        if options.view_document:
            dump_document(options.collection, options.view_document)
        if options.remove_document:
            remove_document(options.collection, options.remove_document)

    if options.pretty_view_user:
        pretty_view_user(options.pretty_view_user)

    if options.survivor:
        if options.survivor_attrib:
            if options.remove_attrib:
                update_survivor("remove", s_id=options.survivor, attrib=options.survivor_attrib, attrib_value=options.remove_attrib)

    if options.play_summary:
        motd()
        play_summary()
