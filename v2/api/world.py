#!/usr/bin/python2.7


# general imports
from bson import json_util
from bson.objectid import ObjectId
import daemon
from datetime import datetime, timedelta
import json
from lockfile.pidlockfile import PIDLockFile
from optparse import OptionParser
import os
from pwd import getpwuid
import shutil
import subprocess
import stat
import sys
import time

# local imports
from assets import world as world_assets
import settings
import utils








#
# World object below
#

class World:

    def __init__(self):
        self.logger = utils.get_logger()
        self.assets = world_assets.models


    def refresh_all_assets(self, force=False):
        """ Updates all assets. Set 'force' to True to ignore 'max_age' and
        'asset_max_age'. A wrapper for self.refresh_asset(). """

        self.logger.info("Refreshing all warehouse assets...")
        for asset_key in self.assets.keys():
            self.refresh_asset(asset_key, force=force)


    def refresh_asset(self, asset_key=None, force=False):
        """ Updates a single asset. Checks the 'max_age' of the asset and falls
        back to settings.world.asset_max_age if it can't find one.

        Set 'force' to True if you want to force a refresh, regardless of the
        asset's age. """


        max_age = settings.get("world", "asset_max_age") * 60

        asset_dict = self.assets[asset_key]
        if "max_age" in asset_dict.keys():
            max_age = asset_dict["max_age"] * 60

        # now determine whether we want to refresh it
        do_refresh = False
        current_age = None


        mdb_asset = utils.mdb.world.find_one({"handle": asset_key})
        if mdb_asset is None:
            self.logger.debug("Asset handle '%s' not found in mdb!" % asset_key)
            do_refresh = True
        else:
            current_age = datetime.now() - mdb_asset["created_on"]
        if current_age is None:
            do_refresh = True
        elif current_age.seconds > max_age:
            self.logger.debug("Asset '%s' has a current age of %s seconds (max age is %s seconds)." % (asset_key, current_age.seconds, max_age))
            do_refresh = True
        if force:
            do_refresh = True

        # now do the refresh, if necessary
        if do_refresh:
