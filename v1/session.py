#!/usr/bin/env python

from bson.objectid import ObjectId
import Cookie
from datetime import datetime
import os

import admin
import assets
import html
import models
from utils import mdb, get_logger, get_user_agent, load_settings

settings = load_settings()

class Session:
    """ The properties of a Session object are these:

        self.params     -> a cgi.FieldStorage() object
        self.session    -> a mdb session object
        self.Settlement -> an assets.Settlement object
        self.User       -> an assets.User object

    """

    def __init__(self, params={}):
        """ Initialize a new Session object."""
        self.logger = get_logger()

        # these are our session attributes. Declare them all here
        self.params = params
        self.session = None
        self.Settlement = None
        self.User = None

        # we're not processing params yet, but if we have a log out request, we
        #   do it here, while we're initializing a new session object.
        if "remove_session" in self.params:
            admin.remove_session(self.params["remove_session"].value)

        # try to retrieve a session and other session attributes from mdb using
        #   the browser cookie
        self.cookie = Cookie.SimpleCookie(os.environ.get("HTTP_COOKIE"))

        if self.cookie is not None and "session" in self.cookie.keys():
            session_id = ObjectId(self.cookie["session"].value)
            self.session = mdb.sessions.find_one({"_id": session_id})
            if self.session is not None:
                user_object = mdb.users.find_one({"current_session": session_id})
                self.User = assets.User(user_object["_id"])
                self.set_current_settlement()


    def set_current_settlement(self, settlement_id=False):
        """ Tries (hard) to set the current settlement.

        The best way is to use the 'settlement_id' kwarg and feed an ObjectId
        object. If you haven't got one of those, this func will back off to the
        current session's mdb object and try to set it from there.
        """
        if settlement_id:
            self.session["current_settlement"] = settlement_id

        if self.session is not None:
            if "current_settlement" in self.session.keys():
                s_id = ObjectId(self.session["current_settlement"])
                self.Settlement = assets.Settlement(settlement_id=s_id)

            # back off to current_asset if we haven't got current_settlement
            if self.Settlement is None:
                if "current_asset" in self.session.keys():
                    self.logger.info("set settlement from current_asset %s" % self.session["current_asset"])
                    s_id = ObjectId(self.session["current_asset"])
                    self.Settlement = assets.Settlement(settlement_id=s_id)

        if self.Settlement is None:
            self.logger.debug("Unable to set 'current_settlement' for session '%s'." % self.session["_id"])
        mdb.sessions.save(self.session)


    def new(self, login):
        """ Creates a new session. Only needs a valid user login.

        Updates the session with a User object ('self.User') and a new Session
        object ('self.session'). """

        user = mdb.users.find_one({"login": login})
        mdb.sessions.remove({"login": user["login"]})

        session_dict = {
            "login": login,
            "created_on": datetime.now(),
            "current_view": "dashboard",
            "user_agent": {"is_mobile": get_user_agent().is_mobile, "browser": get_user_agent().browser },
        }
        session_id = mdb.sessions.insert(session_dict)
        self.session = mdb.sessions.find_one({"_id": ObjectId(session_id)})

        # update the user with the session ID
        user["current_session"] = session_id
        mdb.users.save(user)

        self.User = assets.User(user["_id"])

        return session_id   # passes this back to the html.create_cookie_js()


    def change_current_view(self, target_view, asset_id=False):
        """ Convenience function to update a session with a new current_view.

        'asset_id' is only mandatory if using 'view_survivor' or
        'view_settlement' as the 'target_view'.

        Otherwise, if you're just changing the view to 'dashbaord' or whatever,
        'asset_id' isn't mandatory.
        """
        self.session["current_view"] = target_view
        if target_view == "dashboard":
            self.session["current_settlement"] = None
            self.session["current_settlement"] = None
        if asset_id:
            asset = ObjectId(asset_id)
            self.session["current_asset"] = asset
            if target_view == "view_game":
                self.session["current_settlement"] = asset
                self.set_current_settlement(settlement_id = asset)
        mdb.sessions.save(self.session)
        self.session = mdb.sessions.find_one(self.session["_id"])


    def process_params(self):
        """ All cgi.FieldStorage() params passed to this object on init
        need to be processed. This does ALL OF THEM at once. """

        if "change_view" in self.params:
            self.change_current_view(self.params["change_view"].value)

        if "view_game" in self.params:
            self.change_current_view("view_game", asset_id=self.params["view_game"].value)
        if "view_settlement" in self.params:
            self.change_current_view("view_settlement", asset_id=self.params["view_settlement"].value)
        if "view_survivor" in self.params:
            self.change_current_view("view_survivor", asset_id=self.params["view_survivor"].value)

        if "remove_settlement" in self.params:
            self.change_current_view("dashboard")
            settlement_id = ObjectId(self.params["remove_settlement"].value)
            survivors = mdb.survivors.find({"settlement": settlement_id})
            for survivor in survivors:
                mdb.survivors.remove({"_id": survivor["_id"]})
                self.logger.info("User '%s' removed survivor '%s'" % (self.User.user["login"], survivor["name"]))
            self.User.get_settlements()
            mdb.settlements.remove({"_id": settlement_id})
            self.logger.info("User '%s' removed settlement '%s'" % (self.User.user["login"], settlement_id))

        if "remove_survivor" in self.params:
            self.change_current_view("dashboard")
            mdb.survivors.remove({"_id": ObjectId(self.params["remove_survivor"].value)})

        if "new" in self.params:
            if self.params["new"].value == "settlement":
                settlement_name = self.params["settlement_name"].value
                s = assets.Settlement(name=settlement_name, created_by=ObjectId(self.User.user["_id"]))
                self.set_current_settlement(s.settlement["_id"])
                self.change_current_view("view_game", asset_id=s.settlement["_id"])
            if self.params["new"].value == "survivor":
                s = assets.Survivor(params=self.params)
                self.change_current_view("view_survivor", asset_id=s.survivor["_id"])

        if "modify" in self.params:
            if self.params["modify"].value == "settlement":
                assets.update_settlement(self.params)
            if self.params["modify"].value == "survivor":
                S = assets.Survivor(survivor_id=self.params["asset_id"].value)
                S.modify(self.params)


    def current_view_html(self):
        """ This func uses session's 'current_view' attribute to render the html
        for that view.

        In a best case, we want this function to initialize a class (e.g. a
        Settlement or a Survivor or a User, etc.) and then use one of the render
        methods of that class to get html.

        Generally speaking, however, we're not above calling one of the methods
        of the html module to summon some html.

        Ideally, we will be able to refactor that kind of stuff out at some
        point, and use this function as a function that simply initalizes a
        class and uses that class's methods to get html.
        """
        output = html.meta.saved_dialog

        if self.session["current_view"] == "dashboard":
            output += html.dashboard.headline.safe_substitute(title="&#x02261; Campaigns", desc="Games you are currently playing.", h_class="purple")
            output += self.User.get_games()
            output += html.dashboard.headline.safe_substitute(title="Settlements", desc="Manage settlements created by you. You may not manage a settlement you did not create.")
            output += self.User.get_settlements(return_as="asset_links")
            output += html.dashboard.new_settlement_button
            output += html.dashboard.headline.safe_substitute(title="Survivors", desc='Manage survivors created by you or shared with you. New survivors are created from the "Game" and "Settlement" views.')
            survivors = self.User.get_survivors()
            for s in survivors:
                S = assets.Survivor(survivor_id=s["_id"])
                output += S.asset_link(include=["dead", "retired", "hunt_xp", "settlement_name"])
            output += html.dashboard.headline.safe_substitute(title="System", desc="KD:M Manager! Version %s.<hr/><p>login: %s</p>" % (settings.get("application","version"), self.User.user["login"]))
        elif self.session["current_view"] == "view_game":
            if self.Settlement.settlement["created_by"] == self.User.user["_id"]:
                output += self.Settlement.asset_link(fixed=True, link_text="Edit")
            output += self.Settlement.render_html_summary(user_id=self.User.user["_id"])
            # if session user owns the settlement, let him edit it
        elif self.session["current_view"] == "new_settlement":
            output += html.dashboard.new_settlement_form
        elif self.session["current_view"] == "new_survivor":
            options = self.User.get_settlements(return_as="html_option")
            output += html.dashboard.new_survivor_form.safe_substitute(home_settlement=self.session["current_settlement"], user_email=self.User.user["login"], created_by=self.User.user["_id"])
        elif self.session["current_view"] == "view_settlement":
            settlement = mdb.settlements.find_one({"_id": self.session["current_asset"]})
            self.set_current_settlement(ObjectId(settlement["_id"]))
            S = assets.Settlement(settlement_id = settlement["_id"])
            output += S.render_html_form()
        elif self.session["current_view"] == "view_survivor":
            survivor = mdb.survivors.find_one({"_id": self.session["current_asset"]})
            S = assets.Survivor(survivor_id = survivor["_id"])
            output += S.render_html_form()
        else:
            output += "UNKNOWN VIEW!!!"

        if self.session["current_view"] != "dashboard":
            output += html.dashboard.home_button

        output += html.meta.log_out_button.safe_substitute(session_id=self.session["_id"])
        return output
