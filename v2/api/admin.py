#!/usr/bin/python2.7

from bson.objectid import ObjectId
from collections import Counter

from optparse import OptionParser
import os
import sys
import time

import utils
from models import monsters, users


#
#   This is an admin script and does not contain any classes that should be
#   initialized or used by other parts of the API application (or the webapp).
#
#   If you don't know what you're doing, you should probably stay out of here,
#   as this script has the potential to create massive havoc in the MDB if used
#   incorrectly.
#
#   YHBW
#



#
#   General purpose helper functions
#

def remove_api_response_data():
    """ Drops all documents from the mdb.api_response_times collection."""
    removed = utils.mdb.api_response_times.remove()
    print("\n  Removed %s API response time records." % removed)


def dump_doc_to_cli(m, tab_spaces=2, gap_spaces=20, buffer_lines=0):
    """ Convenience function for this collection of CLI admin scripts.
    Dumps a single MDB record to stdout using print() statements.

    Also works for dict objects. You know. Becuase they're the same thing.
    """

    tab = " " * tab_spaces
    buffer = "%s" % "\n" * buffer_lines

    print(buffer)

    for k in sorted(m.keys()):
        first_spacer = " " * (gap_spaces - len(k))
        second_spacer = " " * ((gap_spaces * 2) - len(str(m[k])))
        print("%s%s%s%s%s%s" % (tab, k.decode('utf8'), first_spacer, m[k.decode('utf8')], second_spacer, type(m[k])))


    print(buffer)



#
#   Administration objects - DANGER: KEEP OUT
#

class KillboardMaintenance:
    """ Initialize one of these and then use its methods to work on the
    mdb.killboard collection. """

    def __init__(self, search_criteria={"$or": [{"handle": {"$exists": False}}, {"handle": "other"}]}, force=False):
        self.logger = utils.get_logger()
        self.search_criteria = search_criteria
        self.force = force
        self.performance = {"success": 0, "failure": 0, "deferred": 0}
        print("\tInitializing maintenance object.")
        print("\tForce == %s" % self.force)
        print("\tSearch criteria: %s" % self.search_criteria)


    def dump_others(self):
        """ Dump all killboard records whose handle is "other". """
        documents = utils.mdb.killboard.find({"handle": "other"})
        print("\n\tFound %s 'other' documents!\n" % documents.count())
        for d in documents:
            dump_doc_to_cli({
                "_id": d["_id"],
                "handle": d["handle"],
                "name": d["name"],
                "created_by": d["created_by"],
                "created_on": d["created_on"],
            })


    def check_all_docs(self):
        """ Counts how many docs match to self.search_criteria and then calls
        self.check_one_doc() until there are no more docs to check. """

        documents = utils.mdb.killboard.find(self.search_criteria)
        print("\n\t%s records match search criteria." % documents.count())

        if self.force:
            answer = raw_input("\tEnter 'Y' to process all records automatically: ")
            if answer == "Y":
                for d in documents:
                    try:
                        self.check_one_doc(d)
                    except Exception as e:
                        self.logger.exception(e)
                        self.performance["failure"] += 1
                        print("Update failed! Moving on...")
            else:
                print("\tExiting...\n")
                sys.exit(0)
        else:
            print("\tProcessing interactively...")
            for d in documents:
                self.check_one_doc(d)

        print("\n\tProcessed all records. Summary:\n")
        for k in sorted(self.performance.keys()):
            spacer = " " * (15 - len(k))
            print("\t%s%s%s" % (k, spacer, self.performance[k]))
        self.logger.info("Finished mdb.killboard update run. Results:")
        self.logger.info(self.performance)
        print("\nExiting...\n")
        sys.exit()


    def check_one_doc(self, doc, mode="interactive"):
        """ Pulls one record using self.search_criteria kwarg as a query and
        tries to initialize it as a monster object in order to suggest updates.
        Prompts to do another until there are none. """

        if doc is None:
            "No documents matching '%s' were found. Exiting..." % self.search_criteria

        # first, show the record
        print("\n\tFound one document!\n\tCurrent data:")
        try:
            dump_doc_to_cli(doc)
        except Exception as e:
            print doc
            return Exception

        # next, try to make a monster object out of it, for suggested changes
        try:
            m = monsters.Monster(name=doc["name"])
        except:
            m = None
            print("\tMonster object could not be initialized!")


        # now check for a list of required attribs on the record and suggest
        #   recommended updates

        update_dict = {"raw_name": doc["name"]}
        for var in ["level","handle","comment","name"]:
            if m is not None:
                update_dict["type"] = m.type
            elif m is None:
                update_dict["handle"] = "other"
            if hasattr(m, var):
                update_dict[var] = getattr(m, var)

        # try to normalize kill_ly

        try:
            if type(doc["kill_ly"]) == unicode:
                update_dict["kill_ly"] = int(doc["kill_ly"].split("_")[1])
        except:
            print("\tUnable to normalize 'kill_ly' value!")


        # now show all proposed updates
        print("\t%s recommended updates:" % len(update_dict))
        dump_doc_to_cli(update_dict)

        doc.update(update_dict)

        print("\tProposed record:")
        dump_doc_to_cli(doc)


        # depending on our run mode, we wrap up the operation by doing a few
        #   different things. If we're forcing, we accept the update as long as
        #   we were able to get a monster object. Otherwise, we defer.
        #   If we're running interactive, however, we let the user wither take
        #   the results or pass on them.

        if self.force:
            if m is None:
                self.performance["deferred"] += 1
            else:
                utils.mdb.killboard.save(doc)
                self.performance["success"] += 1
        else:
            answer = raw_input("\n\tSave new record to MDB? ").upper()
            if answer != "" and answer[0] == "Y":
                utils.mdb.killboard.save(doc)
                print("\tSaved updated record to MDB! Moving on...")
                self.performance["success"] += 1
            else:
                self.performance["deferred"] += 1
                print("\tDeferring update. Moving on...")

        # hang for a second at the end of the operation if we're running
        #   interactively (in order to show the user what has happened).
        if not self.force:
            time.sleep(1)