#            self.logger.debug("Refreshing '%s' asset..." % asset_key)
            try:
                exec "value = self.%s()" % asset_key
                asset_dict.update({"handle": asset_key})
                asset_dict.update({"created_on": datetime.now()})
                asset_dict.update({"value": value})
                self.update_mdb(asset_dict)
                self.logger.debug("Updated '%s' asset in mdb." % asset_key)
            except AttributeError:
                self.logger.error("Could not refresh '%s' asset: no method available." % asset_key)
            except Exception as e:
                self.logger.error("Exception caught while refreshing asset!")
                self.logger.exception(e)


    def update_mdb(self, asset_dict):
        """ Creates a new document in mdb.world OR, if this handle already
        exists, updates an existing one. """

        existing_asset = utils.mdb.world.find_one({"handle": asset_dict["handle"]})
        if existing_asset is not None:
            asset_dict["_id"] = existing_asset["_id"]
        utils.mdb.world.save(asset_dict)
        utils.mdb.world.create_index("handle", unique=True)


    def remove(self, asset_id):
        """ Removes a single asset _id from mdb.world. """
        _id = ObjectId(asset_id)
        if utils.mdb.world.find_one({"_id": _id}) is not None:
            utils.mdb.world.remove(_id)
            self.logger.warn("Removed asset _id '%s'" % asset_id )
        else:
            self.logger.warn("Object _id '%s' was not found!" % asset_id)


    def list(self, output_type="JSON"):
        """ Dump world data in a few different formats."""

        d = {"world": {}}
        for asset in utils.mdb.world.find():
            d["world"][asset["handle"]] = asset
            d["world"][asset["handle"]]["age_in_seconds"] = (datetime.now() - asset["created_on"]).seconds
            if "max_age" in asset.keys():
                del d["world"][asset["handle"]]["max_age"]

        if output_type == "CLI":
            print("\n\tWarehouse data:\n")
            spacer = 25
            for k, v in d["world"].iteritems():
                utils.cli_dump(k, spacer, v)
                print("")
        elif output_type == "dict":
            return d
        elif output_type == "JSON":
            return json.dumps(d, default=json_util.default)


    def dump(self, asset_handle):
        """ Prints a single asset to STDOUT. CLI admin functionality. """

        asset = utils.mdb.world.find_one({"handle": asset_handle})
        print("\n\t%s\n" % asset_handle)
        spacer = 20
        for k, v in asset.iteritems():
            utils.cli_dump(k, spacer, v)
        print("\n")



    #
    # refresh method helpers and shortcuts
    #


    def get_eligible_documents(self, collection=None, attrib=None):
        """ Returns a dict representing the baseline mdb query for a given
        collection. """

        # common list of banned names (across all collections)
        ineligible_names = [
            "test","Test","TEST",
            "unknown", "Unknown","UNKNOWN",
            "Anonymous","anonymous",
        ]

        # base query dict; excludes ineligible names and docs w/o 'attrib'
        query = {
            "name": {"$nin": ineligible_names},
            attrib: {"$exists": True},
        }

        # customize based on collection name
        if collection == "settlements":
            query.update({
                "lantern_year": {"$gt": 0},
                "population": {"$gt": 1},
                "death_count": {"$gt": 0},
            })
        elif collection == "survivors":
            query.update({
                "dead": {"$exists": False},
            })
        elif collection == "users":
            query.update({
                "removed": {"$exists": False},
            })
        else:
            self.logger.error("The collections '%s' is not within the scope of world.py")


        return utils.mdb[collection].find(query)


    def get_minmax(self, collection=None, attrib=None):
        """ Gets the highest/lowest value for 'attrib' across all eligible
        documents in 'collection'. Returns a tuple. """

        sample_set = self.get_eligible_documents(collection, attrib)

        data_points = []
        for sample in sample_set:
            data_points.append(int(sample[attrib]))
        return min(data_points), max(data_points)


    def get_average(self, collection=None, attrib=None, precision=2, return_type=float):
        """ Gets the average value for 'attrib' across all elgible documents in
        'collection' (as determined by the world.eligible_documents() method).

        Returns a float rounded to two decimal places by default. Use the
        'precision' kwarg to modify rounding precision and 'return_type' to
        coerce the return a str or int as desired. """

        sample_set = self.get_eligible_documents(collection, attrib)

        data_points = []
        for sample in sample_set:
            try:
                data_points.append(return_type(sample[attrib]))
            except: # in case we need to coerce a list to an int
                data_points.append(return_type(len(sample[attrib])))
        result = reduce(lambda x, y: x + y, data_points) / float(len(data_points))

        # coerce return based on 'return_type' kwarg
        if return_type == int:
            return result
        elif return_type == float:
            return round(result, precision)
        else:
            return None


    def get_list_average(self, data_points):
        """ Super generic function for turning a list of int or float data into
        a float average. """

        list_length = float(len(data_points))
        result = reduce(lambda x, y: x + y, data_points) / list_length
        return round(result,2)



    #
    # actual refresh methods from here down (nothing after)
    #

    def dead_survivors(self):
        return utils.mdb.the_dead.find().count()

    def live_survivors(self):
        return utils.mdb.survivors.find({"dead": {"$exists": False}}).count()

    def total_survivors(self):
        return utils.mdb.survivors.find().count()

    def total_settlements(self):
        return utils.mdb.settlements.find().count()

    def total_users(self):
        return utils.mdb.users.find().count()

    def total_users_last_30(self):
        return utils.mdb.users.find({"latest_sign_in": {"$gte": utils.thirty_days_ago}}).count()

    def abandoned_settlements(self):
        return utils.mdb.settlements.find(
            {"$or": [
                {"removed": {"$exists": True}},
                {"abandoned": {"$exists": True}}
            ]
        }).count()

    def active_settlements(self):
        return self.total_settlements() - self.abandoned_settlements()

    def new_settlements_last_30(self):
        return utils.mdb.settlements.find({"created_on": {"$gte": utils.thirty_days_ago}}).count()

    def recent_sessions(self):
        return utils.mdb.users.find({"latest_activity": {"$gte": utils.recent_session_cutoff}}).count()

    # min/max queries
    def max_pop(self):
        return self.get_minmax("settlements","population")[1]

    def max_death_count(self):
        return self.get_minmax("settlements","death_count")[1]

    def max_survival_limit(self):
        return self.get_minmax("settlements","survival_limit")[1]

    # settlement averages
    def avg_ly(self):
        return self.get_average("settlements", "lantern_year")

    def avg_lost_settlements(self):
        return self.get_average("settlements", "lost_settlements")

    def avg_pop(self):
        return self.get_average("settlements", "population")

    def avg_death_count(self):
        return self.get_average("settlements", "death_count")

    def avg_survival_limit(self):
        return self.get_average("settlements", "survival_limit")

    def avg_milestones(self):
        return self.get_average("settlements", "milestone_story_events")

    def avg_storage(self):
        return self.get_average("settlements", "storage")

    def avg_defeated_monsters(self):
        return self.get_average("settlements", "defeated_monsters")

    def avg_expansions(self):
        return self.get_average("settlements", "expansions")

    def avg_innovations(self):
        return self.get_average("settlements", "innovations")

    # survivor averages
    def avg_disorders(self):
        return self.get_average("survivors", "disorders")

    def avg_abilities(self):
        return self.get_average("survivors", "abilities_and_impairments")

    def avg_hunt_xp(self):
        return self.get_average("survivors", "hunt_xp")

    def avg_insanity(self):
        return self.get_average("survivors", "Insanity")

    def avg_courage(self):
        return self.get_average("survivors", "Courage")

    def avg_understanding(self):
        return self.get_average("survivors", "Understanding")

    def avg_fighting_arts(self):
        return self.get_average("survivors", "fighting_arts")

    # user averages
    # these happen in stages in order to work around the stable version of mdb
    # (which doesn't support $lookup aggregations yet). 
    # Not super DRY, but it still beats using a relational DB.

    def avg_user_settlements(self):
        data_points = []
        for user in utils.mdb.users.find():
            data_points.append(utils.mdb.settlements.find({"created_by": user["_id"]}).count())
        return self.get_list_average(data_points)

    def avg_user_survivors(self):
        data_points = []
        for user in utils.mdb.users.find():
            data_points.append(utils.mdb.survivors.find({"created_by": user["_id"]}).count())
        return self.get_list_average(data_points)

    def avg_user_avatars(self):
        data_points = []
        for user in utils.mdb.users.find():
            data_points.append(utils.mdb.survivors.find({"created_by": user["_id"], "avatar": {"$exists": True}}).count())
        return self.get_list_average(data_points)




