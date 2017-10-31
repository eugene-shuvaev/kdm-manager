#!/usr/bin/python2.7

# standard
from bson import json_util
from bson.objectid import ObjectId
from copy import copy
from datetime import datetime, timedelta
import json
import os
import settings
import sys

# project
import utils
from models import users, settlements

logger = utils.get_logger(log_name="server")

def get_settlement_data():
    """ Returns JSON about recently updated settlements. Also serializes those
    settlements and gets their event_log. """

    recent_cutoff = datetime.now() - timedelta(hours=settings.get("application","recent_user_horizon"))

    s_info = []

    ids = utils.mdb.settlements.find({'last_accessed': {'$gte': recent_cutoff}}).distinct('_id')

    sorting_hat = {}
    for s_id in ids:
        last_updated = utils.mdb.settlement_events.find({'settlement_id': s_id}).limit(1).sort("created_on",-1)[0]['created_on']
        sorting_hat[last_updated] = s_id

    sorted_ids = []
    for timestamp in sorted(sorting_hat.keys(), reverse=True):
        sorted_ids.append(sorting_hat[timestamp])

    for s_id in sorted_ids:
        S = settlements.Settlement(_id=s_id, normalize_on_init=False)
        s_dict = copy(S.serialize('dashboard'))
        s_info.append(s_dict)

    return "[" + ",".join(s_info) + "]"


def get_user_data():
    """ Returns JSON about active and recently active users, as well as info
    about user agents, etc. """

    # first, do the user agent popularity contest, since that's simple
    results = utils.mdb.users.group(
        ['latest_user_agent'],
        {'latest_user_agent': {'$exists': True}},
        {"count": 0},
        "function(o, p){p.count++}"
    )
    sorted_list = sorted(results, key=lambda k: k["count"], reverse=True)
    for i in sorted_list:
        i["value"] = i['latest_user_agent']
        i["count"] = int(i["count"])
    ua_data = sorted_list[:25]


    # next, get active/recent users
    recent_user_cutoff = datetime.now() - timedelta(hours=settings.get("application","recent_user_horizon"))
    recent_users = utils.mdb.users.find(
        {"latest_activity": {"$gte": recent_user_cutoff}}
    ).sort("latest_activity", -1)

    # now enhance the user data to include a bit more info (to avoid having to
    #   do date calc in javascripts, etc.

    def update_user_info(u):
        try:
            U = users.User(_id=u["_id"])
        except Exception as e:
            logger.error("panel.py failed to initialize user '%s'" % u["login"])
            logger.error(e)
        u["age"] = U.get_age()
        u["latest_activity_age"] = U.get_latest_activity(return_type='age')
        u["has_session"] = U.has_session()
        u["is_active"] = U.is_active()
        u["friend_count"] = U.get_friends(int)
        u["friend_list"] = U.get_friends(list)
        u["current_session"] = utils.mdb.sessions.find_one({"_id": u["current_session"]})
        return u

    final_user_info = []
    for u in recent_users:
        try:
            final_user_info.append(update_user_info(u))
        except Exception as e:
#            logger.error("panel.py threw an exception while attempting to enhance recent user data!")
#            logger.error("User '%s' (%s) could not be initialized and enhanced! Returning it as-is..." % (u["login"], u["_id"]))
#            logger.error("Exception was: %s" % e)
            u["retrieval_error"] = True
            final_user_info.append(u)

    active_user_count = 0
    recent_user_count = 0
    for u in final_user_info:
        if u["is_active"]:
            active_user_count += 1
        else:
            recent_user_count += 1

    # create the final output dictionary
    d = {
        "meta": {
            "active_user_horizon": settings.get("application","active_user_horizon"),
            "active_user_count": active_user_count,
            "recent_user_horizon": settings.get("application","recent_user_horizon"),
            "recent_user_count": recent_user_count,
        },
        "user_agent_stats": ua_data,
        "user_info": final_user_info,
    }

    # and return it as json
    return json.dumps(d, default=json_util.default)


def serialize_system_logs():
    """ Returns JSON represent application/system log output. """

    d = {}

    log_root = settings.get("application","log_root_dir")

    for l in ["world","api","server","world_daemon","gunicorn"]:
        log_file_name = os.path.join(log_root, "%s.log" % l)
        if os.path.isfile(log_file_name):
            fh = file(log_file_name, "r")
            log_lines = fh.readlines()
            log_limit = settings.get("application","log_summary_length")
            d[l] = [line for line in reversed(log_lines[-log_limit:])]
        else:
            d[l] = ["'%s' does not exist!" % log_file_name]


    return json.dumps(d, default=json_util.default)