def update_user(oid, level, beta):
    """ Loads a user from the MDB, initializes it and calls the methods that set
    the patron level and the beta flag, etc. """

    if not ObjectId.is_valid(oid):
        print("The user ID '%s' is not a valid Object ID." % (oid))

    if type(beta) == bool:
        pass
    elif beta[0].upper() == 'T':
        beta = True
    else:
        beta = False

    U = users.User(_id=ObjectId(oid))
    U.set_patron_attributes(int(level), beta)

    print("\n %s Updated patron attributes:\n %s\n" % (U, U.user['patron']))


def COD_histogram():
    """ Dumps a CLI histogram of survivor causes of death (for R&D purposes,
    mainly, but also useful in verifying world stats. """

    the_dead = utils.mdb.survivors.find({"dead": {"$exists": True}, "cause_of_death": {"$exists": True}})
    cod_list = []
    for s in the_dead:
        cod_list.append(s["cause_of_death"])
    c = Counter(cod_list)
    for c in c.most_common():
        print "%s|%s" % (c[1],c[0].encode('utf-8').strip())


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-U", dest="work_with_user", default=None, help="Work with a user.")
    parser.add_option("--level", dest="user_level", default=0, help="Work with a user.")
    parser.add_option("--beta", dest="user_beta", default=False, help="Work with a user.")
    parser.add_option("-f", dest="force", action="store_true", default=False, help="Skips interactive pauses.")
    parser.add_option("-o", dest="others", action="store_true", default=False, help="Dump killboard entries whose handle is 'other'. Requires -K flag.")
    parser.add_option("-K", dest="killboard", action="store_true", default=False, help="Clean up the Killboard.")
    parser.add_option("--cod_histogram", dest="cod_histo", action="store_true", default=False, help="Dump a histogram of causes of death.")
    parser.add_option("--reset_api_response_data", dest="reset_api_response_data", action="store_true", default=False, help="Removes all data from mdb.api_response_times collection.")
    (options, args) = parser.parse_args()

    if options.work_with_user is not None:
        update_user(options.work_with_user, options.user_level, options.user_beta)

    if options.reset_api_response_data:
        remove_api_response_data()

    if options.cod_histo:
        COD_histogram()

    if options.killboard:
        K = KillboardMaintenance(force=options.force)
        K.logger.warn("%s is performing mdb.killboard maintenance!" % os.environ["USER"])
        if options.others:
            K.dump_others()
        else:
            K.check_all_docs()