#
#   daemon code here
#

class WorldDaemon:
    """ The world daemon determines whether to update a given world asset (see
    assets/world.py) based on the default 'asset_max_age' in settings.cfg or
    based on the custom 'max_age' attribute of a given asset.

    Since the daemon does not always update all assets, it minimizes resource
    usage and can therefore be left running without whaling on CPU and/or
    physical memory.

    Finally, the world daemon DOES NOT actually refresh/update or otherwise
    gather any data or run any queries. Rather, it initializes a World object
    (see above) and then works with that object as necessary. """

    def __init__(self):

        self.logger = utils.get_logger(log_name="world_daemon")

        self.pid_file_path = os.path.abspath(settings.get("world","daemon_pid_file"))
        self.pid_dir = os.path.dirname(self.pid_file_path)
        self.set_pid()

        self.kill_command = "/bin/kill"


    def check_pid_dir(self):
        """ Checks to see if the pid directory exists and is writable. Creates a
        a new dir if it needs to do so. Also logs a WARN if the user requesting
        the check is not the owner of the pid dir. """

        if not os.path.isdir(self.pid_dir):
            self.logger.error("PID dir '%s' does not exist!" % self.pid_dir)
            try:
                shutil.os.mkdir(self.pid_dir)
                self.logger.critical("Created PID dir '%s'!" % self.pid_dir)
            except Exception as e:
                self.logger.error("Could not create PID dir '%s'!" % self.pid_dir)
                self.logger.exception(e)
                sys.exit(255)

        pid_dir_owner = getpwuid(os.stat(self.pid_dir).st_uid).pw_name
        self.logger.debug("PID dir '%s' is owned by '%s'." % (self.pid_dir, pid_dir_owner))
        if pid_dir_owner != os.environ["USER"]:
            self.logger.warn("PID dir owner is not the current user!")


    def set_pid(self):
        """ Updates 'self.pid' with the int in the daemon pid file. Returns None
        if there is no file or the file cannot be parsed. """
        self.pid = None
        if os.path.isfile(self.pid_file_path):
            try:
                self.pid = int(file(self.pid_file_path, "rb").read().strip())
            except Exception as e:
                self.logger.exception(e)


    def command(self, command=None):
        """ Executes a daemon command. Think of this as the router for incoming
        daemon commands/operations. Register all commands here. """

        if command == "start":
            self.start()
        elif command == "stop":
            self.stop()
        elif command == "restart":
            self.stop()
            time.sleep(1)
            self.start()
        elif command == "status":
            self.dump_status()

    def start(self):
        """ Starts the daemon. """
        self.logger.info("Starting World Daemon...")

        # pre-flight sanity checks and initialization tasks
        self.check_pid_dir()

        if os.getuid() == 0:
            self.logger.error("The World Daemon may not be started as root!")
            sys.exit(255)

        context = daemon.DaemonContext(
            working_directory = (settings.get("api","cwd")),
            detach_process = True,
            umask=0o002, pidfile=PIDLockFile(self.pid_file_path),
            files_preserve = [self.logger.handlers[0].stream],
        )

        with context:
            while True:
                try:
                    self.run()
                except Exception as e:
                    self.logger.error("An exception occured during daemonization!")
                    self.logger.exception(e)
                    raise


    def run(self):
        """ A run involves checking all warehouse assets and, if they're older
        than their 'max_age' attrib (default to the world.asset_max_age value),
        it refreshes them.

        Once finished, it sleeps for world.refresh_interval, which is measured
        in minutes. """

        W = World()
        W.refresh_all_assets()
        self.logger.debug("World Daemon will sleep for %s minutes..." % settings.get("world","refresh_interval"))
        time.sleep(settings.get("world","refresh_interval") * 60)


    def stop(self):
        """ Stops the daemon. """
        self.set_pid()

        if self.pid is not None:
            self.logger.warn("Preparing to kill PID %s" % self.pid)
            p = subprocess.Popen([self.kill_command, str(self.pid)], stdout=subprocess.PIPE)
            out, err = p.communicate()
            self.logger.warn("Process killed.")
        else:
            self.logger.debug("Daemon is not running. Ignoring stop command...")


    def get_uptime(self):
        """ Uses the pid file to determine how long the daemon has been active.
        Returns None if the daemon isn't active. Otherwise, this returns a raw
        timedelta. """

        if os.path.isfile(self.pid_file_path):
            pid_file_age = time.time() - os.stat(self.pid_file_path)[stat.ST_MTIME]
            seconds = timedelta(seconds=pid_file_age).seconds
            return utils.seconds_to_hms(seconds)
        else:
            return None


    def dump_status(self, output_type="CLI"):
        """ Prints daemon status to stdout. """

        active = False
        if self.pid is not None:
            active = True

        d = {}
        d["active"] = active
        d["uptime_hms"] = self.get_uptime()
        d["pid"] = self.pid
        d["pid_file"] = self.pid_file_path
        d["assets"] = utils.mdb.world.find().count()

        if output_type == "dict":
            return d
        elif output_type == "CLI":
            spacer = 15
            print("\n\tWorld Daemon stats:\n")
            for k, v in d.iteritems():
                utils.cli_dump(k, spacer, v)
            print("\n")




if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-r", dest="refresh", action="store_true", default=False, help="Force a warehouse refresh")
    parser.add_option("-a", dest="asset", default=False, help="Print a single asset to STDOUT")
    parser.add_option("-l", dest="list", default=False, help="List warehoused data")
    parser.add_option("-R", dest="remove_one", default=None, help="Remove an object _id from the warehouse")
    parser.add_option("-d", dest="daemon_cmd", help="Daemon controls: status|start|stop|restart", default=None)
    (options, args) = parser.parse_args()

    # process specific/manual world operations first
    W = World()
    if options.remove_one is not None:
        W.remove(options.remove_one)
    if options.refresh:
        W.logger.debug("Beginning forced asset refresh...")
        W.refresh_all_assets(force=True)
    if options.asset:
        print(W.dump(options.asset))
    if options.list:
        print(W.list(options.list))

    # now process daemon commands
    if options.daemon_cmd is not None:
        if options.daemon_cmd in ["status","start","stop","restart"]:
            D = WorldDaemon()
            D.command(options.daemon_cmd)
        else:
            print("\nInvalid daemon command. Use -h for help. Exiting...\n")
            sys.exit(255)
