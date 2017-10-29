# coding=utf-8
#!/usr/bin/env python

#   standard
from datetime import datetime, timedelta
from string import Template
import sys

#   custom
import admin
import api
#import game_assets
from session import Session
from utils import load_settings, mdb, get_logger, get_latest_update_string

settings = load_settings()
logger = get_logger()

user_error_msg = Template("""
    <div id="user_error_msg" class="$err_class" onclick="hide('user_error_msg')">$err_msg</div>
    """)


class panel:
    headline = Template("""\n\
    <meta http-equiv="refresh" content="60">

    <form method="POST" action="">
        <input type="hidden" name="change_view" value="dashboard"/>
        <button id="admin_panel_floating_dashboard">Dashboard</button>
    </form>

    <div class="admin_panel_left">
        <!-- nothing here -->
    </div> <!-- admin_panel_left -->

    <div class="admin_panel_right">
        <h3>Administration</h3>
        $admin_stats
        $admins
        $response_times
        $world_daemon
    </div>

    <hr class="invisible"/><br/><hr/><h1>Recent User Activity</h1>

    \n""")
    panel_table_top = '<table id="panel_aux_table">\n'
    panel_table_header = Template('\t<tr><th colspan="2">$title</th></tr>\n')
    panel_table_row = Template('\t<tr class="$zebra"><td class="key">$key</td><td>$value</td></tr>\n')
    panel_table_bot = '</table>\n'
    log_line = Template("""\n\
    <p class="$zebra">$line</p>
    \n""")
    user_status_summary = Template("""\n\
    <div class="panel_block">
        <table class="panel_recent_user">
            <tr class="gradient_blue bold"><th colspan="3">$user_name [$u_id]</th></tr>
            <tr><td class="key">User Created:</td><td>$user_created_on_days days ago</td><td class="m_ago">$user_created_on</td></tr>
            <tr><td class="key">Latest Sign-in:</td><td>$latest_sign_in_mins m. ago</td><td class="m_ago">$latest_sign_in</td></tr>
<!--            <tr><td class="key">Latest Activity:</td><td>$latest_activity_mins m. ago</td><td class="m_ago">$latest_activity</td></tr> -->
            <tr><td class="key" colspan="3"></td></tr>
            <tr><td class="key">Latest Activity:</td><td colspan="2" class="latest_action">$latest_activity_mins m. ago</td></tr>
            <tr><td class="latest_action" colspan="3"> $latest_action</td></tr>
            <tr><td class="key" colspan="3"></td></tr>
            <tr><td class="key">Session Length:</td><td colspan="2">$session_length minutes</td></tr>
            <tr><td class="key">User Agent:</td><td colspan="2">$ua</td></tr>
            <tr><td class="key" colspan="3"></td></tr>
            <tr><td class="key">Survivors:</td><td colspan="2">$survivor_count</td></tr>
            <tr><td class="key">Settlements:</td><td colspan="2">$settlements</td></tr>
            <tr>
             <td class="key" colspan="3">
                <form action="#">
                 <input type="hidden" value="pickle" name="export_user_data"/>
                 <input type="hidden" value="$u_id" name="asset_id"/>
                 <br/>
                &ensp; &ensp; &ensp; <button class="gradient_blue">Download User Data Pickle</button>
                 <br /><br/>
                </form>
             </td>
            </tr>
        </table>
    </div><br/>
    \n""")


class ui:
    game_asset_select_top = Template("""\n\
    <select
        class="$select_class"
        name="$operation$name"
        ng_model="$ng_model"
        ng_change="$ng_change"
        onchange="$on_change"
    >
      <option selected disabled hidden value="">$operation_pretty $name_pretty</option>
    """)
    game_asset_select_row = Template('\t  <option value="$asset">$asset</option>\n')
    game_asset_select_bot = '    </select>\n'
    text_input = Template('\t  <input onchange="this.form.submit()" type="text" class="full_width" name="$name" placeholder="$placeholder_text"/>')



class dashboard:
    # flash
    down_arrow_flash = '<img class="dashboard_down_arrow" src="%s/icons/down_arrow.png"/> ' % settings.get("application", "STATIC_URL")
    campaign_flash = '<img class="dashboard_icon" src="%s/icons/campaign.png"/> ' % settings.get("application", "STATIC_URL")
    settlement_flash = '<img class="dashboard_icon" src="%s/icons/settlement.png"/> ' % settings.get("application", "STATIC_URL")
    system_flash = '<img class="dashboard_icon" src="%s/icons/system.png"/> ' % settings.get("application", "STATIC_URL")
    refresh_flash = '<img class="dashboard_icon" src="%s/icons/refresh.png"/> ' % settings.get("application", "STATIC_URL")


    # AngularJS and V2 stuff

    # settlement administrivia; needs to be above the dashboard accordions
    panel_button = '<form action="#" method="POST"><input type="hidden" name="change_view" value="panel"/><button class="dashboard_admin_panel_launch_button kd_blue tablet_and_desktop">Admin Panel!</button></form>\n'
    new_settlement_button = '<form method="POST" action="#"><input type="hidden" name="change_view" value="new_settlement" /><button class="kd_blue">+ New Settlement</button></form>\n'

    # dashboard accordions

    preference_header = Template("""\n
    <div class="dashboard_preference_block_group">
        <h2>$title</h2>
    \n""")
    preference_footer = "</div> <!-- dashboard_preference_block_group $title--> "
    preference_block = Template("""\n
    <p class="preference_description">$desc</p>

    <div class="dashboard_preference_elections_container">
        <input
            id="pref_true_$pref_key"
            class="kd_css_checkbox kd_radio_option"
            name="$pref_key"
            style="display: none"
            type="radio"
            value="True"
            $pref_true_checked
            onchange="updateUserPreference(this);"
        />
        <label for="pref_true_$pref_key">
            $affirmative
        </label>

        <input
            id="pref_false_$pref_key"
            class="kd_css_checkbox kd_radio_option"
            name="$pref_key"
            style="display: none"
            type="radio"
            value="False"
            $pref_false_checked
            onchange="updateUserPreference(this);"
        />
        <label for="pref_false_$pref_key">
            $negative
        </label>
    </div> <!-- dashboar_preference_elections_container -->

    \n""")


    #
    #   ANGULARJS dashboard components!
    #

    initializer = Template("""\
    <script src="/media/dashboard.js?v=$application_version"></script>
    <div
        id="dashboardWelcomeModal"
        class="modal dashboard_welcome_modal"
        ng-class="{true: 'visible', false: 'hidden'}[user.dashboard.settlements.length == 0]"
        onclick="showHide('dashboardWelcomeModal')"
    >
    <p>Welcome to <b>http://kdm-manager.com</b>!</p>
    <p><b>The Manager</b> is an interactive webapp intended to make it
    easier to manage and share your Kingdom Death: <i>Monster</i> campaigns.</p>
    <p>&nbsp; </p>
    <p>This application is fan-maintained and <b>is not</b> supported by or
    affiliated with Kingdom Death.</p>
    <p>&nbsp; </p>
    <p>To get started, you will have to <b>create a new settlement</b>. Once your new
    settlement is created, you will be shown a <b>campaign summary</b>, which is
    is like a dashboard for your campaign.</p>
    <p>From the <b>campaign summary</b>, you can use the controls in the upper-left
    corner to add new survivors, view your settlement's "sheet" and add/remove
    expansion content.</p>
    <p>In order to add other players to your campaign, all you have to do is
    navigate to an individual survivor's "sheet" and change that survivor's email
    address to the email address of another registered user of this site.</p>
    <p>Changes to settlement and survivor sheets are always saved
    automatically.</p>
    <p>&nbsp; </p>
    <p>Finally, this application is <u>under active development</u> and problems <b>will</b>
    occur! Please use the controls within the app to report errors/issues.</p>
    <p>&nbsp; </p>
    <div class="kd_alert_no_exclaim">Click or tap anywhere to get started!</div>
    </div>
    <div
        id="dashboardControlElement"
        ng-controller="dashboardController"
        ng-init="initialize('dashboard', '$user_id', '$api_url'); showInitDash(); setLatestChangeLog();"
    >
    """)

    angular_app = """\

    <div
        id="dashboardTwitter"
        class="dashboard_twitter_container modal"
        ng-init="registerModalDiv('dashboardTwitterButton','dashboardTwitter');"
    >
        <h3>Updates!</h3>
        <div class="dashboard_updates_container">
            <div class="updates">
                <p><b>http://kdm-manager.com</b> release <b>{{user.meta.webapp.release}}</b> is currently running on version <b>{{user.meta.api.version}}</b> of <a href="http://api.thewatcher.io" target="top">the Kingdom Death API</a>, which was released on {{latest_blog_post.published}}.</p>
                <p>The KDM API currently supports version <b>1.5</b> of Kingdom Death: <i>Monster</i>.</p>
                <a target="top" href="{{latest_blog_post.url}}"><button class="kd_blue full_width_modal_button">View latest change log</button></a>
            </div>
            <div class="twitter_embed_container">
                <a
                    class="twitter-timeline"
                    href="https://twitter.com/kdmManager"
                    data-tweet-limit="3"
                > Retrieving tweets...
                </a>
                <script async src="//platform.twitter.com/widgets.js" charset="utf-8"></script>
            </div>
        </div> <!-- dashboard_updates_container -->
        <button class="kd_alert_no_exclaim" onclick="closeModal('dashboardTwitter')">Return to the Dashboard!</button>

    </div> <!-- dashboard_twitter -->

    <button
        id="dashboardTwitterButton"
        class="dashboard_twitter_button kd_promo"
    > !
    </button>

    <div class="dashboard_menu">
        <h2
            class="clickable campaign_summary_gradient dashboard_rollup"
            onclick="showHide('campaign_div')"
        >
            <img class="dashboard_icon" src="/media/icons/campaign.png"/>
            Campaigns <img class="dashboard_down_arrow" src="/media/icons/down_arrow.png"/>
        </h2>

        <div
            id="campaign_div"
            class="dashboard_accordion campaign_summary_gradient"
        >
            <p class="panel_top_tooltip">Games you are currently playing.</p>

            <div class="dashboard_button_list">

                <div
                    id="dashboardCampaignsLoader"
                    class="dashboard_settlement_loader"
                >
                    <img
                        src="/media/loading_lantern.gif"
                        alt="Retrieving settlements..."
                    /> Retrieving campaigns...
                </div>

                <form
                    ng-repeat="s in user.dashboard.settlements | orderBy: '-'"
                    ng-if="s.sheet.abandoned == undefined"
                    method="POST"
                >
                    <input type="hidden" name="view_campaign" value="{{s.sheet._id.$oid}}" />
                    <button
                        class="kd_dying_lantern dashboard_settlement_list_settlement_button"
                        onclick="showFullPageLoader(); this.form.submit()"
                    >
                        <b>{{s.sheet.name}}</b>
                        <br/><i>{{s.sheet.campaign_pretty}}</i>
                        <ul class="dashboard_settlement_list_settlement_attribs">
                            <li ng-if="s.meta.creator_email != user_login"><i>Created by:</i> {{s.meta.creator_email}}</li>
                            <li><i>Started:</i> {{s.meta.age}} ago</li>
                            <li><i>LY:</i> {{s.sheet.lantern_year}} &nbsp; <i>Survivors:</i> {{s.sheet.population}}</li>
                            <li ng-if="s.meta.player_email_list.length >= 2">
                                <i>Players:</i> {{s.meta.player_email_list.join(', ')}}
                            </li>
                        </ul>
                    </button>
                </form>

            </div>
        </div>
    </div>

    <div
        id="all_settlements_panel"
        class="dashboard_menu all_settlements_panel"
    >
        <h2
            class="clickable settlement_sheet_gradient dashboard_rollup"
            onclick="showHide('all_settlements_div')"
        >
            <img class="dashboard_icon" src="/media/icons/settlement.png"/>
            Settlements <img class="dashboard_down_arrow" src="/media/icons/down_arrow.png"/>
        </h2>

        <div
            id="all_settlements_div"
            class="dashboard_accordion settlement_sheet_gradient hidden"
        >
            <p class="panel_top_tooltip">Manage settlements you have created.</p>

            <div class="dashboard_button_list">

                <form method="POST" action="">
                    <input type="hidden" name="change_view" value="new_settlement" />
                    <button class="kd_blue centered" onclick="showFullPageLoader()">+ Create New Settlement</button>
                </form>

                <div
                    id="dashboardSettlementsLoader"
                    class="dashboard_settlement_loader"
                >
                    <img
                        src="/media/loading_lantern.gif"
                        alt="Retrieving settlements..."
                    /> Retrieving settlements...
                </div>

                <form
                    ng-repeat="s in user.dashboard.settlements"
                    ng-if="s.sheet.created_by.$oid == user_id"
                    method="POST"
                >
                    <input type="hidden" name="view_settlement" value="{{s.sheet._id.$oid}}" />
                    <button
                        class="kd_dying_lantern dashboard_settlement_list_settlement_button"
                        onclick="showFullPageLoader(); this.form.submit()"
                    >
                        <b>{{s.sheet.name}}</b>
                        <span class="maroon_text" ng-if="s.sheet.abandoned != undefined">[ABANDONED]</span>
                        <br/><i>{{s.campaign_pretty}}</i>
                        <ul class="dashboard_settlement_list_settlement_attribs">
                            <li><i>Created on:</i> {{s.meta.age}} ago</li>
                            <li>{{s.sheet.expansions.length}} expansions / {{s.meta.player_email_list.length}} player(s)</li>
                            <li><i>LY:</i> {{s.sheet.lantern_year}}</li>
                            <li><i>Population:</i> {{s.sheet.population}}</li>
                            <li><i>Deaths:</i> {{s.sheet.death_count}}</li>
                            <li ng-if="s.meta.player_email_list.length >= 2"><i>Admins:</i> {{s.sheet.admins.join(', ')}}</li>
                            <li ng-if="s.meta.player_email_list.length >= 2"><i>Players:</i> {{s.meta.player_email_list.join(', ')}}</li>
                        </ul>
                    </button>
                </form>

            </div> <!-- dashboard_button_list -->

        </div> <!-- all_settlements_div -->
    </div> <!-- all_settlements_panel -->

    <div
        id="world_container"
        class="dashboard_menu world_panel"
    >

        <h2
            class="clickable world_primary dashboard_rollup"
            onclick="showHide('world_detail_div')"
        >
            <font class="kdm_font_hit_locations dashboard_kdm_font white">g</font>
            <font class="white">World</font>
            <img class="dashboard_down_arrow" src="/media/icons/down_arrow_white.png"/>
        </h2>

        <div id="world_detail_div" class="dashboard_accordion world_secondary hidden world_container">

            <div class="world_panel_basic_box">
                <p>
                    <font class="green_text"> <b>{{world.active_settlements.value}} </b></font> Settlements are holding fast.
                    <font class="maroon_text"><b> {{world.abandoned_or_removed_settlements.value}} </b></font> have been abandoned.
                </p>
                <p>
                    <font class="green_text"> <b>{{world.live_survivors.value}}</b> </font> Survivors are alive and fighting.
                    <font class="maroon_text"><b>{{world.dead_survivors.value}}</b></font> have perished.</p>
            </div>

            <div class="world_panel_basic_box">
                <h3>Settlement Statistics</h3>

                <p>{{world.total_multiplayer_settlements.name}}: <b>{{world.total_multiplayer_settlements.value}}</b></p>
                <p>{{world.new_settlements_last_30.name}}: <b>{{world.new_settlements_last_30.value}}</b></p>

                <table>
                    <tr><th colspan="2">{{world.top_settlement_names.name}}</th></tr>
                    <tr ng-repeat="row in world.top_settlement_names.value" ng-class-even="'zebra'">
                        <td>{{row.name}}</td><td class="int_value">{{row.count}}</td>
                    </tr>
                </table>

                <table>
                    <tr><th colspan="2">Active Campaigns</th></tr>
                    <tr ng-repeat="(name,count) in world.settlement_popularity_contest_campaigns.value" ng-class-even="'zebra'">
                        <td>{{name}}</td> <td class="int_value">{{count}}</td>
                    </tr>
                </table>

                <table>
                    <tr><th colspan="2">Campaigns w/ Expansion Content</th></tr>
                    <tr ng-repeat="e in world.settlement_popularity_contest_expansions.value" ng-class-even="'zebra'">
                        <td>{{e.name}}</td> <td class="int_value">{{e.count}}</td>
                    </tr>
                </table>

                <table>
                    <tr><th colspan="2">Settlement Averages</th></tr>
                    <tr><td>Lantern Year </td><td class="int_value">{{world.avg_ly.value}}</td></tr>
                    <tr class="zebra"><td>Innovation Count </td><td>{{world.avg_innovations.value}}</td></tr>
                    <tr><td>Expansions</td><td> {{world.avg_expansions.value}}</td></tr>
                    <tr class="zebra"><td>Defeated Monsters</td><td> {{world.avg_defeated_monsters.value}}</td></tr>
                    <tr><td>Items in Storage</td> <td>{{world.avg_storage.value}}</td></tr>
                    <tr class="zebra"><td>Milestone Story Events</td><td> {{world.avg_milestones.value}}</td></tr>
                    <tr><td>Lost Settlements </td><td>{{world.avg_lost_settlements.value}}</td></tr>
                </table>

                <table><tr><th>Principle selection rates</th></tr></table>
                <div ng-repeat="(principle, selections) in world.principle_selection_rates.value">
                    <table>
                        <tr><th colspan="2" class="principle">{{principle}}</th></tr>
                        <tr ng-repeat="option in selections.options" ng-class-even="'zebra'">
                            <td>{{option}}</td>
                            <td class="int_value">{{selections[option].percentage}}%</td>
                        </tr>
                    </table>
                </div>

                <table>
                    <tr><th colspan="2">Top Innovations</th></tr>
                    <tr ng-repeat="row in world.top_innovations.value" ng-class-even="'zebra'">
                        <td>{{row.name}}</td><td class="int_value">{{row.count}}</td>
                    </tr>
                </table>

                <table>
                    <tr><th>Survival Limit stats</th></tr>
                    <tr><td>Average Survival Limit:</td><td class="int_value">{{world.avg_survival_limit.value}}</td></tr>
                    <tr class="zebra"><td>Max Survival Limit:</td><td>{{world.max_survival_limit.value}}</td></tr>
                </table>


            </div>

            <div class="world_panel_basic_box">
                <h3>Latest Settlement</h3>
                <table>
                    <tr><td colspan="2"><b>{{world.latest_settlement.value.name}}</b></td></tr>
                    <tr><td colspan="2"><i>{{world.latest_settlement.value.campaign}}</i></td></tr>
                    <tr ng-if="world.latest_settlement.value.expansions != null">
                        <td colspan="2">{{world.latest_settlement.value.expansions}}</td>
                    </tr>
                    <tr><td>Created</td><td>{{world.latest_settlement.value.age}} ago</td></tr>
                    <tr class="zebra"><td>Players</td><td>{{world.latest_settlement.value.player_count}}</td></tr>
                    <tr><td>Population</td><td>{{world.latest_settlement.value.population}}</td></tr>
                    <tr class="zebra"><td>Death count</td><td>{{world.latest_settlement.value.death_count}}</td></tr>
                </table>

            </div>

            <div class="world_panel_basic_box">
                <h3>Survivor Statistics</h3>

                <table>
                    <tr><th>Population and death stats</th></tr>
                    <tr><td>Average Population</td><td class="int_value">{{world.avg_pop.value}}</td></tr>
                    <tr class="zebra"><td>Max Population</td><td>{{world.max_pop.value}}</td></tr>
                    <tr><td>Average Death count</td><td> {{world.avg_death_count.value}}</td></tr>
                    <tr class="zebra"><td>Max Death Count</td> <td>{{world.max_death_count.value}}</td></tr>
                </table>

                <table>
                    <tr><th colspan="2">Top Survivor names</th></tr>
                    <tr ng-repeat="row in world.top_survivor_names.value" ng-class-even="'zebra'">
                        <td>{{row.name}}</td> <td class="int_value">{{row.count}}</td>
                    </tr>
                </table>

                <table>
                    <tr><th colspan="2">Top Causes of Death</th></tr>
                    <tr ng-repeat="row in world.top_causes_of_death.value" ng-class-even="'zebra'">
                        <td>{{row.cause_of_death}}</td> <td class="int_value">{{row.count}}</td>
                    </tr>
                </table>

                <table>
                    <tr><th colspan="2">Living survivor averages</th></tr>
                    <tr><td>Hunt XP:</td><td>{{world.avg_hunt_xp.value}}</td></tr>
                    <tr class="zebra"><td>Insanity:</td><td class="int_value">{{world.avg_insanity.value}}</td></tr>
                    <tr><td>Courage:</td><td>{{world.avg_courage.value}}</td></tr>
                    <tr class="zebra"><td>Fighting Arts:</td><td>{{world.avg_fighting_arts.value}}</td></tr>
                    <tr><td>Understanding:</td><td>{{world.avg_understanding.value}}</td></tr>
                    <tr class="zebra"><td>Disorders:</td><td>{{world.avg_disorders.value}}</td></tr>
                    <tr><td>Abilities/Impairments:</td><td>{{world.avg_abilities.value}}</td></tr>
                </table>

            </div>

            <div class="world_panel_basic_box">
                <h3>Latest Survivor</h3>
                <table>
                    <tr ng-if="world.latest_survivor.value.avatar != undefined">
                        <td colspan="2" class="world_panel_avatar_cell">
                            <img
                                class="world_panel_avatar"
                                ng-src="/get_image?id={{world.latest_survivor.value.avatar.$oid}}"
                                title="{{world.latest_survivor.value.name}}"
                            />
                    </tr>
                    <tr><td colspan="2"><b>{{world.latest_survivor.value.name}}</b> [{{world.latest_survivor.value.sex}}] of </td></tr>
                    <tr><td colspan="2"><i>{{world.latest_survivor.value.settlement_name}}</i></td></tr>
                    <tr ng-if="world.latest_settlement.value.epithets != null">
                        <td colspan="2">{{world.latest_survivor.value.epithets}}</td>
                    </tr>
                    <tr><td>Created</td><td>{{world.latest_survivor.value.age}} ago</td></tr>
                    <tr class="zebra"><td>Joined in LY</td><td>{{world.latest_survivor.value.born_in_ly}}</td></tr>
                    <tr><td>Hunt XP</td><td>{{world.latest_survivor.value.hunt_xp}}</td></tr>
                    <tr class="zebra"><td>Insanity</td><td>{{world.latest_survivor.value.Insanity}}</td></tr>
                    <tr><td>Courage</td><td>{{world.latest_survivor.value.Understanding}}</td></tr>
                    <tr class="zebra"><td>Understanding</td><td>{{world.latest_survivor.value.Insanity}}</td></tr>
                </table>

            </div>

            <div class="world_panel_basic_box">
                <h3>Latest Fatality</h3>
                <table>
                    <tr ng-if="world.latest_fatality.value.avatar != undefined">
                        <td colspan="2" class="world_panel_avatar_cell">
                            <img
                                class="world_panel_avatar"
                                ng-src="/get_image?id={{world.latest_fatality.value.avatar.$oid}}"
                                title="{{world.latest_fatality.value.name}}"
                            />
                    </tr>
                    <tr><td colspan="2"><b>{{world.latest_fatality.value.name}}</b> [{{world.latest_fatality.value.sex}}] of </td></tr>
                    <tr><td colspan="2"><i>{{world.latest_fatality.value.settlement_name}}</i></td></tr>
                    <tr><td colspan="2">Cause of Death:</i></td></tr>
                    <tr><td colspan="2">&ensp; <font class="maroon_text"><b>{{world.latest_fatality.value.cause_of_death}}</b></td></tr>
                    <tr ng-if="world.latest_settlement.value.epithets != null">
                        <td colspan="2">{{world.latest_fatality.value.epithets}}</td>
                    </tr>
                    <tr><td>Created</td><td>{{world.latest_fatality.value.age}} ago</td></tr>
                    <tr class="zebra"><td>Died in LY</td><td>{{world.latest_fatality.value.died_in}}</td></tr>
                    <tr><td>Hunt XP</td><td>{{world.latest_fatality.value.hunt_xp}}</td></tr>
                    <tr class="zebra"><td>Insanity</td><td>{{world.latest_fatality.value.Insanity}}</td></tr>
                    <tr><td>Courage</td><td>{{world.latest_fatality.value.Understanding}}</td></tr>
                    <tr class="zebra"><td>Understanding</td><td>{{world.latest_fatality.value.Insanity}}</td></tr>
                </table>

            </div> <!-- latest fatality -->

            <div class="world_panel_basic_box">
                <h3>Latest Kill</h3>
                <p><b>{{world.latest_kill.value.raw_name}}</b></p>
                <p>Defeated by the survivors of <b>{{world.latest_kill.value.settlement_name}}</b> on {{world.latest_kill.value.killed_date}} at {{world.latest_kill.value.killed_time}}.</p>
            </div>

            <div class="world_panel_basic_box">
                <h3>{{world.killboard.name}}</h3>
                <table ng-repeat="(type,board) in world.killboard.value">
                    <tr><th class="principle capitalize" colspan="2">{{type}}</th></tr>
                    <tr ng-repeat="row in board" ng-class-even="'zebra'">
                        <td>{{row.name}}</td> <td class="int_value">{{row.count}}</td>
                    </tr>
                </table>
            </div>

            <div class="world_panel_basic_box">
                <h3>User Statistics</h3>
                <p> <b>{{world.total_users.value}}</b> users are registered.</p>
                <p> <b>{{world.recent_sessions.value}}</b> users have managed campaigns in the last 12 hours.</p>
                <p> <b>{{world.total_users_last_30.value}}</b> users have managed campaigns in the last 30 days.</p>

                <table>
                    <tr><th colspan="2">Per user averages</th></tr>
                    <tr><td>Survivors</td><td class="int_value">{{world.avg_user_survivors.value}}</td></tr>
                    <tr class="zebra"><td>Settlements</td><td>{{world.avg_user_settlements.value}}</td></tr>
                    <tr><td>Avatars</td><td>{{world.avg_user_avatars.value}}</tr></tr>
                </table>
            </div> <!-- user stats -->

        </div> <!-- world_detail_div -->

    </div> <!-- dashboard_menu 'World'-->

        <div
            class="dashboard_menu"
        >
            <h2
                class="clickable about_primary dashboard_rollup"
                onclick="showHide('about_div')"
            >
                <font class="kdm_font dashboard_kdm_font">g</font> About <img class="dashboard_down_arrow" src="/media/icons/down_arrow.png">
            </h2>

            <div
                id="about_div"
                style="display: none;"
                class="dashboard_accordion about_secondary"
            >

                <p class="title">
                    <b>KD:M Manager! Production release {{user.meta.webapp.release}} (<a href="http://api.thewatcher.io">KDM API</a> release version {{user.meta.api.version}}).
                    </b>
                </p>

		<hr/>

		<p>About:</p>
		<ul>
                    <li>This application, which is called <i>kdm-manager.com</i>, or simply, <i>the Manager</i>, is an interactive campaign management tool for use with <i><a href="https://shop.kingdomdeath.com/collections/sold-out/products/kingdom-death-monster" target="top">Monster</a></i>, by <a href="http://kingdomdeath.com" target="top">Kingdom Death</a>.
                    </li>
                </ul>

                <p>Important Information:</p>
                <ul>
                    <li><b>This application is not developed, maintained, authorized or in any other way supported by or affiliated with <a href="http://kingdomdeath.com" target="top">Kingdom Death</a>.</b></li>
                    <li>This application is currently under active development and is running in debug mode!<li>
                    <li>Among other things, this means not only that <i>errors can and will occur</i>, but also that <i>features may be added or removed without notice</i> and <i>presentation elements are subject to change</i>.</li>
                    <li>Users' email addresses and other information are used only for the purposes of developing and maintaining this application and are never shared, published or distributed.</li>
                </ul>

                <hr/>

                <p>Release Information:</p>
                <ul>
                    <li>Release {{user.meta.webapp_release}} of the Manager went into production on {{latest_blog_post.published}}. <a target="top" href="{{latest_blog_post.url}}">View change log</a>.</li>
                    <li>v1.7.0, the first production release of the Manager, went live {{user.meta.webapp.age}} ago on 2015-11-29.</li>
                    <li>For detailed release information, including complete notes and updates for each production release, please check the development blog at <a href="http://blog.kdm-manager.com" target="top"/>blog.kdm-manager.com</a>.</li>
                </ul>

                 <hr/>

                 <p>Development and Support:</p>
                 <ul>
                      <li>Please report issues and errors using the side navigation panel within the application: this feature sends an email containing pertinent data directly to the application maintainers.</li>
                      <li>Follow the project <a href="https://twitter.com/kdmmanager" target="top">on Twitter</a> for updates/announcements.</li>
                      <li>Application source code is <a href="https://github.com/toconnell/kdm-manager" target="top">availableon GitHub</a>.</li>
                      <li>Github users may prefer to <a href="https://github.com/toconnell/kdm-manager/issues" target="top">report issues there</a>.</li>
                      <li>Check <a href="https://github.com/toconnell/kdm-manager/wiki" target="top">the development wiki</a> for complete information about the project.</li>
                 </ul>

                 <hr/>

                 <p>Privacy and Data Usage:</p>
                 <ul>
                      <li>Individually identifiable user data, e.g. email addresses and application data, are not shared or sold.</li>
                      <li>Individually identifiable user data are used for development purposes, including testing and QA.</li>
                      <li>Aggregate, deidentified user data are aggregated and displayed within the application and are available for general review via the KDM API.</li>
                 </ul>

                 <hr/>

                 <p>Credits:</p>
                 <ul>
                     <li> Produced, provisioned and supported by <a href="http://thelaborinvain.com">The Labor in Vain</a>.<li>
                     <li> Developed, maintained and edited by <a href="http://toconnell.info">Timothy O'Connell</a>.</li>
                     <li>Icon font ('kdm-font-10') by <a href="http://steamcommunity.com/id/GeorgianBalloon" target="top"> Miracle Worker</a>.</li>
                     <li>The <font style="font-family: Silverado; font-size: 1.3em;">Silverado Medium Condensed</font> font is licensed through <a href="https://www.myfonts.com/" target="top">MyFonts.com</a>.</li>
                     <li>Loading spinner GIF by <a href="http://loading.io" target="top">loading.io</a></li>
                </ul>

            </div> <!-- about_div -->

        </div> <!-- dashboard_menu 'About' -->

    </div> <!-- dashboardControlElement -->

    <script type="text/javascript">
        // kill the spinner, since we're done loading the page now.
        hideFullPageLoader();
    </script>


    """






    #
    #   DASHBOARD MOTD follows. this is the whole dashboard, basically.
    #

    motd = Template("""\n

    <img class="dashboard_bg" src="%s/tree_logo_shadow.png">

    <div id="preferencesContainerElement" class="dashboard_menu">

        <h2
            class="clickable system_primary dashboard_rollup"
            onclick="showHide('system_div')"
        >
            <img class="dashboard_icon" src="%s/icons/system.png"/> System %s
        </h2>

        <div id="system_div" class="dashboard_accordion system_secondary hidden">

            <div class="dashboard_preferences">
                <p>Use the controls below to update application-wide preferences.
                These settings will affect all of your settlements and survivors!</p>

                $user_preferences

            </div>

            <hr/>

            <div class="dashboard_preferences">
                <h3>Export User Data</h3>
<!--                <form method="POST" action="#">
                    <input type="hidden" name="export_user_data" value="json">
                    <button class="silver">JSON</button>
                </form> -->
                <form method="POST" action="#">
                    <input type="hidden" name="export_user_data" value="dict">
                    <button class="silver">Python Dictionary</button>
                </form>
                <form method="POST" action="#">
                    <input type="hidden" name="export_user_data" value="pickle">
                    <button class="silver">Python Pickle</button>
                </form>
            </div>

            <hr>

            <h3>User Management</h3>
            <div style="font-family: Metrophobic">
                <p class="currently_signed_in_as">Currently signed in as: <i>$login</i> (last sign in: $last_sign_in)</p>
                $last_log_msg

                <div class="dashboard_preferences">
                    <form action="#" method="POST">
                        <input type="hidden" name="change_password" value="True"/>
                        <input type="password" name="password" class="full_width" placeholder="password">
                        <input type="password" name="password_again" class="full_width" placeholder="password (again)"/>
                        <button class="kd_alert_no_exclaim red_glow"> Change Password</button>
                    </form>
                </div>
            </div>
        </div> <!-- system_div -->
    </div> <!-- preferencesContainerElement -->
    """ % (settings.get("application","STATIC_URL"), settings.get("application", "STATIC_URL"), down_arrow_flash))

    avatar_image = Template("""\n
    <img class="latest_fatality" src="/get_image?id=$avatar_id" alt="$name"/>
    \n""")

    # misc html assets

    refresh_button = """\n
    <form method="POST" action="/">
        <button
            id="floating_refresh_button"
            class="touch_me"
            onclick="showFullPageLoader()"
        >
            %s
        </button>
    </form>
    """ % refresh_flash

    view_asset_button = Template("""\n\
    <form method="POST" action="#">
    <input type="hidden" name="view_$asset_type" value="$asset_id" />
    <button id="$button_id" class="$button_class $disabled" $disabled>$asset_name <span class="tablet_and_desktop">$desktop_text</span></button>
    </form>
    \n""")



class angularJS:
    """ HTML here should only be angularJS applications. They need to be strings
    and they may not be python templates or do any other kind of variable
    expansion or anything like that. """


    expansions_manager = """\n
    <div
        id="modalExpansionsManager" class="modal"
        ng-init="registerModalDiv('bulkExpansionsManagerButton','modalExpansionsManager');"
        ng-controller="updateExpansionsController"
    >

      <!-- Modal content -->
        <div class="full_size_modal_panel timeline_gradient">
            <span class="closeModal" onclick="closeModal('modalExpansionsManager')">×</span>

            <h3>Expansions!</h3>

            <div class="expansions_controls_container" >
                <p>Use the controls below to determine which expansion content is
                enabled for this campaign. Remember to save and reload when finished!</p>

                <form method="POST" action="#">
                    <div class="expansion_content_line_item" ng-repeat="x in new_settlement_assets.expansions">
                        <input
                            id="{{x.handle}}_modal_toggle"
                            name="{{x.handle}}"
                            type="checkbox"
                            class="kd_css_checkbox kd_radio_option"
                            ng-model=incomingExpansion
                            ng-checked="settlement.sheet.expansions.indexOf(x.handle) != -1"
                            ng-click="toggleExpansion(x.handle)"
                            ng-disabled="settlement.game_assets.campaign.settlement_sheet_init.expansions.includes(x.handle)"
                        >
                        <label for="{{x.handle}}_modal_toggle">{{x.name}}</label>
                    </div> <!-- line_item -->

                    <div class="expansion_content_remove_warning">
                    <b>Warning!</b>
                    Disabling expansion content when it is required by the
                    campaign or the items on the campaign's Settlement and Survivor
                    Sheets (innovations, locations, fighting arts, etc.)
                    can cause errors and other unexpected behavior!
                    </div>

                    <button
                        type="submit"
                        class="kd_blue save_expansions"
                        onclick="closeModal('modalExpansionsManager'); showFullPageLoader()"
                    >
                        Save Changes and Reload
                    </button>

                </form>
            </div> <!-- container -->
        </div> <!-- modal content -->
    </div> <!-- parent modal -->
    """

    bulk_add_survivors = """\n
    <div
        id="modalBulkAdd" class="modal"
        ng-init="registerModalDiv('bulkAddOpenerButton','modalBulkAdd');"
    >

      <!-- Modal content -->
        <div class="full_size_modal_panel survivor_sheet_gradient">
            <span class="closeModal" onclick="closeModal('modalBulkAdd')">×</span>

            <h3>Add Multiple New Survivors</h3>
            <p>Use these controls to add multiple new survivors to {{settlement_sheet.name}}.
            New survivors will be manageable by all players in the campaign and
            named randomly or 'Anonymous' according to user preference.</p>

            <div
                class="create_user_asset_block_group bulk_add_block_group"
            >
                <div class="bulk_add_control">
                    <form method="POST" action="#">
                        <input type="hidden" name="modify" value="settlement" />
                        <input type="hidden" name="asset_id" value="{{settlement_sheet._id.$oid}}" />
                        <input type="hidden" name="bulk_add_survivors" value="True" />

                        Male

                        <button
                            type="button"
                            class="incrementer"
                            onclick="increment('maleCountBox');"
                        >
                            &#9652;
                        </button>
                        <input
                            id="maleCountBox"
                            class="big_number_square"
                            type="number"
                            name="male_survivors"
                            value="0"
                            min="0"
                        />
                        <button
                            type="button"
                            class="decrementer"
                            onclick="decrement('maleCountBox');"
                        >
                        &#9662;
                        </button>
                </div>  <!-- bulk_add_control maleCountBox" -->
                <div class="bulk_add_control">

                    Female

                    <button
                        type="button"
                        class="incrementer"
                        onclick="increment('femaleCountBox');"
                    >
                        &#9652;
                    </button>
                    <input
                        id="femaleCountBox"
                        class="big_number_square"
                        type="number"
                        name="female_survivors"
                        value="0"
                        min="0"
                    />
                    <button
                        type="button"
                        class="decrementer"
                        onclick="decrement('femaleCountBox');"
                    >
                        &#9662;
                    </button>
                </div>

                <hr class="invisible"/>

                <input
                    type="submit"
                    id="bulkAddSurvivors"
                    onclick="closeModal('modalBulkAdd'); showFullPageLoader()"
                    class="kd_blue settlement_sheet_bulk_add" value="Create New Survivors"
                />

                </form>


            </div> <!-- bulk_add_survivors -->

        </div> <!-- mondal content -->
    </div> <!-- modal parent -->

    \n"""

    settlement_notes = """\n\
    <div
        class="modal"
        id="settlementNotesContainer"
        ng-controller="settlementNotesController"
        ng-init="registerModalDiv('settlementNotesOpenerButton','settlementNotesContainer');"
    >

        <div class="full_size_modal_panel campaign_summary_gradient">

            <span class="closeModal" onclick="closeModal('settlementNotesContainer')">×</span>

            <h3>Campaign Notes</h3>
            <p>All players in the {{settlement_sheet.name}} campaign may make
            notes and comments here. Tap or click notes to remove them.</p>

            <div class="settlement_notes_application_container">

                <div class="settlement_notes_note_container">

                    <div class="settlement_notes_controls">
                        <input ng-model="newNote" onclick="this.select()" class="add_settlement_note">
                        <button ng-click="addNote()" class="kd_blue add_settlement_note">+</button>
                    </div> <!-- settlement_notes_controls -->

                    <div
                        class="settlement_note"
                        ng-repeat="n in settlement_notes"
                    >
                        <div class="note_flair">
                            <font
                                ng-if="userRole(n.author) == 'settlement_admin'"
                                class="kdm_font_hit_locations"
                            > <span class="flair_text">a</span> </font>
                            <font
                                ng-if="userRole(n.author) == 'player'"
                                class="kdm_font_hit_locations"
                            > <span class="flair_text">b</span> </font>
                        </div>

                        <div class="note_content" onclick="showHide(n.js_id);window.alert(n.js_id)">
                            {{n.note}} <span class="author" ng-if="n.author != user_login"> {{n.author}}</span>
                        </div>
                        <span
                            id="{{n.js_id}}"
                            class="kd_alert_no_exclaim note_remove hidden"
                            ng-if="n.author == user_login || user_is_settlement_admin"
                            ng-click="removeNote($index, n.js_id)
                        ">
                            &times;
                        </span>

                    </div><!-- settlement_note -->

                </div> <!-- settlement_notes_note_container -->


            </div> <!-- settlement_notes_application_container -->

            <div
                ng-if="user_is_settlement_admin"
                ng-controller="playerManagementController"
            >
                <hr/>
                <h3>Manage Players</h3>
                    <p>Add other registered users to the {{settlement_sheet.name}}
                    campaign by adding their email addresses to the Survivor Sheets
                    of survivors in this campaign. </p>

                    <table class="player_management">
                        <tr>
                            <th colspan="2">Login</th>
                            <th>Admin</th>
                        </tr>
                        <tr
                            class="player_management_row"
                            ng-repeat="p in settlement.user_assets.players"
                        >
                            <td class="flair" ng-if="arrayContains(p.login, settlement_sheet.admins) == true">
                                <span class="player_management_flair kdm_font_hit_locations">a</span>
                            </td>
                            <td class="flair" ng-if="arrayContains(p.login, settlement_sheet.admins) == false">
                                <span class="player_management_flair kdm_font_hit_locations">b</span>
                            </td>

                            <td class="login">
                                {{p.login}}
                                <span ng-if="p._id.$oid == settlement_sheet.created_by.$oid">
                                    (Founder)
                                </span>
                            </td>

                            <td class="admin">
                                <input
                                    type="checkbox"
                                    class="player_management_admin"
                                    ng-if="p._id.$oid != settlement_sheet.created_by.$oid"
                                    ng-model="playerIsAdmin"
                                    ng-checked="arrayContains(p.login, settlement_sheet.admins) == true"
                                    ng-click="toggleAdmin(p.login)"
                                />
                            </td>
                        </tr>
                    </table>

                <hr/>
                <form action="/">
                    <center>
                        <button class="kd_blue" type="submit">Save Changes and Reload!</button>
                    </center>
                </form>
            </div> <!-- ng-if div -->
        </div><!-- full size modal panel -->

    </div> <!-- modal (parent) -->
    \n"""

    new_survivor = """\n\
    <div
        class="modal"
        id="modalNewSurvivorContainer"
        ng-controller="newSurvivorController"
        ng-init="registerModalDiv('newSurvivorButton','modalNewSurvivorContainer');"
    >

        <div class="full_size_modal_panel survivor_sheet_gradient">

            <h3>Create New Survivor</h3>

            <span class="closeModal" onclick="closeModal('modalNewSurvivorContainer')">×</span>

            <form method="POST" action="#" enctype="multipart/form-data">
            <input type="hidden" name="new" value="survivor" />

            <div class="create_user_asset_block_group">

            <input
                ng-model="new_survivor_name"
                class="new_asset_name"
                type="text"
                name="name"
                placeholder="New Survivor Name"
                autofocus
                >
            </div>


            <div
                class="create_user_asset_block_group"
            >

                <h2 class="new_asset">Survivor Sex</h2>

                <input
                    id="maleInput"
                    class="kd_css_checkbox kd_radio_option"
                    type="radio"
                    name="sex"
                    value="M"
                    checked
                >
                <label
                    id="survivorSexMaleElection"
                    for="maleInput"
                >
                    Male
                </label>

                <input
                    id="femaleInput"
                    class="kd_css_checkbox kd_radio_option"
                    type="radio"
                    name="sex"
                    value="F"
                >
                <label
                    id="survivorSexFemaleElection"
                    for="femaleInput"
                >
                    Female
                </label>

            </div>

            <div class="create_user_asset_block_group">
                <h2 class="no_ul">Survivor Avatar Image</h2>
                <p>Upload an image to represent this survivor (optional).</p>
                <br/>
                <input type="file" class="new_survivor_avatar" name="survivor_avatar" accept="image/*">
            </div>


            <div
                class="create_user_asset_block_group"
                ng-if="
                    settlement_sheet.lantern_year >= 1 &&
                    settlement.eligible_parents.male.length >= 1 &&
                    settlement.eligible_parents.female.length >= 1
                "
            >
                <h2 class="no_ul">Survivor Parents</h2>
                <p class="new_asset">Survivors without parents are not eligible
                for the automatic application of Innovation bonuses granted only
                to newborn survivors!</p>

                <div class="parent_selectors">
                    <select
                        name="father"
                        ng-model="newSurvivorFather"
                        ng-options="survivor._id.$oid as survivor.name for survivor in settlement.eligible_parents.male"
                    /><option selected disabled value="" name="father">Father</option></select>

                    <select
                        name="mother"
                        ng-model="newSurvivorMother"
                        ng-options="survivor._id.$oid as survivor.name for survivor in settlement.eligible_parents.female"
                    /><option selected disabled value="" name="mother">Mother</option></select>
                </div>


            </div> <!-- ancestors -->


            <div class="create_user_asset_block_group">

                <h2 class="no_ul">Access Permissions</h2>

                <p>Use the controls below to determine who is the owner of the
                survivor and whether other players may edit the survivor.</p>

                <input
                    type="email"
                    name="email"
                    ng-placeholder="Survivor Email"
                    ng-value="user_login"
                    onclick="this.select()"
                >

                <input
                    id="publicInput"
                    type="checkbox"
                    class="kd_css_checkbox kd_radio_option"
                    name="public"
                >
                 <label
                     id="survivorPublic"
                     for="publicInput"
                 >
                     Public - anyone may manage this survivor
                </label>

            </div> <!-- survivor perms -->

            <br />
    
            <button
                onclick="closeModal('modalNewSurvivorContainer'); showFullPageLoader()"
                class="kd_blue add_new_survivor"
            >
                Add {{new_survivor_name}}
            </button>

            <br/><br/>

            </form>

        </div><!-- full size modal panel -->

    </div> <!-- modal (parent) -->
    \n"""

    timeline = """\n

    <div
        class="modal"
        id="modalTimelineContainer"
        ng-controller="timelineController"
        ng_init="registerModalDiv('timelineOpenerButton','modalTimelineContainer');"
    >

        <span class="touch_me timeline_overlay_current_ly">LY: <b>{{settlement.sheet.lantern_year}}</b></span>

        <div class="full_size_modal_panel timeline_gradient">

            <span class="closeModal" onclick="closeModal('modalTimelineContainer')">×</span>

            <h3>{{ settlement_sheet.name}} Timeline</h3>

            <p ng-if="user_is_settlement_admin">
                Click or tap on any Lantern Year below to update events occuring during that year.
            </p>
            <p ng-if="user_is_settlement_admin == false">
                The Timeline of story, settlement and showdown events for {{settlement_sheet.name}}. Only settlement admins may modify the timeline.
            </p>

            <div class="timeline_ly_headline">
                <span>Year</span><span>Story & Special Events</span>
            </div>

            <div
                ng-repeat="t in timeline"
                ng-init="t.log_div_id = 'ly' + t.year + 'LogDivIDHandle'"
                class="timeline_whole_entry_container"
            >
                <div class="timeline_ly_container" ng-click="showHideControls(t.year)">
                    <div class="timeline_bullet_and_year_container">
                        <span ng-if="t.year >= settlement.sheet.lantern_year" class="kd_toggle_bullet"></span>
                        <span ng-if="t.year < settlement.sheet.lantern_year" class="kd_toggle_bullet checked_kd_toggle_bullet"></span>
                        <span class="timeline_ly_number">{{t.year}}</span>
                    </div>

                    <div class="timeline_events_container">
                        <span class="timeline_event" ng-repeat="e in t.story_event" ng-model="story_events">
                            <font class="kdm_font">g &nbsp;</font>
                            <b>{{e.name}}</b>
                            <span class="timeline_event_page" ng-if="e.page">
                                &nbsp;(p.{{e.page}})
                            </span>
                        </span>
                        <span class="timeline_event" ng-repeat="q in t.special_showdown">
                        <span><img class="icon special_showdown" src="/media/icons/special_showdown_event.png"/></span>
                            <font class="special_showdown_text"><b>{{q.name}}</b></font>
                        </span>
                        <span class="timeline_event" ng-repeat="q in t.showdown_event">
                            <font class="kdm_font">f &nbsp;</font>
                            {{q.name}}
                        </span>
                        <span class="timeline_event" ng-repeat="n in t.nemesis_encounter">
                        <span><img class="icon" src="/media/icons/nemesis_encounter_event.jpg"/></span>
                            &nbsp; <b> {{n.name}}</b>
                        </span>
                        <span class="timeline_event" ng-repeat="e in t.settlement_event">
                            <font class="kdm_font_hit_locations">a &nbsp;</font>
                            {{e.name}}
                        </span>
                    </div>
                </div>


                <div
                    id="timelineControlsLY{{t.year}}"
                    style="display: none; height: 0;"
                    class="timeline_hidden_controls_container"
                    ng-if="user_is_settlement_admin == true;"
                >

                    <select
                        name="add_timeline_event"
                        class="add_timeline_event"
                        ng-model="newEvent"
                        ng-options="se.handle as se.name for se in story_events"
                        ng-change="addEvent(t.year,'story_event',newEvent)"
                    >
                        <option selected disabled value="">
                            Add Story Event
                        </option>
                    </select>

                    <br/>

                    <select
                        name="add_timeline_event"
                        class="add_timeline_event"
                        ng-model="newEvent"
                        ng-options="s for s in settlement.game_assets.special_showdown_options"
                        ng-change="addEvent(t.year,'special_showdown',newEvent)"
                    >
                        <option selected disabled value="">
                            Add Special Showdown
                        </option>
                    </select>

                    <br/>

                    <select
                        name="add_timeline_event"
                        class="add_timeline_event"
                        ng-model="newEvent"
                        ng-options="s for s in settlement.game_assets.showdown_options"
                        ng-change="addEvent(t.year,'showdown_event',newEvent)"
                    >
                        <option selected disabled value="">
                            Add Showdown
                        </option>
                    </select>

                    <br/>

                    <select
                        name="add_timeline_event"
                        class="add_timeline_event"
                        ng-model="newEvent"
                        ng-options="n for n in settlement.game_assets.nemesis_encounters"
                        ng-change="addEvent(t.year,'nemesis_encounter',newEvent)"
                    >
                        <option selected disabled value="">
                            Add Nemesis Encounter
                        </option>
                    </select>

                    <br/>

                    <select
                        name="add_settlement_event"
                        class="add_timeline_event"
                        ng-model="newEvent"
                        ng-options="se.handle as se.name for se in settlement_events"
                        ng-change="addEvent(t.year,'settlement_event',newEvent)"
                    >
                        <option selected disabled value="">
                            Add Settlement Event
                        </option>
                   </select>

                    <hr class="invisible"/>

                    <div ng-repeat="event_group in t" class="timeline_rm_controls">
                        <span ng-if="isObject(event_group)" class="timeline_rm_event_group">
                            <div
                                ng-click="rmEvent(t.year, e)"
                                ng-repeat="e in event_group"
                                class="kd_alert_no_exclaim rm_timeline_event"
                            > <b>x</b> {{e.name}}
                            </div>
                        </span>
                    </div>

                    <hr class="invisible"/>

                    <div class="end_current_ly" ng-if="t.year==settlement.sheet.lantern_year">
                        <input
                            type="checkbox"
                            id="endLanternYear{{t.year}}"
                            ng-model="lantern_year"
                            ng-click="setLY(t.year + 1); showHideControls(t.year); showControls(t.year+1)"
                        />
                        <label
                            class="kd_blue timeline_change_ly_button"
                            for="endLanternYear{{t.year}}"
                        >
                            End Lantern Year {{t.year}}
                        </label>
                        <input
                            type="checkbox"
                            id="returnToLanternYear{{t.year - 1}}"
                            ng-model="lantern_year"
                            ng-change="setLY(t.year - 1); showHideControls(t.year); showControls(t.year-1)"
                        />
                        <label
                            class="kd_blue timeline_change_ly_button"
                            for="returnToLanternYear{{t.year - 1}}"
                            ng-if="t.year >= 1"
                        >
                            Return to Lantern Year {{t.year - 1}}
                        </label>
                    </div> <!-- end_current_ly -->

                </div> <!-- timelineControlsLy{{t.year}}-->

                <div
                    ng-if="t.year <= settlement.sheet.lantern_year && get_event_log(t.year).length >= 1 "
                    ng-click="showHide(t.log_div_id)"
                    class="timeline_event_log_revealer round_top"
                >
                    LY {{t.year}} Event Log &#9662;
                </div>

                <div
                    class="timeline_event_log_container hidden"
                    id="{{t.log_div_id}}"
                    ng-click="showHide(t.log_div_id)"
                >
                    <span
                        ng-repeat="l in get_event_log(t.year)"
                    >
                        <div
                            ng-class-odd="'log_zebra'"
                            ng-class-even="'log_no_zebra'"
                            ng-bind-html="l.event|trustedHTML"
                        >
                        </div>
                   </span>

                    <div class="timeline_event_log_bottom round_bottom" > </div>
                    <br/>
                </div>

            </div> <!-- iterator ng-repeat t in timeline -->


        </div><!-- full size modal  -->

    </div> <!-- modal (parent) -->

    \n"""


class survivor:

    form = Template("""\n\

    <script src="/media/survivorSheet.js?v=$application_version"></script>

    <div
        id = "survivor_sheet_angularjs_controller_container"
        ng-controller="survivorSheetController"
        ng-init="
            initialize('survivorSheet', '$user_id', '$api_url','$settlement_id','$survivor_id');
            getLineage();
        "
    >
        <span class="tablet_and_desktop nav_bar survivor_sheet_gradient"></span>
        <span class="mobile_only nav_bar_mobile survivor_sheet_gradient"></span>
        <div class="top_nav_spacer">hidden</div>


        <div id="asset_management_left_pane">

            <input
                id="survivor_sheet_survivor_name"
                type="text"
                name="name"
                ng-value="survivor.sheet.name"
                ng-placeholder="Survivor Name"
                ng-model="survivor.sheet.name"
                ng-blur="setSurvivorName()"
                onClick="this.select()"
            />

            <hr class="invisible"/>

            <div
                id="epithet_angular"
                ng-controller="epithetController"
                title="Survivor epithets. Use controls below to add. Click or tap to remove!"
            >

                <ul id="epithet_angular_ul">
                    <li
                        class="touch_me"
                        ng-repeat="e in survivor.sheet.epithets"
                        ng-click="rmEpithet($index)"
                        style="
                            background-color: #{{settlement.game_assets.epithets[e].bgcolor}};
                            color: #{{settlement.game_assets.epithets[e].color}};
                            border-color: #{{settlement.game_assets.epithets[e].bordercolor}};
                        "
                    >
                        <span>{{settlement.game_assets.epithets[e].name}}</span>
                    </li>
                </ul>
                <br/>
                <select
                    name="add_epithets"
                    ng-model="new_epithet"
                    ng-change="addEpithet()"
                    ng-options="e.handle as e.name for e in epithetOptions"
                >
                    <option value="" disabled selected>Add Epithets</option>
                </select>

            </div>

            <!-- AFFINITIES -->
            <button
                id="modalAffinityButton"
                class="modal_affinity_launcher"
                title="Permanent Affinities: click or tap to update!"
            >
                <span
                    ng-repeat="a in ['red','green','blue']"
                >
                    <span
                        class="affinity_{{a}} affinity_span"
                    >
                        {{survivor.sheet.affinities[a]}}
                    </span>
                </span>
            </button>
            <!-- end of AFFINITIES -->

            <!-- SAVIOR controller includes SEX -->
            <div class="survivor_sheet_savior_and_sex_controls" >
                <div class="help-tip survivor_sheet_survivor_sex">
                    <font class="legend">Survivor Sex:</font>
                    <p ng-if="survivor.sheet.sex == survivor.sheet.effective_sex">
                        {{survivor.sheet.name}} has a sex of '{{survivor.sheet.sex}}'.
                    </p>
                    <p ng-if="survivor.sheet.sex != survivor.sheet.effective_sex">
                        {{survivor.sheet.name}} has a sex of '{{survivor.sheet.sex}}', which is different from the survivor's effective sex, '{{survivor.sheet.effective_sex}}', due to a curse.
                    </p>
                </div>
                <input
                    id="survivor_sheet_survivor_sex"
                    class="survivor_sex_text"
                    name="sex"
                    ng-model="survivorSex"
                    ng-value="survivor.sheet.effective_sex"
                    ng-blur="updateSex()"
                />

                <label
                    id="survivor_sheet_avatar"
                    for="avatar_file_input"
                    ng-if="survivor.sheet.avatar != undefined"
                >
                    <img
                        class="survivor_avatar_image mobile_and_tablet"
                        ng-src="/get_image?id={{survivor.sheet.avatar.$oid}}"
                        alt="Click to change the avatar image for {{survivor.sheet.name}}"
                    />
                </label>
                <label
                    id="survivor_sheet_avatar"
                    for="avatar_file_input"
                    ng-if="survivor.sheet.avatar == undefined"
                >
                    <img
                        class="survivor_avatar_image mobile_and_tablet"
                        ng-src="/media/default_avatar_{{survivor.sheet.effective_sex}}.png"
                        alt="Click to change the avatar image for {{survivor.sheet.name}}"
                        />
                </label>

                <div class="survivor_sheet_dynamic_button_holder">

                    <button
                        id="cursedControlsModal"
                        class="orange bold modal_opener"
                    >
                        Cursed Items ({{survivor.sheet.cursed_items.length}})
                    </button>

                    <button
                        id="saviorControlsModal"
                        class="orange bold modal_opener"
                        ng-if="settlement.game_assets.campaign.saviors == true"
                        ng-init="registerModalDiv('saviorControlsModal','modalSavior')"
                    >
                        Savior
                    </button>

                    <button
                        id="dragonControlsModal"
                        class="orange bold modal_opener"
                        ng-if="settlement.game_assets.campaign.dragon_traits != undefined"
                        ng-init="registerModalDiv('dragonControlsModal','dragonTraitsModal')"
                        ng-click="reinitialize()"
                    >
                        Dragon Traits ({{survivor.dragon_traits.trait_list.length}})
                    </button>

                </div>

            </div> <!-- savior controller -->


        <div class="survivor_dead_retired_container" >

            <!-- favorite controls -->
            <input
                id="favorite"
                name="toggle_favorite"
                class="kd_css_checkbox"
                type="checkbox"
                ng-model = 'miscAttribs.favoriteBox'
                ng-click = "toggleFavorite()"
                ng-checked = 'survivor.sheet.favorite.indexOf(user_login) !== -1'
            />
            <label
                class="toggle_favorite"
                for="favorite"
            >
                Favorite
            </label>

            <!-- RETIRED -->
            <input
                id="retired"
                class="kd_css_checkbox"
                type="checkbox"
                name="toggle_retired"
                ng-model="survivor.sheet.retired"
                ng-checked="survivor.sheet.retired == true"
                ng-change="setRetired()"
            >
            <label
                for="retired"
                style="float: right; clear: none;"
            >
                Retired &nbsp;
            </label>

            <button
                id="modalDeathButton"
                class="modal_death_button"
                ng-class="{true: 'survivor_is_dead', false: 'unpressed_button'}[survivor.sheet.dead]"
                title="Open the Controls of Death!"
            >
                Dead
            </button>

        </div> <!-- survivor_dead_retired_container -->



        <hr />

            <div
                class="sotf_reroll_controls"
                ng-if="settlement.sheet.principles.indexOf('survival_of_the_fittest') != -1"
                ng-controller="sotfRerollController"
            >
                <input
                    id="sotfRerollCheckbox"
                    type="checkbox"
                    class="kd_css_checkbox kd_radio_option"
                    ng-model="sotf_reroll_toggle"
                    ng-checked="survivor.sheet.sotf_reroll == true"
                    ng-click="sotfToggle()"
                />

                <label
                    for="sotfRerollCheckbox"
                >
                    Once per lifetime reroll
                    <p class="sotf_reroll_caption">
                        <b>Survival of the fittest:</b> Once per lifetime, a survivor may
                        reroll a single roll result. They must keep this result.</b>
                    </p>
                </label>

                <hr/>

            </div> <!-- sotf reroll -->



        <div
            ng-controller="survivalController"
        >

            <div class="survivor_sheet_survival_container">
                <button
                    class="survivor_sheet_survival_button"
                    ng-click="updateSurvival(1)"
                >
                    &#9652;
                </button>
                <input
                    id="survivalBox"
                    class="survivor_sheet_survival_box"
                    type="number"
                    name="survival"
                    ng-model="survival_input_value"
                    ng-blur="setSurvival()"
                    ng-value="survivor.sheet.survival"
                    min="0"
                />
                <button
                    class="survivor_sheet_survival_button"
                    ng-click="updateSurvival(-1)"
                >
                    &#9662;
                </button>
            </div> <!-- big_number_container -->

            <div
                id="SLwarning"
                class="kd_alert_no_exclaim control_error"
                style="display: none"
            >
                {{settlement.sheet.name}} Survival Limit is <b>{{settlement.sheet.survival_limit}}</b>!
            </div>

            <div class="help-tip big_number_caption survivor_sheet_survival_limit_caption">
                Survival
                <p>{{settlement.sheet.name}} Survival Limit is <b>{{settlement.sheet.survival_limit}}</b></p>
            </div>


            <hr />


            <div id="survivor_survival_actions_container">

                <h3>Survival Actions</h3>

                <p class="survival_actions_container">
                     <input
                        id="cannot_spend_survival"
                        class="survivor_sheet_toggle"
                        name="toggle_cannot_spend_survival"
                        type="checkbox"
                        ng-model='survivor.sheet.cannot_spend_survival'
                        ng-change='toggleStatusFlag()'
                        ng-checked="survivor.sheet.cannot_spend_survival == true"
                    />

                    <label
                        id="cannot_spend_survival"
                        class="float_right_toggle"
                        for="cannot_spend_survival"
                    >
                        Cannot<br/>spend<br/>survival
                    </label>

                    <div
                        ng-if="survivor.survival_actions != undefined"
                    >
                        <div
                            class="help-tip survivor_sheet_survival_action"
                            ng-repeat="sa in survivor.survival_actions"
                        >
                            <font
                                ng-if="sa.available == false"
                                class="survivor_sheet_survival_action_item"
                            >
                                {{sa.name}}
                            </font>
                            <font
                                ng-if="sa.available == true"
                                class="survivor_sheet_survival_action_item survival_action_emphasize"
                            >
                                {{sa.name}}
                            </font>
                            <p>{{sa.title_tip}}</p>
                        </div>
                    </div>

                </p>

                <div id="wideButtonHolder" class="survivor_sheet_dynamic_button_holder desktop_only">
                    <!-- This holds optional survivor modal openers; otherwise, it's empty -->
                </div>

                <label
                    id="survivor_sheet_avatar"
                    for="avatar_file_input"
                    ng-if="survivor.sheet.avatar != undefined"
                >
                    <img
                        class="survivor_avatar_image desktop_only"
                        ng-src="/get_image?id={{survivor.sheet.avatar.$oid}}"
                        alt="Click to change the avatar image for {{survivor.sheet.name}}"
                        />
                </label>
                <label
                    id="survivor_sheet_avatar"
                    for="avatar_file_input"
                    ng-if="survivor.sheet.avatar == undefined"
                >
                    <img
                        ng-if="survivor.sheet.effective_sex != undefined"
                        class="survivor_avatar_image desktop_only"
                        ng-src="/media/default_avatar_{{survivor.sheet.effective_sex}}.png"
                        alt="Click to change the avatar image for {{survivor.sheet.name}}"
                        />
                </label>

                <input
                    onchange='document.getElementById("avatar_change_form").submit(); showFullPageLoader();'
                    id="avatar_file_input"
                    class="hidden"
                    type="file"
                    name="survivor_avatar"
                    accept="image/*"
                    form="avatar_change_form"
                >


            </div> <!-- survivor_survival_actions_container  -->
        </div> <!-- survivalController scope -->


        <a id="edit_attribs">
            <hr>
        </a>


        <div
            ng-if="settlement.survivor_bonuses.survivor_buff.length != 0"
            class="survivor_sheet_survivor_settlement_bonuses"
        >

            <h3>Survivor Bonuses</h3>

            <p class="settlement_buff" ng-repeat="b in settlement.survivor_bonuses.survivor_buff">
                <i>{{b.name}}:</i> <span ng-bind-html="b.desc|trustedHTML"></span>
            </p>

            <hr/>
        </div>

        <h3>Survivor Notes</h3>

        <div
            id="survivor_notes_angular"
            ng-controller="survivorNotesController"
            title="Survivor notes controls. Survivor notes are included in the Campaign Summary Survivor Search results."
        >
            <p>Add notes to {{survivor.sheet.name}}'s Survivor Sheet using the controls below. Click or tap a note to remove it.</p>
            <ul class="survivor_sheet_survivor_note">
            <li
                class="survivor_sheet_survivor_note touch_me"
                ng-repeat="x in survivor.notes"
                ng-click="removeNote($index, x._id.$oid)"
            >
                {{x.note}}
            </li>
        </ul>

        <input
            class="survivor_sheet_add_survivor_note"
            ng-model="note"
            placeholder="Add a Survivor Note"
            onClick="this.select()"
        />
        <button
            class="survival_limit_style survivor_sheet_add_survivor_note"
            ng-click="addNote()"
        >
            Add Note
        </button>
    <br/>

    <!-- suppress error text if not debugging -->
    <!-- <p>{{errortext}}</p> -->
    </div>


        </div> <!-- asset_management_left_pane -->



                <!-- MIDDLE ASSET MANAGEMENT PANE STARTS HERE -->



        <a id="edit_hit_boxes">
            <hr class="mobile_only"/>
        </a>

        <div id="asset_management_middle_pane" ng-if="survivor != undefined">


            <!-- BRAIN -->

            <div class="survivor_hit_box insanity_box">

                <div class="big_number_container right_border">

                    <button
                        class="incrementer"
                        ng-click="incrementAttrib('Insanity',1)"
                    >
                        +
                    </button>


                    <input
                        id="insanityBox"
                        type="number"
                        class="shield"
                        name="Insanity" min="0"
                        ng-model="survivor.sheet.Insanity"
                        ng-value="survivor.sheet.Insanity"
                        ng-blur="updateAttrib('Insanity')"
                        ng-class="{true: 'maroon_text'}[survivor.sheet.Insanity >= 3]"
                    />

                    <font id="hit_box_insanity">Insanity</font>

                    <button
                        class="decrementer"
                        ng-click="incrementAttrib('Insanity',-1)"
                    >
                        -
                    </button>

                 </div> <!-- big_number_container -->

                 <div class="hit_box_detail">
                     <input
                        id="damage_brain_light"
                        name="toggle_brain_damage_light"
                        class="damage_box_$brain_damage_light_checked damage_box"
                        type="submit"
                        value=" "
                        onclick="toggleDamage('damage_brain_light','$survivor_id');"
                    />

                    <h2>Brain</h2>

                </div> <!-- hit_box_detail -->

                <p>If your insanity is 3+, you are <b>Insane</b>.</p>

            </div> <!-- survivor_hit_box -->



            <!-- HEAD -->

            <div class="survivor_hit_box">
                <div class="big_number_container right_border">
                    <button
                        class="incrementer"
                        onclick="stepAndSave('up','headBox','survivor','$survivor_id');"
                    >
                        +
                    </button>
                    <input
                        id="headBox"
                        type="number"
                        class="shield"
                        name="Head"
                        value="$head"
                        min="0"
                        onchange="updateAssetAttrib(this,'survivor','$survivor_id')"
                    />
                    <button
                        class="decrementer"
                        onclick="stepAndSave('down','headBox','survivor','$survivor_id');"
                    >
                        -
                    </button>
                </div>
                <div class="hit_box_detail">
                 <input
                    id="damage_head_heavy"
                    onclick="toggleDamage('damage_head_heavy','$survivor_id');"
                    type="submit"
                    class="damage_box_$head_damage_heavy_checked heavy_damage damage_box"
                    name="toggle_head_damage_heavy"
                    value=" "
                 />
                 <h2>Head</h2>
                </div> <!-- hit_box_detail -->
                <p><b>H</b>eavy Injury: Knocked Down</p>
            </div> <!-- survivor_hit_box -->



            $arms_hit_box
            $body_hit_box
            $waist_hit_box
            $legs_hit_box



            <a id="edit_wpn_prof" class="mobile_and_tablet"></a>

            <div ng-controller="secondaryAttributeController">

                <!-- HUNT XP -->
                <div class="survivor_sheet_secondary_attrib_container">
                    <div class="big_number_container">
                        <button
                            class="incrementer"
                            ng-click="incrementAttrib('hunt_xp',1)"
                        >
                            +
                        </button>
                        <input
                            id="huntXPBox"
                            class="big_number_square"
                            type="number"
                            ng-model="survivor.sheet.hunt_xp"
                            ng-value="survivor.sheet.hunt_xp"
                            ng-blur="updateAttrib('hunt_xp')"
                        />
                        <button
                            class="decrementer"
                            ng-click="incrementAttrib('hunt_xp',-1)"
                        >
                            -
                        </button>
                    </div> <!-- big_number_container -->

                    <div class="survivor_sheet_secondary_attribute_caption">
                        <div class="big_number_caption">Hunt XP</div>
                        <p>
                            <font class="kdm_font">g</font> <b>Age</b> occurs at 2, 6, 10 and 15. {{survivor.sheet.name}} retires at 16.
                        </p>
                    </div>

                </div> <!-- HUNT XP -->

                <hr class="mobile_only"/>
                <!-- WEAPON PROFICIENCY -->
            <div class="survivor_sheet_secondary_attrib_container">
                <div class="big_number_container">
                    <button
                        class="incrementer"
                        ng-click="incrementAttrib('Weapon Proficiency',1)"
                    >
                        +
                    </button>
                    <input
                        id="proficiencyBox"
                        class="big_number_square"
                        type="number"
                        ng-model='survivor.sheet["Weapon Proficiency"]'
                        ng-value='survivor.sheet["Weapon Proficiency"]'
                        ng-blur="updateAttrib('Weapon Proficiency')"
                    />
                    <button
                        class="decrementer"
                        ng-click="incrementAttrib('Weapon Proficiency',-1)"
                    >
                        -
                    </button>
                </div> <!-- big_number_container -->
                <div class="survivor_sheet_secondary_attribute_caption">
                    <div class="big_number_caption">Weapon Proficiency</div>
                        <select
                            ng-model="survivor.sheet.weapon_proficiency_type"
                            ng-options="w.handle as w.name for w in settlement.game_assets.weapon_proficiency"
                            ng-change="setWeaponProficiencyType()"
                            ng-selected="survivor.sheet.weapon_proficiency_type"
                        >
                            <option disabled value="">Choose a Weapon Type</option>
                        </select>

                    <p>
                        <b>Specialist</b> at 3<br/><b>Master</b> at 8.
                    </p>
                </div>

            </div> <!-- survivor_sheet_secondary_attrib_container -->

                <hr class="mobile_only"/>

                <!-- COURAGE AND UNDERSTANDING -->

                <div class="survivor_sheet_secondary_attrib_container">
                    <div class="big_number_container">
                        <button
                            class="incrementer"
                            ng-click="incrementAttrib('Courage',1)"
                        >
                            +
                        </button>
                        <input
                            id="courageBox"
                            class="big_number_square"
                            type="number"
                            ng-value="survivor.sheet.Courage"
                            ng-model="survivor.sheet.Courage"
                            ng-blur="updateAttrib('Courage')"
                        />
                        <button
                            class="decrementer"
                            ng-click="incrementAttrib('Courage',-1)"
                        >
                            -
                        </button>
                    </div>

                    <div class="survivor_sheet_secondary_attribute_caption">
                        <div class="big_number_caption">Courage</div>
                        <div ng-repeat="m in settlement.survivor_attribute_milestones.Courage">
                            <p ng-repeat="v in m.values">
                                <font class="kdm_font">g</font>
                                <b>{{settlement.game_assets.events[m.handle].name}}</b>
                                (p.{{settlement.game_assets.events[m.handle].page}}) occurs at {{v}}.
                            </p>
                        </div>
                    </div>

                </div> <!-- survivor_sheet_secondary_attrib_container -->

                <hr class="mobile_only"/>

                <!-- UNDERSTANDING -->

                <div class="survivor_sheet_secondary_attrib_container">
                    <div class="big_number_container">
                        <button
                            class="incrementer"
                            ng-click="incrementAttrib('Understanding',1)"
                        >
                            +
                        </button>
                        <input
                            id="understandingBox"
                            class="big_number_square"
                            type="number"
                            ng-value="survivor.sheet.Understanding"
                            ng-model="survivor.sheet.Understanding"
                            ng-blur="updateAttrib('Understanding')"
                        />
                        <button
                            class="decrementer"
                            ng-click="incrementAttrib('Understanding',-1)"
                        >
                            -
                        </button>
                    </div>

                    <div class="survivor_sheet_secondary_attribute_caption">
                        <div class="big_number_caption">Understanding</div>
                        <div ng-repeat="m in settlement.survivor_attribute_milestones.Understanding">
                            <p ng-repeat="v in m.values">
                                <font class="kdm_font">g</font>
                                <b>{{settlement.game_assets.events[m.handle].name}}</b>
                                (p.{{settlement.game_assets.events[m.handle].page}}) occurs at {{v}}.
                            </p>
                        </div>
                    </div>

                </div> <!-- survivor_sheet_secondary_attrib_container -->

            </div> <!-- SECONDARY ATTRIB CONTROLLER SCOPE -->

        </div> <!-- asset_management_middle_pane -->



        <div id="survivor_sheet_right_pane" >


        <!-- SURVIVOR SPECIAL ATTRIBUTES -->

        <div
            ng-controller="survivorSpecialAttribsController"
            ng-if="settlement.game_assets.survivor_special_attributes.length >= 1"
            class="survivor_sheet_special_attributes_container"
        >
            <div
                class = "survivor_sheet_special_attribute_container clickable"
                ng-repeat="s in settlement.game_assets.survivor_special_attributes"
                ng-click="toggleSpecialAttrib(s.handle)"
                ng-class="{active: survivor.sheet[s.handle] == true}",
                title = "{{s.title_tip}}"
            >
                <div
                    class="special_attribute_checkbox"
                    ng-class="{active: survivor.sheet[s.handle] == true}"
                ></div>
                <div
                    class="special_attribute_text"
                    ng-class="{active: survivor.sheet[s.handle] == true}"
                >
                    {{s.name}}
                </div>
            </div>

        </div><!-- special attributes controller -->

        <hr ng-if="settlement.game_assets.survivor_special_attributes.length >= 1">


        <!-- PARTNER CONTROLS - why hasn't this been refactored? -->

        <form
            method="POST"
            action="#edit_misc_attribs"
            ng-if="survivor.sheet.abilities_and_impairments.indexOf('partner') != -1"
        >
            <button class="hidden"></button>
            <input type="hidden" name="modify" value="survivor" />
            <input type="hidden" name="asset_id" value="$survivor_id" />
            $partner_controls
        </form>




        <!-- FARTING ARTS -->

        <a id="edit_fighting_arts" class="mobile_and_tablet"></a>


        <div
            ng-controller='fightingArtsController'
            ng-init="setFAoptions()"
            ng-if="survivor.sheet.fighting_arts != undefined"
        >
<!--
            <div class="help-tip help-icon kd_promo">
                <p> Use the drop-down controls below to add new Fighting Arts; click or tap a Fighting Art to remove it. <br/>Fighting Arts with levels, such as "Silk Surgeon", may be improved by tapping or clicking on the desired level.</p>
            </div>
-->

            <h3>Fighting Arts</h3>

            <input
                id="survivor_sheet_cannot_use_fighting_arts"
                class="survivor_sheet_toggle"
                name="toggle_cannot_use_fighting_arts"
                type="checkbox"
                ng-model='survivor.sheet.cannot_use_fighting_arts'
                ng-change='toggleStatusFlag()'
                ng-checked="survivor.sheet.cannot_use_fighting_arts == true"
            />
            <label
                id="survivor_sheet_cannot_use_fighting_arts_label"
                class="float_right_toggle"
                for="survivor_sheet_cannot_use_fighting_arts"
             >
                Cannot use<br/>Fighting Arts
            </label>

            <p>Maximum 3.</p>


            <div
                title="Click or tap to remove survivor Fighting Arts."
                class="survivor_sheet_card_container"
            >
                <div
                    ng-repeat="fa_handle in survivor.sheet.fighting_arts"
                    class="survivor_sheet_card survivor_sheet_gradient clickable"
                    ng-class="{true: 'faded'}[survivor.sheet.cannot_use_fighting_arts]"
                >
                    <span ng-if = "settlement.game_assets.fighting_arts[fa_handle] == undefined">
                        <img src="/media/loading_lantern.gif"><br/>
                        Loading Fighting Art data...
                    </span>
                    <span
                        ng-init="
                            FA = settlement.game_assets.fighting_arts[fa_handle];
                            expansion_handle = settlement.game_assets.fighting_arts[fa_handle].expansion;
                            expansion_dict = settlement.game_assets.expansions[expansion_handle];
                        "
                        ng-if = "settlement.game_assets.fighting_arts[fa_handle] != undefined"
                        ng-click="rmFightingArt(fa_handle, $index)"
                        title="Click or tap to remove {{FA.name}} from {{survivor.sheet.name}}"
                    >

                        <div
                            class="settlement_sheet_card_expansion_flair"
                            ng-if="expansion_handle != null"
                            title="{{expansion_dict.name}} expansion Fighting Art"
                            style='
                                color: #{{expansion_dict.flair.color}};
                                background-color: #{{expansion_dict.flair.bgcolor}};
                            '
                            >
                        {{expansion_dict.name}}
                        </div>

                            <!-- regular title -->
                        <b ng-if="FA.constellation == null" class="card_title">
                            {{FA.name}}
                        </b>

                            <!-- dragon trait title -->
                        <b ng-if="FA.constellation != null" class="card_title card_constellation">
                            {{FA.name}}
                        </b>

                        <p class="survivor_sheet_card_subhead">- {{FA.type_pretty}} -</p>
                        <p class="survivor_sheet_fighting_art_color_span {{FA.type}}_gradient"> </p>
                        <div
                            class="survivor_sheet_card_text"
                            ng-bind-html="FA.desc|trustedHTML"
                        >
                        </div>
                        <div
                            ng-repeat="(level, desc) in FA.levels track by $index"
                            ng-if="desc != ''"
                            title="Tap or click a {{FA.name}} skill level to toggle it on or off."
                        >
                            <div
                                class="survivor_sheet_card_level_block clickable"
                                ng-click="toggleLevel($event, fa_handle, level)"
                                ng-if="survivor.sheet.fighting_arts_levels[fa_handle].indexOf($index) !== -1"
                            >
                                <span class="survivor_sheet_card_level_number toggled_on">{{level}}</span>
                                <span
                                    class="survivor_sheet_card_level_desc toggled_on"
                                    ng-bind-html="desc|trustedHTML"
                                >
                                </span>
                            </div>
                            <div
                                class="survivor_sheet_card_level_block clickable"
                                ng-click="toggleLevel($event, fa_handle, level)"
                                ng-if="survivor.sheet.fighting_arts_levels[fa_handle].indexOf($index) === -1"
                            >
                                <span class="survivor_sheet_card_level_number">{{level}}</span>
                                <span class="survivor_sheet_card_level_desc" ng-bind-html="desc|trustedHTML"></span>
                            </div>
                        </div> <!-- levels -->
                        <div class="survivor_sheet_card_click_to_remove">Tap or click to <b>remove</b>.</div>
                    </span>
                </div>
            </div> <!-- survivor_sheet_card_container -->

            <div class="survivor_sheet_card_asset_list_container" ng-if="survivor.sheet.fighting_arts.length <= 2">
                <span class="empty_bullet" /></span>
                <select
                    name="add_fighting_arts"
                    ng-model="userFA.newFA"
                    ng-change="addFightingArt(); userFA.newFA = FAoptions[0]"
                    ng-blur="userFA.newFA = FAoptions[0]"
                    ng-options="fa.handle as (fa.name + ' (' + fa.type_pretty + ')'  ) for fa in FAoptions | orderObjectBy:'handle':false"
                >
                    <option value="" disabled selected>Add Fighting Art</option>
                </select>
            </div>

        <hr />

        </div> <!-- fartingArtsController -->


        <a id="edit_disorders" class="mobile_and_tablet"></a>


        <!-- DISORDERS -->

        <div ng-controller="disordersController" ng-if="survivor.sheet.disorders != undefined">

            <h3>Disorders</h3>

            <p class="survivor_sheet_game_asset_tip">Maximum 3.</p>

            <div
                title="Click or tap to remove survivor Disorders."
                class="survivor_sheet_card_container disorders_container"
            >
                <div
                    ng-repeat="d_handle in survivor.sheet.disorders"
                    class="survivor_sheet_card disorder_card_gradient clickable"
                >
                    <span ng-if = "settlement.game_assets.disorders[d_handle] == undefined">
                        <img src="/media/loading_lantern.gif"><br/>
                        Loading Disorder data...
                    </span>
                    <span
                        ng-init="
                            D = settlement.game_assets.disorders[d_handle];
                            expansion_handle = settlement.game_assets.disorders[d_handle].expansion;
                            expansion_dict = settlement.game_assets.expansions[expansion_handle];
                        "
                        ng-if = "settlement.game_assets.disorders[d_handle] != undefined"
                        ng-click="rmDisorder(d_handle, $index)"
                        title="Click or tap to remove {{D.name}} from {{survivor.sheet.name}}"
                    >
                        <!-- EXPANSION FLAIR -->

                        <div
                            class="settlement_sheet_card_expansion_flair"
                            ng-if="expansion_handle != null"
                            title="{{expansion_dict.name}} expansion Disorder"
                            style='
                                color: #{{expansion_dict.flair.color}};
                                background-color: #{{expansion_dict.flair.bgcolor}};
                            '
                        >
                            {{expansion_dict.name}}
                        </div>

                        <!-- regular title -->
                        <b ng-if="D.constellation == null" class="card_title">
                            {{D.name}}
                        </b>

                        <!-- dragon trait title -->
                        <b ng-if="D.constellation != null" class="card_title card_constellation">
                            {{D.name}}
                        </b>
                        <div
                            class="survivor_sheet_card_text disorder_flavor_text"
                            ng-bind-html="D.flavor_text|trustedHTML"
                        >
                        </div>
                        <div
                            class="survivor_sheet_card_text"
                            ng-bind-html="D.survivor_effect|trustedHTML"
                        >
                        </div>

                        <div class="survivor_sheet_card_click_to_remove remove_disorder">
                            Tap or click to <b>remove</b>.
                        </div>

                    </span> <!-- actual disorder span -->
                </div> <!-- disorder ng-repeat -->
            </div> <!-- disorders survivor_sheet_card_container -->

            <div class="survivor_sheet_card_asset_list_container" ng-if="survivor.sheet.disorders.length <= 2">
                <span class="empty_bullet" /></span>
                <select
                    name="add_disorders"
                    ng-model="userD.newD"
                    ng-change="addDisorder(); userD.newD = dOptions[0]"
                    ng-blur="userD.newD = dOptions[0]"
                    ng-options="d.handle as d.name for d in dOptions | orderObjectBy:'handle':false"
                >
                    <option value="" disabled selected>Add Disorder</option>
                </select>
            </div>
        </div> <!-- disordersController -->


        <a id="edit_abilities" class="mobile_only"></a>
        <hr />


        <!-- ABILITIES AND IMPAIRMENTS -->


        <h3>Abilities & Impairments</h3>

        <div ng-controller="skipNextHuntController">
            <input
                id="skip_next_hunt"
                name="toggle_skip_next_hunt"
                type="checkbox"
                class="survivor_sheet_toggle"
                ng-model='survivor.sheet.skip_next_hunt'
                ng-change='toggleStatusFlag()'
                ng-checked="survivor.sheet.skip_next_hunt == true"
            />
            <label
                class="float_right_toggle"
                for="skip_next_hunt"
                id="skip_next_hunt_label"
            >
                Skip Next<br/>
                Hunt
            </label>
        </div>

        <div
            title="Click or tap to remove survivor Abilities & Impairments."
            ng-controller="abilitiesAndImpairmentsController"
        >

            <div
                class="survivor_sheet_ai_container"
                ng-repeat="ai_handle in survivor.sheet.abilities_and_impairments track by $index"
            >
                <span
                    class="survivor_sheet_ai clickable"
                    ng-click="rmAI(ai_handle, $index)"
                    title="Click or tap to remove '{{settlement.game_assets.abilities_and_impairments[ai_handle].name}}'"
                >
                    <b
                        ng-if="settlement.game_assets.abilities_and_impairments[ai_handle].constellation == undefined"
                    >
                        {{settlement.game_assets.abilities_and_impairments[ai_handle].name}}:
                    </b>
                    <b
                        ng-if="settlement.game_assets.abilities_and_impairments[ai_handle].constellation != undefined"
                        class="card_constellation"
                    >
                        {{settlement.game_assets.abilities_and_impairments[ai_handle].name}}:
                    </b>
                    <span ng-bind-html="settlement.game_assets.abilities_and_impairments[ai_handle].desc|trustedHTML"></span>
                </span>

            </div>

            <div class="line_item">
                <span class="empty_bullet" /></span>
                <select
                    name="add_abilities_and_impairments"
                    ng_model="newAI"
                    ng_change="addAI()"
                    ng-options="ai.handle as (ai.name + ' (' + ai.type_pretty + ')'  ) for ai in AIoptions"
                >
                    <option value="" disabled selected>Add Abilities & Impairments</option>
                </select>
            </div>

        <hr/>

        </div> <!-- A&I controller -->



        <a
            id="edit_lineage"
            class="mobile_and_tablet"
        >
            &nbsp;
        </a>


        <div
            ng-controller="lineageController"
            ng-if="lineage != undefined"
            class="lineage_block"
        >

            <h3 title="Survivor family and relationship information is stored here">Lineage</h3>
            <p class="lineage_subhead">Facts about the life and relationships of <b>{{survivor.sheet.name}}</b> will appear here
            as the campaign unfolds.</p>

            <div class="survivor_sheet_block_group lineage_block">

                <div>
                    <h4>Biography</h4>

                    <!-- founder -->
                    <p ng-if="survivor.sheet.founder == true">
                        <font class="kdm_font_hit_locations">a</font> Founding member of {{settlement.sheet.name}}. 
                    </p>

                    <!-- born or joined -->
                    <p ng-if="survivor.sheet.father != undefined || survivor.sheet.mother != undefined">
                        <font class="kdm_font_hit_locations">a</font> Born in LY{{survivor.sheet.born_in_ly}}. 
                    </p>
                    <p ng-if="survivor.sheet.father == undefined && survivor.sheet.mother == undefined && survivor.sheet.founder == false">
                        <font class="kdm_font_hit_locations">a</font> Joined the settlement in LY{{survivor.sheet.born_in_ly}}.
                    </p>

                    <!-- inheritance -->
                    <p ng-repeat="ai in survivor.sheet.inherited.father.abilities_and_impairments">
                        <font class="kdm_font_hit_locations">a</font> Inherited <b>{{settlement.game_assets.abilities_and_impairments[ai].name}}</b> from <b>{{survivor.sheet.parents.father.name}}</b> (father).
                    </p>
                    <p ng-repeat="ai in survivor.sheet.inherited.mother.abilities_and_impairments">
                        <font class="kdm_font_hit_locations">a</font> Inherited <b>{{settlement.game_assets.abilities_and_impairments[ai].name}}</b> from <b>{{survivor.sheet.parents.mother.name}}</b> (mother).
                    </p>

                    <!-- returning survivor -->
                    <p ng-if="survivor.sheet.returning_survivor.length >= 1">
                        <font class="kdm_font_hit_locations">a</font> Returning survivor in the following Lantern Years: {{survivor.sheet.returning_survivor.join(', ')}}. 
                    </p>
                    <p ng-if="survivor.sheet.dead == true" class="maroon_text">
                        <font class="kdm_font_hit_locations">a</font> <b>Died in LY{{survivor.sheet.died_in}}.</b>
                    </p>
                </div> <!-- bio -->

                <div
                    id="survivorParents"
                    class="survivor_sheet_parents_container"
                    ng-if="survivor.sheet.founder == false"
                >
                    <h4>Parents</h4>

                    <select
                        class="survivor_sheet_father_picker"
                        ng-model="survivor.sheet.father.$oid"
                        ng-selected="survivor.sheet.father"
                        ng-options="s.sheet._id.$oid as s.sheet.name for s in settlement.user_assets.survivors | filter:maleFilter"
                        ng-change="setParent('father',survivor.sheet.father.$oid)"
                    >
                        <option disabled value="">Father</option>
                    </select>

                    <select
                        class="survivor_sheet_mother_picker"
                        ng-model="survivor.sheet.mother.$oid"
                        ng-selected="survivor.sheet.mother"
                        ng-options="s.sheet._id.$oid as s.sheet.name for s in settlement.user_assets.survivors | filter:femaleFilter"
                        ng-change="setParent('mother', survivor.sheet.mother.$oid)"
                    >
                        <option disabled value="">Mother</option>
                    </select>


                </div>

                <div ng-if="lineage.intimacy_partners >= 1">
                    <h4>Intimacy Partners</h4>
                    <p>
                        <span ng-repeat="s in lineage.intimacy_partners">{{s.name}}{{$last ? '' : ', '}}</span>
                    </p>
                </div>

                <div ng-if="lineage.siblings.full.length >= 1 || lineage.siblings.half.length >= 1">
                    <h4>Siblings</h4>
                    <p ng-if='lineage.siblings.full.length >= 1'>
                        <i>Full:</i> <span ng-repeat='s in lineage.siblings.full'>
                            {{s.name}}{{$last ? '' : ', '}}
                        </span>
                    </p>
                    <p ng-if='lineage.siblings.half.length >= 1'>
                        <i>Half</i>: <span ng-repeat='s in lineage.siblings.half'>
                            {{s.name}}{{$last ? '' : ', '}}
                        </span>
                    </p>
                </div> <!-- siblings container -->

                <div ng-if="lineage.intimacy_partners.length >= 1">
                    <h4>Children</h4>
                    <p span ng-repeat="p in lineage.intimacy_partners">
                        <i>with</i> <b>{{p.name}}</b> [{{p.sex}}]</b><i>: </i>
                        <span ng-repeat="s in lineage.children[p._id.$oid]">
                            {{s.name}} (LY{{s.born_in_ly}}){{$last ? '' : ', '}}
                        </span>
                    </p>
                </div>

            <hr/>

            </div> <!-- survivor_sheet_block_group lineage -->


            <h3>Permissions</h3>
            <div class="survivor_sheet_block_group">
                <h4>Owner</h4>
                    <input
                        id="survivorOwnerEmail"
                        class="survivor_owner_email"
                        onclick="this.select()"
                        type="email"
                        name="email"
                        placeholder="email"
                        ng-model="newSurvivorEmail"
                        ng-value="survivor.sheet.email"
                        ng-blur="setEmail()"
                    />

                <p>Enter another registered user's email address here to make
                them a player in this campaign.</p>

                <h4>Access</h4>
                <p>Toggle this checkbox on or off to allow any player in this
                campaign to manage this survivor.</p>

                  <input
                    type="checkbox"
                    id="public"
                    class="kd_css_checkbox kd_radio_option"
                    name="toggle_public"
                    ng-model="public"
                    ng-checked="survivor.sheet.public"
                    ng-change="togglePublic()"
                  >
                  <label
                    class="public_survivor_toggle"
                    for="public"
                  >
                    Anyone May Manage this Survivor &nbsp;
                  </label>

                  <br/>
            </div> <!-- survivor_sheet_block_group perms -->

        </div> <!-- survivor_sheet_right_pane_blocks -->


        $remove_survivor_controls


        <!-- gotta put this here, outside of the other forms -->
        <form
            id="avatar_change_form"
            method="POST"
            action="#"
            enctype="multipart/form-data"
        >
            <input type="hidden" name="modify" value="survivor" />
            <input type="hidden" name="asset_id" value="$survivor_id" />
        </form>

    </div> <!-- asset_management_right_pane -->


    <div class="survivor_sheet_bottom_attrib_spacer">&nbsp;</div>


    <!--            THIS IS THE FOLD! Only Modal content below!     -->



    <!-- CURSED ITEMS CONTROLS -->

    <div
        id="modalCurseControls" class="modal"
        ng-controller="cursedItemsController"
        ng-init="registerModalDiv('cursedControlsModal','modalCurseControls')"
    >
        <div class="modal-content survivor_sheet_gradient">
            <span class="closeModal" onclick="closeModal('modalCurseControls')">×</span>

            <h3>Cursed Items</h3>
            <p>Use the controls below to add cursed items to a Survivor. Cursed
            gear cannot be removed from the Survivor's gear grid. Archive the gear
            when the survivor dies.</p>

            <div class="cursed_items_flex_container">

                <div class="cursed_item_toggle" ng-repeat="c in settlement.game_assets.cursed_items">
                    <input
                        id="{{c.handle}}"
                        class="cursed_item_toggle"
                        type="checkbox"
                        ng-model="cursedItemHandle"
                        ng-change="toggleCursedItem(c.handle)"
                        ng-checked="survivor.sheet.cursed_items.indexOf(c.handle) != -1"
                    />
                    <label
                        class="cursed_item_toggle"
                        for="{{c.handle}}"
                     >
                        <span class="cursed_item_name">{{c.name}}</span>

                        <div class="cursed_item_ability_block" ng-repeat="a in c.abilities_and_impairments">
                            <span
                                ng-if="settlement.game_assets.abilities_and_impairments[a] != undefined"
                                class="cursed_item_ability"
                            >
                                {{settlement.game_assets.abilities_and_impairments[a].name}} - 
                            </span>
                            <span
                                class="cursed_item_ability_desc"
                                ng-if="settlement.game_assets.abilities_and_impairments[a] != undefined"
                                ng-bind-html="settlement.game_assets.abilities_and_impairments[a].desc|trustedHTML"
                            >
                            </span>

                        </div>
                    </label>

                </div><!-- cursed_item_toggle -->
            </div> <!-- cursed_items_flex_container-->
        </div> <!-- modal-content -->
    </div> <!-- modal -->



    <!-- SURVIVOR ATTRIBUTE CONTROLS -->

    <div
        ng-controller="attributeController"
        class="survivor_sheet_attrib_controls"
    >

        <div
            ng-repeat="token in attributeTokens"
            ng-init="control_id = token.longName + '_controller'"
            id="{{token.longName}}_controls_container"
        >

            <div
                id="{{control_id}}"
                class="survivor_sheet_attrib_controls_modal survivor_sheet_gradient hidden"
            >
                <span
                    class="close_attrib_controls_modal"
                    ng-click="showHide(control_id)"
                >
                    X
                </span>

                <h3 class="{{token.buttonClass}}">{{token.longName}}</h3>

                <div
                    class="synthetic_attrib_total synthetic_attrib_total_{{token.longName}}"
                >
                    {{ survivor.sheet[token.longName] + survivor.sheet.attribute_detail[token.longName].gear + survivor.sheet.attribute_detail[token.longName].tokens }}
                </div>

                <hr/>

                <div class="survivor_sheet_attrib_controls_number_container_container">

                    <!-- start of BASE -->

                    <div class="survivor_sheet_attrib_controls_number_container">

                        <button
                            class="incrementer"
                            ng-click="incrementBase(token.longName, 1)"
                        >
                            +
                        </button>

                        <input
                            id="base_value_{{control_id}}"
                            type="number" string-to-number
                            class="survivor_sheet_attrib_controls_number"
                            onClick="this.select()"
                            ng-model="survivor.sheet[token.longName]"
                            ng-value="survivor.sheet[token.longName]"
                            ng-blur="setBase(token.longName)"
                        />

                        <button
                            class="decrementer"
                            ng-click="incrementBase(token.longName, -1)"
                        >
                            -
                        </button>

                        <p><b>Base</b></p>

                    </div> <!-- survivor_sheet_attrib_controls_number_container -->

                    <!-- end of BASE; start of GEAR -->

                    <div class="survivor_sheet_attrib_controls_number_container">

                        <button
                            class="incrementer"
                            ng-click="incrementDetail(token.longName, 'gear', 1)"
                        >
                            +
                        </button>

                        <input
                            id="gear_value_{{token.longName}}_controller"
                            type="number"
                            class="survivor_sheet_attrib_controls_number"
                            onClick="this.select()"
                            ng-model="survivor.sheet.attribute_detail[token.longName].gear"
                            ng-value="survivor.sheet.attribute_detail[token.longName].gear"
                            ng-blur="setDetail(token.longName, 'gear')"
                        />

                        <button
                            class="decrementer"
                            ng-click="incrementDetail(token.longName, 'gear', -1)"
                        >
                            -
                        </button>

                        <p>Gear</p>

                    </div> <!-- survivor_sheet_attrib_controls_number_container GEAR -->

                    <!-- end $long_name GEAR; begin TOKENS -->

                    <div class="survivor_sheet_attrib_controls_number_container">

                        <button
                            class="incrementer"
                            ng-click="incrementDetail(token.longName, 'tokens', 1)"
                        >
                            +
                        </button>

                        <input
                            id="tokens_value_{{token.longName}}_controller"
                            class="survivor_sheet_attrib_controls_number"
                            type="number"
                            onClick="this.select()"
                            ng-model="survivor.sheet.attribute_detail[token.longName].tokens"
                            ng-value="survivor.sheet.attribute_detail[token.longName].tokens"
                            ng-blur="setDetail(token.longName, 'tokens')"
                        />

                        <button
                            class="decrementer"
                            ng-click="incrementDetail(token.longName, 'tokens', -1)"
                        >
                            -
                        </button>

                        <p>Tokens</p>

                    </div> <!-- survivor_sheet_attrib_controls_number_container -->

                </div><!-- survivor_sheet_attrib_controls_number_container_container -->

            </div> <!-- survivor_sheet_attrib_controls_modal starts out hidden -->

        <button
            class="survivor_sheet_attrib_controls_token {{token.buttonClass}}"
            ng-click="showHide(control_id)"
        >
            <p class="short_name">{{token.shortName}}</p>
            <p class="attrib_value synthetic_attrib_total_{{token.longName}}">
                {{ survivor.sheet[token.longName] + survivor.sheet.attribute_detail[token.longName].gear + survivor.sheet.attribute_detail[token.longName].tokens }}
            </p>
        </button>

        </div> <!-- attrib token controls container ng-repeat -->

    </div> <!-- survivor_sheet_attrib_controls -->


    <!-- THE CONSTELLATIONS -->


    <div
        id="dragonTraitsModal"
        class="modal"
        ng-controller='theConstellationsController'
    >
        <div class="modal-content survivor_sheet_gradient">

            <span class="closeModal" onclick="closeModal('dragonTraitsModal')">×</span>

            <h3>The Constellations</h3>

            <table id="survivor_constellation_table">
                <tr><th colspan="6">&nbsp</th></tr>
                <tr>
                    <th>&nbsp</th>
                    <th>Witch</th>
                    <th>Rust</th>
                    <th>Storm</th>
                    <th>Reaper</th>
                    <th>&nbsp</th>
                </tr>
                <tr>
                    <th>Gambler</th>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('A1') == false">9 Understanding (max)</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('A1') == true" class="active">9 Understanding (max)</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('B1') == false">Destined disorder</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('B1') == true" class="active">Destined disorder</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('C1') == false">Fated Blow fighting art</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('C1') == true" class="active">Fated Blow fighting art</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('D1') == false">Pristine ability</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('D1') == true" class="active">Pristine ability</td>
                </tr>
                <tr>
                    <th>Absolute</th>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('A2') == false">Reincarnated Surname</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('A2') == true" class="active">Reincarnated Surname</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('B2') == false">Frozen Star secret fighting art</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('B2') == true" class="active">Frozen Star secret fighting art</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('C2') == false">Iridescent Hide ability</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('C2') == true" class="active">Iridescent Hide ability</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('D2') == false">Champion's Rite fighting art</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('D2') == true" class="active">Champion's Rite fighting art</td>
                </tr>
                <tr>
                    <th>Sculptor</th>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('A3') == false">Scar</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('A3') == true" class="active">Scar</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('B3') == false">Noble surname</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('B3') == true" class="active">Noble surname</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('C3') == false">Weapon Mastery</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('C3') == true" class="active">Weapon Mastery</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('D3') == false">+1 Accuracy attribute</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('D3') == true" class="active">+1 Accuracy attribute</td>
                </tr>
                <tr>
                    <th>Goblin</th>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('A4') == false">Oracle's Eye ability</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('A4') == true" class="active">Oracle's Eye ability</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('B4') == false">Unbreakable fighting art</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('B4') == true" class="active">Unbreakable fighting art</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('C4') == false">3+ Strength attribute</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('C4') == true" class="active">3+ Strength attribute</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('D4') == false">9 Courage (max)</td>
                    <td ng-if="survivor.dragon_traits.active_cells.includes('D4') == true" class="active">9 courage (max)</td>
                </tr>
                <tr><th colspan="6">&nbsp</th></tr>

            </table>
            <br />

            <div id="survivor_constellation_control_container">

                <select
                    class="survivor_sheet_constellations_picker"
                    ng-if="survivor.dragon_traits.available_constellations.length >= 1"
                    ng-model="survivor.sheet.constellation"
                    ng-options="c for c in survivor.dragon_traits.available_constellations"
                    ng-change="setConstellation(survivor.sheet.constellation)"
                    ng-selected="survivor.sheet.constellation"
                >
                    <option disabled value="">Choose a Constellation</option>
                </select>

                <button
                    ng-if="survivor.sheet.constellation != undefined"
                    ng-click="unsetConstellation()"
                >
                    Unset Constellation
                </button>
            </div>

            <br/><br/>

        </div> <!-- modal-content -->

    </div> <!-- dragonTraitsModal ng-controller -->


    <!-- SAVIOR CONTROLS -->


    <div
        ng-controller="saviorController"
        id="modalSavior" class="modal"
    >
        <div class="modal-content survivor_sheet_gradient">
            <span class="closeModal" onclick="closeModal('modalSavior')">×</span>

            <h3>Savior</h3>

            <button
                class="affinity_red"
                ng-click="setSaviorStatus('red')"
            >
                Dream of the Beast
            </button>
            <button
                class="affinity_green"
                ng-click="setSaviorStatus('green')"
            >
                Dream of the Crown
            </button>
            <button
                class="affinity_blue"
                ng-click="setSaviorStatus('blue')"
            >
                Dream of the Lantern
            </button>

            <br/>

            <button
                ng-if = "survivor.sheet.savior != false"
                ng-click = "unsetSaviorStatus()"
            >
                Unset Savior Info
            </button>

        </div> <!-- modal-content -->

    </div> <!-- modalSavior -->

    <div
        id="modalDeath" class="modal"
        ng-init="
            registerModalDiv('modalDeathButton','modalDeath');
        "
        ng-controller="controlsOfDeath"
    >
        <div class="modal-content survivor_sheet_gradient">
            <span class="closeModal" onclick="closeModal('modalDeath')">×</span>
            <h3>Controls of Death!</h3>
            <select
                class="survivor_sheet_cod_picker"
                ng-model="survivor.sheet.cause_of_death"
                ng-options="c.name as c.name disable when c.disabled for c in settlement.game_assets.causes_of_death"
                ng-change="processSelectCOD()"
                ng-selected='survivor.sheet.cause_of_death'
            >
                <option disabled value="">Choose Cause of Death</option>
            </select>

            <p id="addCustomCOD" style="display: none">
                <input
                    type="text"
                    class="custom_cod_text"
                    placeholder="Enter custom Cause of Death"
                    name="enter_cause_of_death"
                    ng-value="survivor.sheet.cause_of_death"
                    ng-model="customCOD"
                />
            </p>

            <p
                id="addCustomCOD"
                ng-if="
                    survivor.sheet.cause_of_death != undefined &&
                    settlement_cod_list.indexOf(survivor.sheet.cause_of_death) == -1
                "
            >
                <input
                    type="text"
                    class="custom_cod_text"
                    placeholder="Enter custom Cause of Death"
                    name="enter_cause_of_death"
                    ng-value="survivor.sheet.cause_of_death"
                    ng-model="customCOD"
                />
            </p>

            <div
                id="CODwarning"
                class="kd_alert control_error"
                style="display: none"
            >
                Please select or enter a Cause of Death!
            </div>

            <button
                class="kd_alert_no_exclaim red_glow"
                ng-click="submitCOD(customCOD)"
            >
                Die
            </button>

            <div ng-if="survivor.sheet.dead == true">
                <hr/>
                <button
                    class="kd_blue"
                    ng-click="resurrect()"
                >
                    Resurrect $name
                </button>
            </div>

        </div> <!-- modal-content -->
    </div> <!-- modalDeath -->


    <div
        id="modalAffinity" class="modal"
        ng-controller = "affinitiesController"
        ng-init="registerModalDiv('modalAffinityButton','modalAffinity')"
    >
        <div class="modal-content survivor_sheet_gradient">
            <span class="closeModal" onclick="closeModal('modalAffinity')">×</span>

            <h3>Survivor Affinities</h3>
            <p>Adjust permanent affinities for <b>{{survivor.sheet.name}}</b>. Changes are saved automatically.</p><hr/>

            <div class="modal_affinity_controls_container">

                <div
                    ng-repeat="a in ['red','green','blue']"
                    class="modal_affinity_control_unit"
                >
                    <div class="bulk_add_control" title="{{a}} affinity controls">
                        <button
                            type="button"
                            class="incrementer"
                            ng-click="incrementAffinity(a, 1)"
                        >
                            +
                        </button>
                        <input
                            id="{{a}}CountBox"
                            class="big_number_square"
                            type="number"
                            name="{{a}}_affinities"
                            ng-value="survivor.sheet.affinities[a]"
                            ng-model = 'affValue'
                            ng-change = "updateAffinity(this)"
                        />
                        <button
                            type="button"
                            class="decrementer"
                            ng-click="incrementAffinity(a, -1)"
                        >
                            -
                        </button>
                    </div>

                    <div class="affinity_block affinity_{{a}}">&nbsp;</div>

                    <hr class="affinity_spacer"/>

                </div> <!-- modal_affinity_control_unit REPEATS/ng-repeat-->

            </div> <!-- modal_affinity_controls_container -->
        </div> <!-- modal-content -->
    </div> <!-- modalAffinity -->

    \n""")


    survivor_sheet_rm_controls = Template("""\n
    <hr class="mobile_and_tablet"/>
    <div class="permanently_delete_survivor">
        <h3>Permanently Delete Survivor</h3>
        <form action="#" method="POST" onsubmit="return confirm('Press OK to permanently delete this survivor forever.\\r\\rThis is NOT THE SAME THING as marking it dead using controls above.\\r\\rPermanently deleting the survivor prevents anyone from viewing and/or editing this record ever again!');">
            <input type="hidden" name="remove_survivor" value="$survivor_id"/>
            <p>Use the button below to permanently remove $name. Please note that <b>this cannot be undone</b> and that any relationships between $name and other survivors will be removed.</p>
            <button class="kd_alert_no_exclaim red_glow permanently_delete">Permanently Delete Survivor</button>
        </form>
    </div>
    """)
    survivor_sheet_hit_box_controls = Template("""\n

            <!-- $hit_location [ render_hit_box_controls() ] -->

            <div class="survivor_hit_box">
                <div class="big_number_container right_border">
                    <button
                        class="incrementer"
                        onclick="stepAndSave('up','$number_input_id','survivor','$survivor_id');"
                    >
                        +
                    </button>
                    <input
                        id="$number_input_id"
                        type="number"
                        class="shield"
                        name="$hit_location"
                        value="$hit_location_value"
                        min="0"
                        onchange="updateAssetAttrib(this,'survivor','$survivor_id')"
                    />
                    <button
                        class="decrementer"
                        onclick="stepAndSave('down','$number_input_id','survivor','$survivor_id');"
                    >
                        -
                    </button>
                </div>
                <div class="hit_box_detail">
                    <input
                        id="$damage_location_heavy"
                        name="$toggle_location_damage_heavy"
                        value=" "
                        class="$dmg_heavy_checked damage_heavy_checked heavy_damage damage_box"
                        onclick="toggleDamage('$damage_location_heavy','$survivor_id');"
                        type="submit"
                    />
                    <input
                        id="$damage_location_light"
                        name="$toggle_location_damage_light"
                        onclick="toggleDamage('$damage_location_light','$survivor_id');"
                        type="submit"
                        class="$dmg_light_checked damage_light_checked damage_box"
                        value=" "
                    />
                    <h2>$hit_location</h2>
                </div> <!-- hit_box_detail -->
                <p><b>H</b>eavy Injury: Knocked Down</p>
            </div> <!-- survivor_hit_box -->

    \n""")
    partner_controls_top = '\n\t<p><span class="tiny_break">&nbsp;</span><h3 class="partner">Partner</h3><select name="partner_id" onchange="this.form.submit()">\n'
    partner_controls_none = '<option selected disabled>Select a Survivor</option>'
    partner_controls_opt = Template('<option value="$value" $selected>$name</option>')
    partner_controls_bot = '</select><span class="tiny_break"/>&nbsp;</span></p>\n\n'
    expansion_attrib_controls = Template("""\n

    <div class="expansion_attribs_container">
        <form method="POST" action="#edit_misc_attribs">
        <input type="hidden" name="modify" value="survivor" />
        <input type="hidden" name="asset_id" ng-value="survivor_id" />
        <input type="hidden" name="expansion_attribs" value="None"/> <!-- Hacks -->
        <input type="hidden" name="expansion_attribs" value="None"/> <!-- Hacks -->

        $control_items

        </form>
    </div> <!-- expansion_attribs_container -->

    <hr />

    \n""")
    expansion_attrib_item = Template("""\n

    <div class="line_item">
        <input
            onchange="this.form.submit()"
            type="checkbox" id="$item_id"
            class="kd_css_checkbox kd_radio_option"
            name="expansion_attribs"
            value="$key"
            $checked
        />
        <label
            for="$item_id"
        >
            $key
        </label>
    </div> <!-- expansion_attrib line_item -->

    \n""")
    returning_survivor_badge = Template("""\n\
    <div class="returning_survivor_badge $color_class" title="$div_title">$flag_letter</div>
    \n""")
    survivor_constellation_badge = Template("""\n\
    <div class="survivor_constellation_badge" title="Survivor Constellation">$value</div>
    \n""")
    stat_story_event_stub = Template("""\n
               <font class="kdm_font">g</font> <b>$event</b> (p.$page) occurs at $attrib_value<br/>
    """)
    survival_action_item = Template('\
        <font class="survivor_sheet_survival_action_item $f_class">$action</font><br/>\
    \n')


class settlement:

    new = """\n\
    <script type="text/javascript">
        // kill the spinner, just in case it hasn't been killed
        hideFullPageLoader();
    </script>
    <span class="tablet_and_desktop nav_bar settlement_sheet_gradient"></span>
    <span class="nav_bar_mobile mobile_only settlement_sheet_gradient"></span>
    <span class="top_nav_spacer mobile_only"> hidden </span>

    <br />

    <div
        id="create_new_asset_form_container"
        ng-controller="newSettlementController"
        ng-init="initNewSettlement('$api_url')"
    >

        <form action="#" method="POST">
            <div class="create_user_asset_block_group">
                <input type="hidden" name="new" value="settlement" />
                <input
                    type="text"
                    name="name"
                    placeholder="New Settlement Name"
                    onclick="this.select()"
                    class="new_asset_name"
                    ng-model = "settlementName"
                    autofocus
                >
            </div>

        <div class="create_user_asset_block_group">
            <h2 class="no_ul">Campaign:</h2>
            <p> Choosing an expansion campaign automatically enables expansion
            content required by that campaign and modifies the settlement timeline,
            milestones, principles, rules and Survivor Sheets. <br/><br/>
            A settlement's campaign <b>cannot be changed</b> after settlement
            creation!</p>

            <div ng-if="showLoader" class="new_settlement_loading"><img src="/media/loading_io.gif"></div>

            <div
                class="new_settlement_campaign_container"
                ng-repeat="c in new_settlement_assets.campaigns"
            >
            <input
                type="radio"
                id="{{c.handle}}"
                class="kd_css_checkbox kd_radio_option"
                name="campaign"
                value="{{c.handle}}"
                ng-checked="{{c.default}}"
            />
            <label for="{{c.handle}}">{{c.name}}
                <p ng-if="c.subtitle" class="new_settlement_asset"> {{c.subtitle}}</p>
            </label>
            </div>

        </div>  <!-- campaigns -->


        <div class="create_user_asset_block_group">
            <h2 class="no_ul">Expansions:</h2>
            <p> Enable expansion content by toggling items below. Expansion
            content may also be enabled (or disabled) later using the controls
            on the left-side navigation bar.</p>

            <div ng-if="showLoader" class="new_settlement_loading"><img src="/media/loading_io.gif"></div>

            <div
                class="new_settlement_expansions_container"
                ng-repeat="e in new_settlement_assets.expansions"
            >
            <input
                type="checkbox"
                id="{{e.handle}}"
                class="kd_css_checkbox kd_radio_option"
                name="expansions"
                value="{{e.handle}}"
            />
            <label for="{{e.handle}}">{{e.name}}
                <p ng-if="e.subtitle" class="new_settlement_asset"> {{e.subtitle}}</p>
            </label>
            </div>

        </div> <!-- expansions -->


        <div class="create_user_asset_block_group">
            <h2 class="no_ul">Survivors:</h2>
            <p>By default, new settlements are created with no survivors. Toggle options below to create the settlement with pre-made survivors. </p>

            <div ng-repeat="c in new_settlement_assets.specials">
                <input
                    type="checkbox"
                    id="{{c.handle}}_checkbox"
                    class="kd_css_checkbox kd_radio_option"
                    name="specials"
                    ng-value="c.handle"
                />
                <label
                    for="{{c.handle}}_checkbox"
                >
                    {{c.title}}
                    <p
                        class="new_settlement_asset"
                        ng-bind-html="c.desc|trustedHTML"
                    ></p>

                </label>

            </div> <!-- specials-->

            <div ng-if="showLoader" class="new_settlement_loading"><img src="/media/loading_io.gif"></div>

            <div
                class="new_settlement_survivors_container"
                ng-repeat="s in new_settlement_assets.survivors"
            >
                <input
                    id="{{s.handle}}"
                    class="kd_css_checkbox kd_radio_option"
                    type="checkbox"
                    name="survivors"
                    value="{{s.handle}}"
                />
                <label
                    for="{{s.handle}}"
                />
                    {{s.name}}
                </label>
            </div> <!-- survivors -->


        <br/><br/>

        <button
            onclick="showFullPageLoader()"
            ng-if="showLoader == false"
            class="kd_blue"
        >
                Create {{settlementName}}
        </button>

        <br/><br/><br/>

        </form>

    </div> <!-- create_new_asset_form_container -->
    \n"""
    add_innovations_form = Template("""\n
        <form action="/" method="POST" class="settlement_sheet_add_innovations_legacy_form">
            <input type="hidden" name="modify" value="settlement"/>
            <input type="hidden" name="asset_id" value="$settlement_id"/>
            $select_controls
        </form>
    """)
    storage_warning = Template(""" onclick="return confirm('Remove $item_name from Settlement Storage?');" """)
    storage_remove_button = Template("""\n\
    \t<button $confirmation id="remove_item" name="remove_item" value="$item_key" style="background-color: #$item_color; color: #$item_font_color;"> $item_key_and_count </button>
    \n""")
    storage_tag = Template('<h3 class="inventory_tag" style="color: #$color">$name</h3><hr/>')
    storage_resource_pool = Template("""\n\
    <p>Hide: $hide, Bone: $bone, Scrap: $scrap, Organ: $organ</p>
    \n""")


    # dashboard refactor
    dashboard_campaign_asset = Template("""\n
    <form method="POST" action="#">
        <input type="hidden" name="view_campaign" value="$asset_id" />
        <button class="settlement_sheet_gradient dashboard_settlement_name">
        <b class="dashboard_settlement_name">$name</b>
        <i>$campaign</i></span><br/>
        LY $ly. &ensp; Survivors: $pop &ensp;
        $players_block
        </button>
    </form>
    \n""")

    #   campaign view campaign summary
    summary = Template("""\n\n

    <script src="/media/campaignSummary.js?v=$application_version"></script>
    <div
        id = "campaign_summary_angularjs_controller_container"
        ng-init="initialize('campaignSummary', '$user_id', '$api_url','$settlement_id')"
    >
        <span class="tablet_and_desktop nav_bar campaign_summary_gradient"></span>
        <span class="nav_bar_mobile mobile_only campaign_summary_gradient"></span>
        <span class="top_nav_spacer mobile_only"> hidden </span>

        <div class="campaign_summary_headline_container">
            <h1 class="settlement_name"> %s {{settlement_sheet.name}}</h1>
            <p class="campaign_summary_campaign_type">{{settlement.game_assets.campaign.name}}</p>
            <p>Population:
                {{settlement.sheet.population}}
                ({{settlement.sheet.population_by_sex.M}}M/{{settlement.sheet.population_by_sex.F}}F)<span ng-if="settlement.sheet.death_count > 0">; 
                    {{settlement.sheet.death_count}} death<span ng-if="settlement.sheet.death_count > 1">s</span>
                </span>
            </p>
            <hr class="mobile_only"/>
            <p>Lantern Year: {{settlement.sheet.lantern_year}}, Survival Limit: {{settlement.sheet.survival_limit}}</p>
            <hr class="mobile_only"/>
        </div> <!-- campaign_summary_headline_container -->

        <div class="campaign_summary_panels_container">

            <div
                ng-if="settlement.user_assets.survivors.length == 0"
                class="kd_alert user_asset_sheet_error"
            >
                    <b>{{settlement.sheet.name}}</b> does not have any survivors!
                    Use the navigation menu controls in the upper left to add new survivors.
            </div>


            <div
                class="campaign_summary_survivors_container"
                ng-if="settlement.user_assets.survivors.length >= 0"
                ng-controller="survivorManagementController"
            >

            <h2>- Survivors - </h2>
            <p class="subtitle">Tap or click a survivor for management options.</p>

                <div
                    class="campaign_summary_survivors_group"
                    ng-repeat="group in settlement.user_assets.survivor_groups"
                    ng-if="group.survivors.length >= 1"
                    ng-init="containerID = group.handle + '_container'; group.arrow = false; "
                >

                    <h3 title="group.title_tip" ng-click="showHide(containerID); flipArrow(group)" class="clickable {{group.handle}}">
                        <span ng-if="group.arrow == true || group.arrow == undefined">
                            &#x25B2;
                        </span>
                        <span ng-if="group.arrow == false">
                            &#x25BC;
                        </span>

                        {{group.name}} ({{group.survivors.length}})
                    </h3>

                    <div id="{{containerID}}" >

                        <div
                            class="campaign_summary_survivor_container {{group.handle}}"
                            ng-repeat="s in group.survivors"
                            ng-init="initSurvivorCard(s)"
                        >
                            <button
                                class="campaign_summary_survivor {{group.handle}}"
                                ng-click="showSurvivorControls(s)"
                                ng-class="{
                                    disabled: s.meta.manageable == false,
                                    survivor_sheet_gradient: s.meta.manageable == true,
                                    dead_survivor_gradient: s.sheet.dead == true,
                                    affinity_red: s.sheet.savior == 'red',
                                    affinity_green: s.sheet.savior == 'green',
                                    affinity_blue: s.sheet.savior == 'blue',
                                }"
                            >
                                <div
                                    ng-if="s.meta.returning_survivor == true && s.sheet.dead != true"
                                    class="campaign_summary_survivor_returning_flash"
                                >
                                    Returning Survivor
                                </div>

                                <div class="avatar_and_summary">
                                    <div class="avatar">
                                        <span class="death_x" ng-if="s.sheet.dead == true">
                                            X
                                        </span>
                                        <img
                                            class="campaign_summary_avatar"
                                            ng-if="s.sheet.avatar != undefined"
                                            ng-src="/get_image?id={{s.sheet.avatar.$oid}}"
                                        />
                                        <img
                                            class="campaign_summary_avatar"
                                            ng-if="s.sheet.avatar == undefined"
                                            ng-src="/media/default_avatar_{{s.sheet.effective_sex}}.png"
                                        />
                                    </div>
                                    <div class="summary">
                                        <div
                                            class="name"
                                            ng-class="{maroon_text: s.sheet.dead == true}"
                                        >
                                            <b>{{s.sheet.name}}</b> [{{s.sheet.effective_sex}}]
                                        </div>

                                        <div class="epithets">
                                            <span ng-repeat="e in s.sheet.epithets">
                                                {{settlement.game_assets.epithets[e].name}}{{$last ? '' : ', '}}
                                            </span>
                                        </div>
                                        <div class="attr_holder">
                                            <div class="attr maroon_text" ng-if="s.sheet.dead == true">
                                                <b>Died in Lantern Year {{s.sheet.died_in}} </b>
                                            </div>
                                            <div class="attr COD maroon_text" ng-if="s.sheet.dead == true">
                                                Cause of death: {{s.sheet.cause_of_death}}
                                            </div>
                                            <div class="attr">Hunt XP: {{s.sheet.hunt_xp}}</div>
                                            <div class="attr">Survival: {{s.sheet.survival}}</div>
                                            <div class="attr" ng-class="{maroon_text: s.sheet.Insanity >= 3}">Insanity: {{s.sheet.Insanity}}</div>
                                            <div class="attr">Courage: {{s.sheet.Courage}}</div>
                                            <div class="attr">Understanding: {{s.sheet.Understanding}}</div>
                                        </div> <!-- attr_holder -->

                                    </div> <!-- summary -->
                                </div> <!-- avatar_and_summary -->

                                <div class="campaign_summary_survivor_tags_container">
                                    <!-- NOT IMPLEMENTED -->
                                </div>

                                <div
                                    ng-if="s.sheet.constellation != undefined"
                                    class="campaign_summary_survivor_constellation dragon_king"
                                >
                                    {{s.sheet.constellation}}
                                </div>

                            </button>

                            <div
                                id="{{s.sheet._id.$oid}}_modal_controls"
                                class="hidden modal survivor_controls modal-black"
                            >
                                <h3><b>{{s.sheet.name}}</b> [{{s.sheet.effective_sex}}]</h3>

                                <div class="avatar_and_stats">
                                    <img
                                        ng-src="/get_image?id={{s.sheet.avatar.$oid}}"
                                        ng-if="s.sheet.avatar != undefined"
                                    />
                                    <img
                                        ng-if="s.sheet.avatar == undefined"
                                        ng-src="/media/default_avatar_{{s.sheet.effective_sex}}.png"
                                    />

                                    <table class="stats_table">
                                        <tr><th></th><th>Base </th><th>Gear </th><th>Tok</th></tr>
                                        <tr>
                                            <td class="key">MOV:</td>
                                            <td>{{s.sheet.Movement}}</td>
                                            <td>{{s.sheet.attribute_detail.Movement.gear}}</td>
                                            <td>{{s.sheet.attribute_detail.Movement.tokens}}</td>
                                        </tr>
                                        <tr>
                                            <td class="key">ACC:</td>
                                            <td>{{s.sheet.Accuracy}}</td>
                                            <td>{{s.sheet.attribute_detail.Accuracy.gear}}</td>
                                            <td>{{s.sheet.attribute_detail.Accuracy.tokens}}</td>
                                        </tr>
                                        <tr>
                                            <td class="key">STR:</td>
                                            <td>{{s.sheet.Strength}}</td>
                                            <td>{{s.sheet.attribute_detail.Strength.gear}}</td>
                                            <td>{{s.sheet.attribute_detail.Strength.tokens}}</td>
                                        </tr>
                                        <tr>
                                            <td class="key">EVA:</td>
                                            <td>{{s.sheet.Evasion}}</td>
                                            <td>{{s.sheet.attribute_detail.Evasion.gear}}</td>
                                            <td>{{s.sheet.attribute_detail.Evasion.tokens}}</td>
                                        </tr>
                                        <tr>
                                            <td class="key">LUCK:</td>
                                            <td>{{s.sheet.Luck}}</td>
                                            <td>{{s.sheet.attribute_detail.Luck.gear}}</td>
                                            <td>{{s.sheet.attribute_detail.Luck.tokens}}</td>
                                        </tr>
                                        <tr>
                                            <td class="key">SPD:</td>
                                            <td>{{s.sheet.Speed}}</td>
                                            <td>{{s.sheet.attribute_detail.Speed.gear}}</td>
                                            <td>{{s.sheet.attribute_detail.Speed.tokens}}</td>
                                        </tr>
                                    </table>
                                </div> <!-- avatar and stats -->

                                <div class="campaign_summary_survivor_attrib_tumblers">
                                    <div class="tumbler">
                                        <button
                                            ng-click="modifySurvivorAttrib(s, 'survival', 1, settlement.sheet.survival_limit)"
                                            ng-class="{disabled: s.sheet.survival == settlement.sheet.survival_limit}"
                                        >
                                            &#9652;
                                        </button>
                                        <div class="value">{{s.sheet.survival}}</div>
                                        Survival
                                        <button
                                            ng-click="modifySurvivorAttrib(s, 'survival', -1)"
                                            ng-class="{disabled: s.sheet.survival == 0}"
                                        >
                                            &#9662;
                                        </button>
                                    </div>
                                    <div class="tumbler">
                                        <button
                                            ng-click="modifySurvivorAttrib(s, 'Insanity', 1)"
                                        >
                                            &#9652;
                                        </button>
                                        <div
                                            class="value"
                                            ng-class="{maroon_text: s.sheet.Insanity >= 3}"
                                        >
                                            {{s.sheet.Insanity}}
                                        </div>
                                        Insanity
                                        <button
                                            ng-click="modifySurvivorAttrib(s, 'Insanity', -1)"
                                            ng-class="{disabled: s.sheet.Insanity == 0}"
                                        >
                                            &#9662;
                                        </button>
                                    </div>
                                    <div class="tumbler">
                                        <button
                                            ng-click="modifySurvivorAttrib(s, 'Courage', 1, 9)"
                                            ng-class="{disabled: s.sheet.Courage == 9}"
                                        >
                                            &#9652;
                                        </button>
                                        <div class="value">{{s.sheet.Courage}}</div>
                                        Courage
                                        <button
                                            ng-click="modifySurvivorAttrib(s, 'Courage', -1)"
                                            ng-class="{disabled: s.sheet.Courage == 0}"
                                        >
                                            &#9662;
                                        </button>
                                    </div>
                                    <div class="tumbler">
                                        <button
                                            ng-click="modifySurvivorAttrib(s, 'Understanding', 1, 9)"
                                            ng-class="{disabled: s.sheet.Understanding == 9}"
                                        >
                                            &#9652;
                                        </button>
                                        <div class="value">{{s.sheet.Understanding}}</div>
                                        Understanding
                                        <button
                                            ng-click="modifySurvivorAttrib(s, 'Understanding', -1)"
                                            ng-class="{disabled: s.sheet.Understanding == 0}"
                                        >
                                            &#9662;
                                        </button>
                                    </div>
                                </div>

                                <form action="" method="POST">
                                    <input type="hidden" name="view_survivor" value="{{s.sheet._id.$oid}}" />
                                    <button
                                        class="modal_manager survivor_sheet_gradient"
                                        onclick="showFullPageLoader()"
                                        ng-click="showHide(s.sheet._id.$oid + '_modal_controls');"
                                    >
                                        Edit <b>Survivor Sheet</b>
                                    >
                                    </button>
                                </form>

                                <div
                                    ng-if="
                                        group.handle == 'available' ||
                                        group.handle == 'favorite' ||
                                        group.handle == 'departing'
                                    "
                                >
                                    <button
                                        ng-if="s.sheet.departing == true"
                                        ng-click="
                                            toggleDepartingStatus(s);
                                            showHide(s.sheet._id.$oid + '_modal_controls');
                                        "
                                        class="modal_manager departing_toggle"
                                    >   Leave <b>Departing</b> Survivors
                                    </button>
                                    <button
                                        ng-if="s.sheet.departing != true"
                                        ng-click="
                                            toggleDepartingStatus(s);
                                            showHide(s.sheet._id.$oid + '_modal_controls');
                                        "
                                        class="modal_manager departing_toggle"
                                    >   Join <b>Departing</b> Survivors
                                    </button>
                                </div> <!-- conditional -->

                                <hr>

                                <button
                                    class="modal_manager"
                                    ng-click="showHide(s.sheet._id.$oid + '_modal_controls')"
                                > Back
                                </button>

                            </div> <!-- modal controls -->


                        </div> <!-- survivor container -->

                    </div><!-- show/hide container -->

                </div> <!-- survivors_group -->

                <footer ng-repeat-end ng-init="checkManageable()"></footer>

            </div> <!-- campaign_summary_survivors_container -->

            <div class="campaign_summary_facts_box" ng-if="settlement != undefined">

                <div
                    ng-repeat="r in settlement.campaign.special_rules"
                    class="campaign_summary_special_rule"
                    style="background-color: #{{r.bg_color}}; color: #{{r.font_color}}"
                >
                    <h3>{{r.name}}</h3>
                    <span ng-bind-html="r.desc|trustedHTML"></span>
                </div>
                <div
                    ng-if="
                        user_is_settlement_admin &&
                        user.user.preferences.show_endeavor_token_controls != false
                    "
                    class="campaign_summary_small_box"
                >
                    <div
                        title="Manage settlement Endeavor tokens here! Settlement admins may use the controls at the right to increment or decrement the total number of tokens!"
                        class="campaign_summary_endeavor_controller"
                        ng-controller="endeavorController"
                    >

                        <span ng-if="settlement_sheet.endeavor_tokens >= 1">
                            <div
                                class="tokens"
                            >
                                <img
                                    ng-repeat="e in range(settlement_sheet.endeavor_tokens)"
                                    class="campaign_summary_endeavor_star"
                                    src="/media/icons/endeavor_star.png"
                                >
                            </div>
                            <div ng-if="user_is_settlement_admin" class="controls">
                                <button ng-click="rmToken()" > &#9662; </button>
                                <button ng-click="addToken()" > &#9652; </button>
                            </div>
                        </span>

                        <div
                            ng-if="settlement_sheet.endeavor_tokens <= 0"
                            ng-click="addToken()"
                            class="endeavor_controls_toggle settlement_sheet_block_group clickable"
                        >
                            <h4>- Endeavor Tokens -</h4>
                            <span>Click or tap here to manage Endeavor Tokens.</span>
                        </div>

                        <div class="endeavor_controls_clear_div"></div>

                    </div>

                </div> <!-- show_endeavor_controls -->

            <div
                class="campaign_summary_small_box"
                ng-if="settlement.sheet.lantern_research_level >= 1"
            >
                <h4 class="pulse_discoveries">- Pulse Discoveries -</h4>
                <div
                    class="pulse_discovery"
                    ng-repeat="d in settlement.game_assets.pulse_discoveries"
                    ng-if="settlement.sheet.lantern_research_level >= d.level"
                    style="background-color: {{d.bgcolor}}"
                >
                    <div class="pd_level_container">
                        <div class="pd_level">{{d.level}}</div>
                    </div>
                    <div class="pd_text">
                        <b>{{d.name}}</b>
                        <span ng-if="d.subtitle != undefined"> - {{d.subtitle}}</span>
                        <br/>
                        {{d.desc}}
                    </div>
                </div><!-- repeater -->
            </div> <!-- pulse discoveries -->

            <div class="campaign_summary_small_box endeavor_box" ng-controller='availableEndeavorsController'>
                <h4>- Available Endeavors -</h4>

                <!-- campaign-specific -->
                <div ng-if="settlement.campaign.endeavors.campaign.length >= 1">
                    <h5><b>Campaign:</b></h5>
                    <div
                        ng-repeat="e in settlement.campaign.endeavors.campaign"
                        class="campaign_summary_endeavor_container campaign_endeavor {{e.class}}"
                    >
                        <div class="endeavor_cost {{e.class}}">
                            <img ng-repeat="c in range(e.cost)" src="/media/icons/endeavor_star.png" class="endeavor_cost">
                        </div>
                        <div class="endeavor_text">
                            <b ng-if="e.name != undefined">{{e.name}}</b>
                            <span ng-if="e.name != undefined && e.desc != undefined"> - </span>
                            <span ng-bind-html="e.desc|trustedHTML"></span>
                        </div>
                    </div>
                </div>

                <!-- innovations -->
                <div
                    ng-repeat="i in settlement.campaign.endeavors.innovations"
                >
                    <h5><b>{{settlement.game_assets.innovations[i['handle']].name}}</b> ({{settlement.game_assets.innovations[i['handle']].innovation_type}}):</h5>
                    <div
                        ng-repeat="e_handle in i.endeavors"
                        ng-init="e = settlement.game_assets.endeavors[e_handle]"
                        class="campaign_summary_endeavor_container {{e.class}}"
                    >
                        <div class="endeavor_cost {{e.class}}">
                            <img ng-repeat="c in range(e.cost)" src="/media/icons/endeavor_star.png" class="endeavor_cost">
                        </div>
                        <div class="endeavor_text">
                            <b ng-if="e.name != undefined">{{e.name}}</b>
                            <span ng-if="e.name != undefined && e.desc != undefined"> - </span>
                            <span ng-bind-html="e.desc|trustedHTML"></span>
                        </div>
                        <div ng-if="e.cost_detail != undefined" class="cost_detail {{e.cost_detail_type}}_cost_detail">
                            <div ng-repeat="i in e.cost_detail">
                                {{i}}
                            </div>
                        </div>
                    </div> <!-- endeavor container -->
                </div> <!-- innovations endeavors -->

                <!-- locations -->
                <div
                    ng-repeat="l in settlement.campaign.endeavors.locations"
                >
                    <h5><b>{{settlement.game_assets.locations[l['handle']].name}}</b>:</h5>
                    <div
                        ng-repeat="e_handle in l.endeavors"
                        ng-init="e = settlement.game_assets.endeavors[e_handle]"
                        class="campaign_summary_endeavor_container {{e.class}}"
                    >
                        <div class="endeavor_cost {{e.class}}">
                            <img ng-repeat="c in range(e.cost)" src="/media/icons/endeavor_star.png" class="endeavor_cost">
                        </div>
                        <div class="endeavor_text">
                            <b ng-if="e.name != undefined">{{e.name}}</b>
                            <span ng-if="e.name != undefined && e.desc != undefined"> - </span>
                            <span ng-bind-html="e.desc|trustedHTML"></span>
                        </div>
                        <div ng-if="e.cost_detail != undefined" class="cost_detail {{e.cost_detail_type}}_cost_detail">
                            <div ng-repeat="i in e.cost_detail">
                                {{i}}
                            </div>
                        </div>
                    </div> <!-- endeavor container -->
                </div> <!-- locations endeavors -->

                <!-- survivors -->
                <div
                    ng-repeat="s in settlement.campaign.endeavors.survivors"
                >
                    <h5><b>{{s.sheet.name}} [{{s.sheet.effective_sex}}]</b>:</h5>
                    <div
                        ng-repeat="e_handle in s.sheet.endeavors"
                        ng-init="e = settlement.game_assets.endeavors[e_handle]"
                        class="campaign_summary_endeavor_container {{e.class}}"
                    >
                        <div class="endeavor_cost {{e.class}}">
                            <img ng-repeat="c in range(e.cost)" src="/media/icons/endeavor_star.png" class="endeavor_cost">
                        </div>
                        <div class="endeavor_text">
                            <b ng-if="e.name != undefined">{{e.name}}</b>
                            <span ng-if="e.name != undefined && e.desc != undefined"> - </span>
                            <span ng-bind-html="e.desc|trustedHTML"></span>
                        </div>
                        <div ng-if="e.cost_detail != undefined" class="cost_detail {{e.cost_detail_type}}_cost_detail">
                            <div ng-repeat="i in e.cost_detail">
                                {{i}}
                            </div>
                        </div>
                    </div> <!-- endeavor container -->
                </div><!-- survivor repeater -->

                <!-- storage -->
                <div
                    ng-repeat="item in settlement.campaign.endeavors.storage"
                >
                    <h5><b>{{item.name}} ({{item.type}})</b>:</h5>
                    <div
                        ng-repeat="e_handle in item.endeavors"
                        ng-init="e = settlement.game_assets.endeavors[e_handle]"
                        class="campaign_summary_endeavor_container {{e.class}}"
                    >
                        <div class="endeavor_cost {{e.class}}">
                            <img ng-repeat="c in range(e.cost)" src="/media/icons/endeavor_star.png" class="endeavor_cost">
                        </div>
                        <div class="endeavor_text">
                            <b ng-if="e.name != undefined">{{e.name}}</b>
                            <span ng-if="e.name != undefined && e.desc != undefined"> - </span>
                            <span ng-bind-html="e.desc|trustedHTML"></span>
                        </div>
                    </div> <!-- endeavor container -->
                </div> <!-- storage endeavors -->


            </div>
            <div class="campaign_summary_small_box settlement_fact" ng-if='settlement.survivor_bonuses.all.length >=1'>
                <h4>- Settlement Bonuses -</h4>
                <span
                    class="kd_checkbox_checked campaign_summary_bullet"
                    ng-repeat="p in settlement.survivor_bonuses.all"
                >
                    <b> {{p.name}}:</b>
                    <span ng-bind-html="p.desc|trustedHTML"></span>
                </span>
            </div>
            <div class="campaign_summary_small_box settlement_fact" ng-if="settlement.sheet.principles.length >= 1">
                <h4>- Principles -</h4>
                <span
                    class="kd_checkbox_checked campaign_summary_bullet"
                    ng-repeat="p in settlement_sheet.principles"
                >
                    {{settlement.game_assets.innovations[p].name}}
                </span>

            </div>
            <div class="campaign_summary_small_box settlement_fact" ng-if="settlement.sheet.innovations.length >= 1">
                <h4>- Innovations -</h4>
                <span
                    class="kd_checkbox_checked campaign_summary_bullet"
                    ng-repeat="i in settlement.sheet.innovations"
                >
                    {{settlement.game_assets.innovations[i].name}}
                </span>
            </div>

            <div class="campaign_summary_small_box settlement_fact" ng-if="settlement.sheet.locations.length >= 1">
                <h4>- Locations -</h4>
                <span
                    class="kd_checkbox_checked campaign_summary_bullet"
                    ng-repeat="l in settlement.sheet.locations"
                >
                    {{settlement.game_assets.locations[l].name}}
                </span>
            </div>

            <div class="campaign_summary_small_box settlement_fact">
                <h4>- Monsters -</h4>

                <h3 class="monster_subhead" ng-if="settlement.sheet.monster_volumes.length >= 1">
                    Monster Volumes
                </h3>
                <span
                    class="kd_checkbox_checked campaign_summary_bullet"
                    ng-repeat='v in settlement.sheet.monster_volumes'
                >
                    {{v}}
                </span>

                <h3 class="monster_subhead" ng-if="settlement.sheet.defeated_monsters.length >=1">
                    Defeated Monsters
                </h3>
                <span
                    class="kd_checkbox_checked campaign_summary_bullet"
                    ng-repeat="d in settlement.sheet.defeated_monsters track by $index"
                >
                    {{d}}
                </span>

                <h3 class="monster_subhead">Quarries </h3>
                <span class="kd_checkbox_checked campaign_summary_bullet" ng-repeat="n in settlement_sheet.quarries">
                    {{ settlement.game_assets.monsters[n].name }}
                </span>

                <h3 class="monster_subhead">Nemesis Monsters</h3>
                <span class="kd_checkbox_checked campaign_summary_bullet" ng-repeat="n in settlement_sheet.nemesis_monsters">
                    {{ settlement.game_assets.monsters[n].name }}
                </span>

            </div>
        </div> <!-- campaign_summary_facts_box -->

    <div class="campaign_summary_bottom_spacer"> </div>

</div> <!-- campaign_summary_panels_container -->



    <!--

        This is 'the fold'. The only content below here should be heavy-
        lift JS applications, modals, etc. That don't need to load or be
        visible right away on page load.

    -->


    <button
        id="departingSurvivorsModalOpener"
        class="manage_departing_survivors kd_brown"
        ng-if="departing_survivor_count > 0"
        onclick="showHide('departingSurvivorsModalContent')"
    >
        Manage {{departing_survivor_count}} <b>Departing</b> Survivors
    </button>

    <div
        id="departingSurvivorsModalContent"
        class="hidden modal modal-black"
        ng-controller="manageDepartingSurvivorsController"
    >
        <h3>Manage Departing Survivors</h3>
        <p class="modal_subtitle">Use the controls below to modify all <i>living</i>
        survivors in the <b>Departing Survivors</b> group. </p>

        <div class="departing_survivors_control">
            <div class="label_div">Survival</div>
            <div class="button_div" ng-if="hideControls==false">
                <button
                    ng-click="updateDepartingSurvivors('survival', +1)"
                > +1
                </button>
                <button
                    ng-click="updateDepartingSurvivors('survival', -1)"
                > -1
                </button>
            </div> <!-- button div -->
        </div> <!-- departing_survivors_control Survival -->

        <div class="departing_survivors_control">
            <div class="label_div">Insanity</div>
            <div class="button_div" ng-if="hideControls==false">
                <button
                    ng-click="updateDepartingSurvivors('Insanity', +1)"
                > +1
                </button>
                <button
                    ng-click="updateDepartingSurvivors('Insanity', -1)"
                > -1
                </button>
            </div> <!-- button div -->
        </div> <!-- departing_survivors_control Insanity -->

        <div class="departing_survivors_control">
            <div class="label_div">Courage</div>
            <div class="button_div" ng-if="hideControls==false">
                <button
                    ng-click="updateDepartingSurvivors('Courage', +1)"
                > +1
                </button>
                <button
                    ng-click="updateDepartingSurvivors('Courage', -1)"
                > -1
                </button>
            </div> <!-- button div -->
        </div> <!-- departing_survivors_control Insanity -->

        <div class="departing_survivors_control">
            <div class="label_div">Understanding</div>
            <div class="button_div" ng-if="hideControls==false">
                <button
                    ng-click="updateDepartingSurvivors('Understanding', +1)"
                > +1
                </button>
                <button
                    ng-click="updateDepartingSurvivors('Understanding', -1)"
                > -1
                </button>
            </div> <!-- button div -->
        </div> <!-- departing_survivors_control Understanding -->

        <div class="departing_survivors_control">
            <div class="label_div">Brain Event Damage</div>
            <div class="button_div" ng-if="hideControls==false">
                <button
                    ng-click="updateDepartingSurvivors('brain_event_damage', 1)"
                    class="maroon_text"
                > 1
                </button>
            </div> <!-- button div -->
        </div> <!-- departing_survivors_control brain event damage -->


        <h3>Monster</h3>
        <p class="modal_subtitle">Use the controls below to select the monster
        facing the survivors in the upcoming Showdown. </p>

        <div class="current_hunt_container">
            <select
                id="set_departing_survivors_current_quarry"
                class="hunting_party_current_quarry"
                name="current_quarry"
                ng-model="current_quarry"
                ng-change="saveCurrentQuarry()"
                ng-options="d for d in settlement.game_assets.defeated_monsters"
            >
                <option disabled selected value="">Choose Monster</option>
            </select>
        </div>

        <div class="showdown_type">
            <span ng-if="settlement.sheet != undefined" ng-init="initShowdownControls()"></span>
            <h3
                ng-click="
                    showHide('showdownOptions');
                    flipShowdownArrow();
                "
            >
                Showdown
                <span class="showdown_arrow" ng-if="scratch.showdown_arrow == true">
                    &#x25BC;
                </span>
                <span class="showdown_arrow" ng-if="scratch.showdown_arrow == false">
                    &#x25B2;
                </span>
            </h3>
            <p class="modal_subtitle">Use the buttons below to select the type of
            showdown.</p>
            <div id="showdownOptions" class="options" ng-class="{hidden: settlement.sheet.showdown_type != undefined}">
                <button
                    class="departing_survivors_mgmt kd_brown"
                    ng-click="setShowdownType('normal'); showHide('showdownOptions')"
                >
                    <b>Showdown</b>
		</button>
                <button
                    class="departing_survivors_mgmt kd_special_showdown"
                    ng-click="setShowdownType('special'); showHide('showdownOptions')"
                >
                    <b>Special Showdown</b>
                </button>
            </div>
        </div>

        <div ng-if="settlement.sheet.showdown_type != undefined">
            <h3 ng-if="settlement.sheet.showdown_type == 'normal'">Return Survivors from Showdown</h3>
            <p class="modal_subtitle" ng-if="settlement.sheet.showdown_type == 'normal'">
                Use the buttons below to return <b>Departing</b> Survivors to
                <b>{{settlement.sheet.name}}</b>. This automatically marks living
                survivors as <b>Returning Survivors</b> and removes armor points,
                attribute modifiers and damage. Settlement <b>Endeavor Tokens</b>
                will also be automatically udpated.<br/>
            </p>
            <h3 ng-if="settlement.sheet.showdown_type == 'special'">Heal Survivors</h3>
            <p class="modal_subtitle" ng-if="settlement.sheet.showdown_type == 'special'">
                Use the buttons below to heal <b>Departing</b> Survivors and
                remove them from the <b>Departing Survivors</b> group. Healing
                survivors automatically removes armor points, attribute
                modifiers and damage.<br/>
            </p>

            <button
                class="kd_blue departing_survivors_mgmt"
                ng-click="returnDepartingSurvivors('victory')"
                onclick="showHide('departingSurvivorsModalContent')"
            >
                Victorious!
            </button>
            <button
                class="kd_alert_no_exclaim departing_survivors_mgmt"
                ng-click="returnDepartingSurvivors('defeat')"
                onclick="showHide('departingSurvivorsModalContent')"
            >
                Defeated...
            </button>
        </div>

        <hr>

        <button
            class="departing_survivors_mgmt"
            onclick="showHide('departingSurvivorsModalContent')"
        >
            <b>Back</b>
        </button>
    </div> <!-- modalDepartingSurvivors whole deal-->


        <!-- SURVIVOR SEARCH -->


    <input
        id="survivorSearchModalOpener"
        class="survivor_search"
        placeholder="Search Living Survivors"
        ng-model="searchText"
    </input>

    <div
        id="survivorSearchModalContent"
        class="survivor_search_modal_container modal"
    >
        <div
            class="survivor_search_modal_content survivor_sheet_gradient"
            ng-controller = "survivorSearchController"
            ng-init = "registerModalDiv('survivorSearchModalOpener','survivorSearchModalContent');"
        >

            <div id="searchTextResults" class="survivor_search_results_buttons">

                <form
                    method="POST" action="/"
                    ng-repeat="s in settlement.user_assets.survivors | filter:searchText "
                >
                    <input type="hidden" name="view_survivor" value="{{s.sheet._id.$oid}}" />
                    <button
                        class="survivor_search_button kd_lantern"
                        ng-class="{disabled : userCanManage(s) == false}"
                        ng-if="s.dead == undefined && s.retired == undefined"
                    >
                      <p class="survivor_name">{{s.sheet.name}} [{{s.sheet.effective_sex}}]</p>
                      <div class="survivor_assets"><b>Hunt XP:</b> {{s.sheet.hunt_xp}} <b>Courage:</b> {{s.sheet.Courage}} <b>Understanding:</b> {{s.sheet.Understanding }}</div>
                      <div class="survivor_assets">
                        <b>MOV</b> {{s.sheet.Movement}} |
                        <b>ACC</b> {{s.sheet.Accuracy}} |
                        <b>STR</b> {{s.sheet.Strength}} |
                        <b>EVA</b> {{s.sheet.Evasion}} |
                        <b>LUCK</b> {{s.sheet.Luck}} |
                        <b>SPD</b> {{s.sheet.Speed}}
                      </div>

                      <div
                          ng-if="s.sheet.epithets.length >= 1"
                          class="survivor_assets"
                      >
                        <b>Epithets:</b> <span ng-repeat="e in s.sheet.epithets">
                            {{settlement.game_assets.epithets[e].name}}{{$last ? '' : ', '}}
                        </span>
                      </div>
                      <div
                          ng-if="s.sheet.fighting_arts.length >= 1"
                          class="survivor_assets"
                      >
                        <b>Fighting Arts:</b> <span ng-repeat="e in s.sheet.fighting_arts">
                            {{settlement.game_assets.fighting_arts[e].name}}{{$last ? '' : ', '}}
                        </span>
                      </div>
                      <div
                          ng-if="s.sheet.disorders.length >= 1"
                          class="survivor_assets"
                      >
                        <b>Disorders:</b> <span ng-repeat="e in s.sheet.disorders">
                            {{settlement.game_assets.disorders[e].name}}{{$last ? '' : ', '}}
                        </span>
                      </div>
                      <div
                          ng-if="s.sheet.abilities_and_impairments.length >= 1"
                          class="survivor_assets"
                      >
                        <b>Abilities & Impairments:</b> <span ng-repeat="e in s.sheet.abilities_and_impairments">
                            {{settlement.game_assets.abilities_and_impairments[e].name}}{{$last ? '' : ', '}}
                        </span>
                      </div>

                      <div ng-if="s.notes.length >= 1" class="survivor_assets"><b>Notes:</b>
                        <span ng-repeat="n in s.notes"> {{n.note}} </span>
                      </div>
                      <div ng-if="s.sheet.sotf_reroll" class="survivor_assets"><b>Once per lifetime SotF re-roll:</b> used.</div>
                    </button>
                </form>
            </div>

        <hr/>
        <span class="survivor_search_retired_survivors_warning">Retired survivors are not included in these results!</span>
        <button
            class="kd_blue close_modal"
            onclick="closeModal('survivorSearchModalContent')"
        >
        Close Search Window
        </button>

        </div> <!-- survivor_search_modal_content -->

    </div> <!-- survivorSearch -->

</div> <!-- campaign_summary methods -->

    \n""" % dashboard.campaign_flash)

    form = Template("""\n\

        <script src="/media/settlementSheet.js?v=$application_version"></script>

        <div
            id = "settlement_sheet_angularjs_controller_container"
            ng-init="initialize('settlementSheet', '$user_id', '$api_url','$settlement_id')"
            ng-controller="settlementSheetController"
        >

        <span class="tablet_and_desktop nav_bar settlement_sheet_gradient"></span>
        <span class="nav_bar_mobile mobile_only settlement_sheet_gradient"></span>
        <div class="top_nav_spacer"> hidden </div>

        <div id="asset_management_left_pane" ng-if="settlement != undefined">

            <input
                name="name"
                id="settlementName"
                class="settlement_sheet_settlement_name settlement_name"
                type="text"
                ng-value="settlement.sheet.name"
                ng-model="scratch.newSettlementName"
                ng-placeholder="Settlement Name"
                ng-blur="setSettlementName()"
                onclick="this.select()"
            />

            <p
                id="campaign_type"
                class="settlement_sheet_campaign_type"
                title="Campaign type may not be changed after a settlement is created!"
            >
                {{settlement.game_assets.campaign.name}}
            </p>


        <h1 ng-if="settlement_sheet.abandoned"class="alert">ABANDONED</h1>

        <div class="settlement_sheet_tumblers_container">
            <div class="settlement_form_wide_box">
                <div class="big_number_container left_margin">
                    <button
                        class="incrementer"
                        ng-click="incrementAttrib('survival_limit',1)"
                    >
                        &#9652;
                    </button>
                    <input
                        id="survivalLimitBox"
                        class="big_number_square"
                        type="number"
                        name="survival_limit"
                        ng-value="settlement.sheet.survival_limit"
                        ng-model="settlement.sheet.survival_limit"
                        ng-blur="setAttrib('survival_limit', settlement.sheet.survival_limit)"
                        min="{{settlement.sheet.minimum_survival_limit}}"
                    />
                    <button
                        class="decrementer"
                        ng-click="incrementAttrib('survival_limit',-1)"
                    >
                        &#9662;
                    </button>
                </div>

                <div class="big_number_caption">
                    <div class="help-tip">
                        Survival Limit
                        <p> The minimum Survival Limit for <b>{{settlement.sheet.name}}</b>, based on settlement innovations and principles, is <b>{{settlement.sheet.minimum_survival_limit}}</b>.
                            <span ng-if="settlement.sheet.enforce_survival_limit == true">
                                The settlement Survival Limit of <b>{{settlement.sheet.survival_limit}}</b> is enforced on the Survivor Sheet.
                            </span>
                            <span ng-if="settlement.sheet.enforce_survival_limit == false">
                                Due to expansion or campaign rules, the settlement Survival Limit of <b>{{settlement.sheet.survival_limit}}</b> is <u>not</u> enforced on the Survivor Sheet!
                            </span>
                        </p>
                    </div>
                </div>

            </div><!-- settlement_form_wide_box -->

            <br class="mobile_only"/>
            <hr class="mobile_only"/>

            <div class="settlement_form_wide_box">
                <div class="big_number_container left_margin">
                    <button
                        class="incrementer"
                        ng-click="incrementAttrib('population',1)"
                    >
                        &#9652;
                    </button>
                    <input
                        id="populationBox"
                        class="big_number_square"
                        type="number" name="population"
                        ng-value="settlement.sheet.population"
                        ng-model="settlement.sheet.population"
                        ng-blur="setAttrib('population', settlement.sheet.population)"
                        min="{{Number(settlement.sheet.minimum_population)}}"
                    />
                    <button
                        class="decrementer"
                        ng-click="incrementAttrib('population',-1)"
                    >
                        &#9662;
                    </button>
                </div>
                <div class="big_number_caption">
                    <div class="help-tip">
                        Poulation
                        <p> The minimum Population for <b>{{settlement.sheet.name}}</b>, based on the total number of living survivors in the settlement, is <b>{{settlement.sheet.minimum_population}}</b>.
                        </p>
                    </div>
                </div>
            </div> <!-- settlement_form_wide_box -->

            <br class="mobile_only"/>
            <hr class="mobile_only"/>

            <div class="settlement_form_wide_box">
                <div class="big_number_container left_margin">
                    <button
                        class="decrementer"
                        ng-click="incrementAttrib('death_count',1)"
                    >
                        &#9652;
                    </button>
                    <input
                        id="deathCountBox"
                        class="big_number_square"
                        type="number"
                        name="death_count"
                        ng-value="settlement.sheet.death_count"
                        ng-model="settlement.sheet.death_count"
                        ng-blur="setAttrib('death_count', settlement.sheet.death_count)"
                        min="{{Number(settlement.sheet.minimum_death_count)}}"
                    />
                    <button
                        class="decrementer"
                        ng-click="incrementAttrib('death_count',-1)"
                    >
                        &#9662;
                    </button>
                </div>
                <div class="big_number_caption">
                    <div class="help-tip">
                        Death Count
                        <p> The minimum Death Count for <b>{{settlement.sheet.name}}</b>, based on the total number of dead survivors in the settlement, is <b>{{settlement.sheet.minimum_death_count}}</b>.
                        </p>
                    </div>
                </div>
            </div> <!-- settlement_form_wide_box -->
        </div> <!-- settlement_sheet_tumblers_container -->


        <hr class="invisible">



            <!-- STORAGE CONTROLS START HERE -->



        <div
            class="settlement_sheet_block_group settlement_storage"
            ng-controller="storageController"
        >
            <h2 class="clickable" ng-click="showHide('editStorage')">Storage</h2>
            <p class="clickable" ng-click="showHide('editStorage')">Gear & Resources may be stored without limit. <b>Tap or click here to edit settlement storage.</b></p>

            <div id="editStorage" class="hidden modal storage_modal">
                    <div
                        class="storage_modal_storage_type"
                        ng-repeat="s_type in settlementStorage"
                    >
                        <h3>{{s_type.name}} Storage</h3>

                        <div
                            ng-repeat="loc in s_type.locations"
                            ng-init="loc.arrow=false"
                            class="storage_modal_storage_location"
                        >
                            <h4
                                class="clickable"
                                ng-click="showHide(loc.handle + '_container'); flipArrow(loc)"
                            >
                                {{loc.name}} <span class="metrophobic"></span>
                                <span ng-if="loc.arrow == false" class="arrow">
                                    &#x25BC;
                                </span>
                                <span ng-if="loc.arrow == true" class="arrow">
                                    &#x25B2;
                                </span>
                            </h4>
                            <div class="hidden" id="{{loc.handle}}_container"> <!-- show hide -->
                                <div
                                    class="inventory_row" ng-repeat="asset in loc.collection"
                                    ng-init="detailId = asset.handle + '_detail'; asset.flippers=false"
                                >
                                    <div
                                        class="inventory_row_item_controls clickable"
                                        ng-click="showHide(detailId); toggleFlippers(asset)"
                                    >
                                        <span class="name">
                                            {{asset.name}}
                                        </span>
                                        <span class="quantity">
                                            {{asset.quantity}}
                                        </span>
                                    </div> <!-- controls -->
                                    <div class="flippers" ng-if="asset.flippers">
                                        <button ng-click="setStorage(asset, 1)"> + </button>
                                        <button ng-click="setStorage(asset, -1)"> - </button>
                                    </div>
                                    <div id="{{detailId}}" class="hidden inventory_row_detail">
                                        <div class="rules" ng-if="asset.rules.length >= 1">
                                            &nbsp; <span ng-repeat="k in asset.rules">
                                                <b>{{k}}</b>{{$last ? '' : ', '}}
                                            </span>
                                        </div>
                                        &nbsp; <span ng-repeat="k in asset.keywords">{{k}}{{$last ? '' : ', '}}</span><br/>
                                        <span ng-bind-html="asset.desc|trustedHTML"></span>
                                    </div>
                                </div>
                            </div>

                        </div> <!-- storage_location -->

                    </div> <!-- storage_type -->

                <div class="button_spacer"></div>
                <button
                    class="kd_blue close_storage"
                    ng-click="showHide('editStorage'); loadStorage();"
                >
                    Save Changes and Return
                </button>
            </div> <!-- storage_modal container -->

            <div id="storageSpinner" class="hidden storage_loading_spinner">
                <img src="/media/loading_io.gif"><br/>
                Loading storage...
            </div>
            <div
                class="settlement_storage_type_container"
                ng-repeat="s_type in settlementStorage"
            >
                <h3 ng-if="s_type.total >= 1">
                    {{s_type.name}} Storage
                </h3>
                <div
                    class="settlement_storage_location"
                    ng-repeat="loc in s_type.locations"
                    ng-if="loc.inventory.length >= 1"
                    ng-init="loc.arrow = false"
                >
                    <h4
                        class="clickable"
                        ng-click="showHide(loc.handle + '_digest_container'); flipArrow(loc)"
                    >
                        {{loc.name}} ({{loc.inventory.length}})
                        <span ng-if="loc.arrow == false" class="arrow">
                            &#x25BC;
                        </span>
                        <span ng-if="loc.arrow == true" class="arrow">
                            &#x25B2;
                        </span>
                    </h4>
                    <div class="hidden" id="{{loc.handle}}_digest_container"> <!-- show hide -->
                        <div
                            class="settlement_storage_inventory_container"
                        >
                            <div
                                class="inventory_repeater clickable"
                                ng-repeat="t in loc.digest"
                                ng-init="detailId = t.handle + '_digest_detail'"
                                style="background-color: #{{loc.bgcolor}}; color: #{{loc.color}}"
                                ng-click="showHide(detailId)"
                            >
                                {{t.name}}
                                <span ng-if="t.count > 1">x {{t.count}}</span>
                                <div id="{{detailId}}" class="hidden inventory_repeater_detail">
                                    <div class="rules" ng-if="t.rules.length >= 1">
                                        &nbsp; <span ng-repeat="k in t.rules">
                                            <b>{{k}}</b>{{$last ? '' : ', '}}
                                        </span>
                                    </div>
                                    &nbsp; <span ng-repeat="k in t.keywords">{{k}}{{$last ? '' : ', '}}</span><br/>
                                    <span ng-bind-html="t.desc|trustedHTML"></span>
                                </div>
                            </div> <!-- inventory repeater, click to remove -->
                        </div> <!-- container flex -->
                    </div> <!-- showhide -->
                </div><!-- storage location container-->
            </div> <!-- storage type container, e.g. gear/resources-->



        </div> <!-- settlement_sheet_block_group for storage -->



    </div> <!-- asset_management_left_pane -->


    <div id="asset_management_middle_pane" ng-if="settlement != undefined">


                    <!-- LOCATIONS - ANGULARJS CONTROLS -->


        <a id="edit_locations" class="mobile_only"><a/>

        <div
            class="settlement_sheet_block_group"
            ng-if="settlement.sheet.innovations.indexOf('sculpture') != -1"
            ng-controller="inspirationalStatueController"
            title="Use these controls to manage your settlement's Inspirational Statue!"
        >
            <h2>Inspirational Statue</h2>
            <p>A settlement can only have one Inspirational Statue.</p>

            <div class="line_item">
                <span class="empty_bullet" ng-if="settlement.sheet.inspirational_statue == undefined"/></span>
                <span class="bullet" ng-if="settlement.sheet.inspirational_statue != undefined"/></span>
                <select
                    ng-model="settlement.sheet.inspirational_statue"
                    ng-options="
                        fa_handle as settlement.game_assets.fighting_arts[fa_handle].name for fa_handle in settlement.game_assets.inspirational_statue_options
                    "
                    ng-change="setInspirationalStatue()"
                    ng-selected="settlement.sheet.inspirational_statue"
                >
                    <option disabled value="">Select a Fighting Art</option>
                </select>
            </div> <!-- line_item -->

        </div>

        <div
            class="settlement_sheet_block_group"
            ng-controller="locationsController"
            title="Click or tap an item to remove it from this list."
        >

            <h2>Settlement Locations</h2>
            <p>Locations in your settlement.</p>
            <hr class="invisible"/> <!-- TK this is pretty low rent -->
            <div
                class="line_item location_container"
                ng-repeat="loc in settlement.sheet.locations"
                ng-init="locationLevel = settlement.sheet.location_levels[loc]"
            >
                <span class="bullet"></span>
                <span
                    class="item"
                    ng-click="rmLocation($index, loc)"
                >
                    {{settlement.game_assets.locations[loc].name}}
                </span>
                <span ng-if="settlement.sheet.location_levels[loc] != undefined" class="location_lvl_select">
                    <select
                        class="location_level"
                        ng-model="locationLevel"
                        ng-options="locationLevel as 'Lvl. '+ locationLevel for locationLevel in [1,2,3]"
                        ng-change="setLocationLevel(loc, locationLevel)"
                        ng-selected="locationLevel"
                    >
                    </select>
                </span> <!-- optional levels controls -->

            </div> <!-- line_item location_container: list/rm locations -->


            <div class="line_item">
                <span class="empty_bullet" /></span>
                <select
                    name="add_location"
                    ng_model="newLocation"
                    ng_change="addLocation()"
                    ng-options="loc.handle as loc.name for loc in locationOptions"
                >
                    <option value="" disabled selected>Add Location</option>
                </select>
            </div>

        </div> <!-- settlement_sheet_block_group locations controller-->




                    <!-- INNOVATIONS - ANGULARJS CONTROLS -->

        <a id="edit_innovations" class="mobile_only"/></a>


        <div
            class="settlement_sheet_block_group"
            ng-controller="innovationsController"
            title="Click or tap on an item to remove it from this list."
        >

            <h2>Innovations</h2>
            <p>The settlement's innovations (including weapon masteries).</p>

            <hr class="invisible"/> <!-- TK why is this still here? need to fix -->

            <div
                class="line_item location_container"
                ng-repeat="i in settlement.sheet.innovations"
                ng-init="innovationLevel = settlement.sheet.innovation_levels[i]"
            >
                <span class="bullet"></span>
                <span
                    class="item"
                    ng-click="rmInnovation($index,i)"
                >
                    {{settlement.game_assets.innovations[i].name}}
                </span>
                <span ng-if="settlement.sheet.innovation_levels[i] != undefined" class="location_lvl_select">
                    <select
                        class="location_level"
                        ng-model="innovationLevel"
                        ng-options="innovationLevel as 'Lvl. '+ innovationLevel for innovationLevel in [1,2,3]"
                        ng-change="setInnovationLevel(i,innovationLevel)"
                        ng-selected="innovationLevel"
                    >
                    </select>
                </span> <!-- optional levels controls -->
            </div>

            <div class="line_item">
                <span class="empty_bullet" /></span>
                <select
                    name="add_innovation"
                    ng_model="newInnovation"
                    ng_change="addInnovation()"
                    ng-options="i.handle as i.name for i in innovationOptions"
                >
                    <option value="" disabled selected>Add Innovation</option>
                </select>
            </div>

            <div
                id="innovationDeckContainerdiv"
                class="innovation_deck"
                title="The current innovation deck for {{settlement.sheet.name}}. Tap or click to refresh!"
                ng-if="settlement.sheet.innovations.length != 0"
                ng-init="setInnovationDeck()"
                ng-click="setInnovationDeck()"
            >
                <h3> - Innovation Deck - </h3>
                <img id="innovationDeckSpinner" class="innovation_deck_spinner" src="/media/loading_io.gif">
                <ul class="asset_deck">
                    <li ng-repeat="i in innovation_deck"> {{i}} </li>
                </ul>
            </div>


        </div> <!-- settlement_sheet_block_group innovations-->

        <div
            class="settlement_sheet_block_group"
            ng-controller="lanternResearchController"
            ng-if="settlement.sheet.locations.indexOf('exhausted_lantern_hoard') != -1"
        >

            <h2>Lantern Research Level</h2>

            <div class="lantern_research_level">
                <div class="big_number_container">
                    <button
                        class="incrementer"
                        ng-click="incrementLanternResearch(1)"
                    >
                        &#9652;
                    </button>
                    <input
                        id="lanternResearchBox"
                        class="big_number_square"
                        type="number" name="population"
                        ng-value="settlement.sheet.lantern_research_level"
                        ng-model="settlement.sheet.lantern_research_level"
                        ng-blur="setLanternResearch()"
                        min="0"
                        max="5"
                    />
                    <button
                        class="decrementer"
                        ng-click="incrementLanternResearch(-1)"
                    >
                        &#9662;
                    </button>
                </div> <!-- big_number_container -->
                <div class="desc_text">
                    <p><b>Once per lantern year, spend 2 x Bone, 2 x hide, 2 x organ to research.</b><br/>If you do, gain the next level of Lantern Research.</p>
                    <p>Corresponding <b>Pulse Discoveries</b> are displayed on the Campaign Summary view.</p>
                </div> <!-- desc_text -->

            </div><!-- big_number_container -->

        </div> <!-- lantern research level -->

        <div
            class="settlement_sheet_block_group"
            ng-controller="monsterVolumesController"
            ng-if="settlement.sheet.innovations.indexOf('records') != -1"
            title="Click or tap on an item to remove it from this list."
        >

            <h2>Monster Volumes</h2>
            <p>There can be up to 3 volumes for each monster.</p>

            <div
                class="line_item location_container"
                ng-repeat="v in settlement.sheet.monster_volumes"
            >
                <span class="bullet"></span>
                <span
                    class="item"
                    ng-click="rmMonsterVolume($index, v)"
                >
                    {{v}}
                </span>
            </div> <!-- line_item -->

            <div class="line_item">
                <span class="empty_bullet"></span>
                <select
                    ng-model="scratch.monster_volume"
                    ng-options="m_string for m_string in settlement.game_assets.monster_volumes_options"
                    ng-change="addMonsterVolume()"
                >
                    <option disabled value="">Add a Monster Volume</option>
                </select>
            </div> <!-- line_item -->

        </div>


    </div> <!-- asset_management_left_pane -->



    <!-- END OF LEFT PANE -->



    <div id="asset_management_right_pane" ng-if="settlement != undefined">

        <a id="edit_principles" class="mobile_only"></a>

        <div
            class="settlement_sheet_block_group"
            ng-controller="principlesController"
        >
            <h2>Principles</h2>
            <p>The settlement's established principles.</p>

            <div
                ng-repeat="p in settlement.game_assets.principles_options"
                class="settlement_sheet_principle_container"
            >
                <div
                    id="{{p.name}} principle"
                    class="principles_container"
                >

                    <div class="settlement_sheet_principle_name">
                        {{p.name}}
                    </div>

                    <div
                        class="principle_option"
                        ng-repeat="o in p.options"
                    >
                        <input
                            type="radio"
                            class="kd_css_checkbox kd_radio"
                            id="{{o.input_id}}"
                            name="{{p.form_handle}}"
                            value="{{o.name}}"
                            ng-checked="o.checked"
                            ng-click="set(p.handle,o.handle)"
                        >

                        <label
                            id="{{o.input_id}}Label"
                            for="{{o.input_id}}"
                        >
                            {{ o.name }}
                        </label>

                    </div> <!-- principle_option repeater-->

                </div> <!-- principles_container -->

            </div> <!-- settlement_sheet_principle_container -->

            <br/>
            <div class="unset_principle_container">
                <span class="empty_bullet rm_bullet"></span>
                <select
                    ng-model="unset"
                    ng-change="unset_principle();"
                    ng-options="p.handle as p.name for p in settlement.game_assets.principles_options"
                >
                    <option disabled value="">Unset Principle</option>
                </select>
            </div> <!-- unset_principle_container -->

        </div> <!-- principle block group -->


                       <!-- MILESTONES -->

        <a id="edit_milestones" class="mobile_only"/></a>

        <div class="settlement_sheet_block_group">
            <h2>Milestone Story Events</h2>
            <p>Trigger these story events when milestone condition is met.</p>

            <div ng-repeat="m in settlement.game_assets.milestones_options" class="milestone_content_container">
                <input
                    id="{{m.handle}}"
                    class="kd_css_checkbox kd_radio_option"
                    type="checkbox"
                    name="toggle_milestone"
                    value="{{m.name}}"
                    onchange="updateAssetAttrib(this, 'settlement', '$settlement_id');"
                    ng-checked="hasattr(settlement_sheet.milestone_story_events, m.name) "/>
                </input>
                <label
                    for="{{m.handle}}"
                    class="settlement_sheet_milestone_container"
                >
                    {{m.name}}
                    <span class="milestone_story_event">
                        <font class="kdm_font">g</font> <b>{{m.story_event}}</b>
                        <span class="milestone_story_reference">
                            (p.{{settlement.game_assets.events[m.story_event_handle].page}})
                        </span>
                    </span>
                </label>
            </div> <!-- milestone div -->

        </div> <!-- block_group for milestones -->




                    <!-- QUARRIES - HAS ITS OWN FORM-->

        <a id="edit_quarries"/>

        <div class="settlement_sheet_block_group" title="Click or tap an item to remove it from this list.">

            <h2>Quarries</h2>
            <p>The monsters your settlement can select to hunt.</p>

            <div>
                <div
                    class="line_item location_container"
                    ng-controller="quarriesController"
                    ng-repeat="q in settlement_sheet.quarries"
                >
                    <div> <!-- span holder -->
                        <span class="bullet"></span>
                        <span
                            class="item"
                            ng-click="removeQuarry($index, q)"
                        >
                            {{settlement.game_assets.monsters[q].name}}
                        </span>
                    </div>
                </div>
            </div>

            <div class="line_item">
                <span class="empty_bullet" /></span>
                <select
                    ng-controller="quarriesController"
                    ng-model="addQuarryMonster"
                    ng-options="q.handle as q.name for q in settlement.game_assets.quarry_options"
                    ng-change="addQuarry($index)"
                >
                    <option selected disabled value="">Add Quarry Monster</option>
                </select>
            </div> <!-- line_item -->

        </div> <!-- settlement_Sheet_block_group quarry controls-->


                    <!-- NEMESIS MONSTERS -->

        <a id="edit_nemeses"/>

        <div
            class="settlement_sheet_block_group"
            ng-controller="nemesisEncountersController"
            title="Click or tap an item to remove it from this list."
        >
            <h2><img class="icon" src="media/icons/nemesis_encounter_event.jpg"/> Nemesis Monsters</h2>
            <p>The available nemesis encounter monsters.</p>

            <div
                class="settlement_sheet_nemesis_line_item"
                ng-repeat="n in settlement_sheet.nemesis_monsters"
            >
                <span class="bullet"></span>
                <span class="item" ng-click="rmNemesis($index,n)">
                    {{settlement.game_assets.monsters[n].name}}
                </span>
                <span class="nemesis_levels">
                    <div
                        class="nemesis_level_toggle_container"
                        ng-repeat="l in range(settlement.game_assets.monsters[n].levels, 'increment')"
                    >
                        <input
                            id="{{n + '_lvl_' + l}}"
                            type="checkbox"
                            class="kd_css_checkbox"
                            ng-model="nemesisLvlToggleValue"
                            ng-checked="arrayContains(l,settlement_sheet.nemesis_encounters[n])"
                        />
                        <label
                            class="settlement_sheet_nemesis_lvl_label"
                            for="{{n + '_lvl_' + l}}"
                            id="{{n+'_lvl_'+l}}_label"
                            ng-click="toggleNemesisLevel(n,l,$event)"
                        >
                            Lvl {{l}}
                        </label>
                    </div> <!-- nemesis_level_toggle_container -->
                </span>
            </div>

            <span class="empty_bullet"></span>
            <select
                ng-model="addNemesisMonster"
                ng-options="n.handle as n.name for n in settlement.game_assets.nemesis_options"
                ng-change="addNemesis()"
            >
                <option selected disabled value="">Add Nemesis Monster</option>
            </select>

        </div> <!-- Nemesis block group/controller -->



                    <!-- DEFEATED MONSTERS -->



        <a id="edit_defeated_monsters"/>

        <div class="settlement_sheet_block_group" ng-controller="defeatedMonstersController" title="Click or tap an item to remove it from this list.">
        <h2>Defeated Monsters</h2>
        <p>A list of defeated monsters and their level.</p>

        <div
            class="line_item defeated_monsters_container"
            ng-repeat="x in settlement_sheet.defeated_monsters track by $index"
        >
            <div> <!-- span holder -->
                <span class="bullet"></span>
                <span class="item" ng-click="rmDefeatedMonster($index, x)">
                    {{x}}
                </span>
            </div>
        </div>

        <div class="line_item">
            <span class="empty_bullet" /></span>
            <select
                ng-model="dMonst"
                ng-change="addDefeatedMonster()"
                ng-options="d as d for d in settlement.game_assets.defeated_monsters ">
            >
                <option selected disabled value="">Add Defeated Monster</option>
            </select>
        </div> <!-- line_item -->

    </div>

    <hr class="mobile_only"/>

        <a id="edit_lost_settlements" class="mobile_only"></a>


                    <!-- LOST SETTLEMENTS ANGULARJS app -->


        <div
            class="lost_settlements_app_container"
            ng-controller="lostSettlementsController"
        >
        <div
            onclick="showHide('lostSettlementsTooltip'); showHide('lostSettlementsControls')"
            class="settlement_sheet_block_group lost_settlements"
        >
            <h2>Lost Settlements</h2>
            <p>Click or tap to show/hide controls.</p>
            <p style="display: none" id="lostSettlementsTooltip">
                <span class="metrophobic">See </span>
                <font class="kdm_font">g</font> <b>Game Over</b>
                <span class="metrophobic"> on p.179</span>:<br/><br/>
                    &ensp;
                        <span class="lost_settlement lost_settlement_checked"></span>
                        1. Left Overs
                    <br/>
                    &ensp;
                        <span class="lost_settlement lost_settlement_checked"></span>
                        <span class="lost_settlement lost_settlement_checked"></span>
                        2. Those Before Us
                    <br/>
                    &ensp;
                        <span class="lost_settlement lost_settlement_checked"></span>
                        <span class="lost_settlement lost_settlement_checked"></span>
                        <span class="lost_settlement lost_settlement_checked"></span>
                        3. Ocular Parasites
                    <br/>
                    &ensp;
                        <span class="lost_settlement lost_settlement_checked"></span>
                        <span class="lost_settlement lost_settlement_checked"></span>
                        <span class="lost_settlement lost_settlement_checked"></span>
                        <span class="lost_settlement lost_settlement_checked"></span>
                        4. Rainy Season
                    <br/>
            </p>

            <div
                class="lost_settlement_squares"
            >

            <span
                class="lost_settlement_box_socket"
                ng-repeat="x in lost"
            >
                <span id="box_{{x.id_num}}" class="lost_settlement {{x.class}}"></span>
            </span>

            </div>
        </div> <!-- settlement_sheet_block_group -->

        <div id="lostSettlementsControls" style="display: none" class="lost_settlements_controls">
            <button
                ng-click="rmLostSettlement(); ls_range(2)"
            >
                &#9662;
            </button>
            <button
                ng-click="addLostSettlement()"
            >
                &#9652;
            </button>
        </div>

        </div> <!-- lost settlement application -->


        <br class="mobile_only"/>
        <hr class="mobile_only"/>

        <div class="settlement_sheet_block_group">

            <h3>Abandon Settlement</h3>
            <p>Mark a settlement as "Abandoned" to prevent it from showing up in your active campaigns without removing it from the system.</p>

            <form action="#" method="POST" onsubmit="return confirm('This will prevent this settlement from appearing on any user Dashboard, including yours. Press OK to Abandon this settlement forever.');">
                <input type="hidden" name="modify" value="settlement" />
                <input type="hidden" name="asset_id" value="$settlement_id" />
                <input type="hidden" name="abandon_settlement" value="toggle" />
                <button class="kd_alert_no_exclaim red_glow"> Abandon Settlement </button>
            </form>
        </div>

    $remove_settlement_button

    </div> <!-- right pane -->


    <!--

        This is the fold! Anything below here is below the fold!
        This should only be modals, heavy angularjs stuff, etc. that is
        still within the settlementSheetApp, but that doesn't need to
        load right away.

    -->

    <form id="settlementSheetReload" method="POST" action="/"><button class="hidden" />SUBMIT</button></form>



</div> <!-- settlementSheetApp -->



    \n""")


    remove_settlement_button = Template("""\

    <div class="settlement_sheet_block_group">
        <h3>Permanently Remove Settlement</h3>
        <form
            action="#"
            method="POST"
            onsubmit="return confirm('Press OK to permanently delete this settlement AND ALL SURVIVORS WHO BELONG TO THIS SETTLEMENT forever. \\r\\rPlease note that this CANNOT BE UNDONE and is not the same as marking a settlement Abandoned.\\r\\rPlease consider abandoning old settlements rather than removing them, as this allows data about the settlement to be used in general kdm-manager stats.\\r\\r');"
        >
            <input type="hidden" name="remove_settlement" value="$settlement_id"/>
            <p>
                Use the button below to permanently delete <i>$settlement_name</i>.
                Please note that <b>this cannot be undone</b> and that this will
                also permanently remove all survivors associated with this
                settlement.
            </p>
            <button class="kd_alert_no_exclaim red_glow permanently_delete">
                Permanently Delete Settlement
            </button>
        </form>
    </div>
    """)

    location_level_controls = Template("""\n\
    $location_name - Lvl
    <form method="POST" action="#edit_locations" class="location_level">
        <input type="hidden" name="modify" value="settlement" />
        <input type="hidden" name="asset_id" value="$settlement_id" />
        <select class="location_level" name="location_level_$location_name" onchange="this.form.submit()">
            $select_items
        </select>
    </form>
    \n""")
    principle_radio = Template("""\n
        <input onchange="this.form.submit()" type="radio" id="$handle" class="radio_principle" name="principle_$principle_key" value="$option" $checked /> 
        <label class="radio_principle_label" for="$handle"> $option </label>
    \n""")
    principle_control = Template("""\n
    <div>
    <p><b>$name</b></p>
    <fieldset class="settlement_principle">
        $radio_buttons
    </fieldset>
    </div>
    \n""")
    innovation_heading = Template("""\n
    <h5>$name</h5><p class="$show_subhead campaign_summary_innovation_subhead innovation_gradient">$subhead</p>
    \n""")


class meta:
    """ This is for HTML that doesn't really fit anywhere else, in terms of
    views, etc. Use this for helpers/containers/administrivia/etc. """

    basic_http_header = "Content-type: text/html\n\n"
    basic_file_header = "Content-Disposition: attachment; filename=%s\n"

    hide_full_page_loader = '<script type="text/javascript">hideFullPageLoader();</script>'

    norefresh_response = Template("""Content-type: text/html\nStatus: $status\n\n
    <html><head><title>$status - $response</title></head><body>$response</body></html>
    """)

    error_500 = Template("""%s<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
    <html><head><title>%s</title></head>
    <body>
        <h1>500 - Server Explosion!</h1>
        <hr/>
        <p>The server erupts in a shower of gore, killing your request instantly. All other servers are so disturbed that they lose 1 survival.</p>
        <hr/>
        <p>$msg</p>
        <p>$params</p>
        <hr/>
        <p>Please report errors and issues at <a href="https://github.com/toconnell/kdm-manager/issues">https://github.com/toconnell/kdm-manager/issues</a></p>
        <p>Use the information below to report this error:</p>
        <hr/>
        <p>%s</p>
        <h2>Traceback:</h2>
        $exception\n""" % (basic_http_header, settings.get("application","title"), datetime.now()))

    start_head = """<!DOCTYPE html>\n<html>
    <head>
        <meta http-equiv="content-type" content="text/html; charset=utf-8" />
        <meta name="theme-color" content="#000000">
        <title>%s</title>
        <link rel="stylesheet" type="text/css" href="/media/style.css?v=%s">
        <link rel="stylesheet" type="text/css" href="/media/help-tip.css">
        <link rel="stylesheet" type="text/css" href="/media/z-index.css?v=%s">
    """ % (
        settings.get("application","title"),
        settings.get('application', 'version'),
        settings.get('application', 'version')
    )

    close_body = """\n
    </div><!-- container -->
    </body>
    </html>
    <script type="text/javascript">
        // kill the spinner, just in case it hasn't been killed
        //hideFullPageLoader();
    </script>
    """
    saved_dialog = """\n
    <div id="saved_dialog" class="saved_dialog_frame" style="">
        <div class="kd_blue saved_dialog_inner">
            <span class="saved_dialog_cap">S</span>
            Saving...
        </div>
    </div>

    <div id="error_dialog" class="saved_dialog_frame" style="">
        <div class="kd_alert_no_exclaim saved_dialog_inner">
            <span class="error_dialog_cap">E</span>
            <b>An Error Occurred!</b>
        </div>
    </div>

    <div
        id="apiErrorModal"
        class="api_error_modal hidden ease clickable"
        onclick="hideAPIerrorModal()">
    >
        <p class="api_error_debug">User login: {{user_login}}</p>
        <p class="api_error_debug">Settlement OID: {{settlement.sheet._id.$oid}}</p>
        <p id="apiErrorModalMsgRequest" class="api_error_debug"></p>
        <p id="apiErrorModalMsg" class="kd_alert_no_exclaim api_error_modal_msg"></p>
        <p>Tap or click anywhere to continue...</p>
    </div>
    \n"""

    full_page_loader = """\n
    <div id="fullPageLoader" class="full_page_loading_spinner">
        <img class="full_page_loading_spinner" src="/media/loading_io.gif">
    </div>
    \n"""
    corner_loader = """\n
    <div id="cornerLoader" class="corner_loading_spinner">
        <img class="corner_loading_spinner" src="/media/loading_io.gif">
    </div>
    \n"""
    mobile_hr = '<hr class="mobile_only"/>'
    dashboard_alert = Template("""\n\
    <div class="dashboard_alert_spacer"></div>
    <div class="kd_alert dashboard_alert">
    $msg
    </div>
    \n""")


    burger_top_level_button = Template("""\n
    <form method="POST" action="/"><input type="hidden" name="change_view" value="$view"/>
    <button class="sidenav_top_level" onclick="showFullPageLoader(); closeNav()"> $link_text </button>
    </form>
    \n""")
    burger_new_settlement = '<div id="mySidenav" class="sidenav">' + burger_top_level_button.safe_substitute(link_text = "Return to Dashboard", view = "dashboard") + '</div><!-- mySidenav -->' + '<button id="floating_dashboard_button" class="gradient_silver" onclick="openNav()"> &#9776; </button>'
    burger_signout_button = Template("""\n
    <form id="logout" method="POST" action="/">
    <input type="hidden" name="remove_session" value="$session_id"/>
    <input type="hidden" name="login" value="$login"/>
    <button>$login<br/>SIGN OUT</button>
    </form>
    \n""")
    burger_change_view_button = Template("""\n
    <form method="POST" action="/">
    <input type="hidden" name="$target_view" value="$settlement_id" />
    <button class="sidenav_button" onclick="showFullPageLoader(); closeNav()">$link_text</button>
    </form>
    \n""")

    burger_export_button = Template("""\n
    <form method="POST" action="/">
     <input type="hidden" name="export_campaign" value="XLS"/>
     <input type="hidden" name="asset_id" value="$settlement_id"/>
     <button class="sidenav_button"> $link_text </button>
    </form>
    \n""")

    burger_anchors_campaign_summary = """\n
    <a href="#" onclick="closeNav()">Survivors</a>
    <a href="#endeavors" onclick="closeNav()">Endeavors</a>
    <a href="#principles" onclick="closeNav()">Principles</a>
    <a href="#innovations" onclick="closeNav()">Innovations</a>
    \n"""
    report_error_button = """<button id="reportErrorButton" onclick="closeNav()">Report an Issue or Error</button>"""
    report_error_div = """\n
    <div
        id="modalReportError" class="modal"
        ng-init="registerModalDiv('reportErrorButton','modalReportError')"
    >
        <div class="modal-content timeline_gradient">
            <span class="closeModal" onclick="closeModal('modalReportError')">×</span>
            <div class="report_error_container">
                <h3>Report an Issue or Error</h3>
                <p>http://kdm-manager.com is a work in progress and is under active development!</p>
                <p>If you identify an issue, error or problem with the application, whether a simple typo, a presentation problem or otherwise, there are a number of ways to report it.</p>
                <p>To rapidly submit an issue via email, use the form below:
                <div class="error_form">
                    <form method="POST" action="/">
                     <input type="hidden" name="error_report" value="from_web">
                     <textarea class="report_error" name="body" placeholder="Describe your issue here"></textarea>
                     <input type="submit" class="kd_alert_no_exclaim" value ="submit"/>
                    </form>
                </div>
                </p>
                <p>Please note that until KD:M 1.5 and/or AKD:M are released, the Manager will continues to use <u>all available 1.4n rules plus any errata or corrections from the FAQ</u> on <a href="http://kingdomdeath.com" target="top">http://kingdomdeath.com</a>.</p>
                <p><b>General Comments/Questions:</b> use <a href="http://kdm-manager.blogspot.com//" target="top">the Development blog at blog.kdm-manager.com</a> to review change logs, make comments and ask questions about the manager.</p>
                <p><b>Source code and development questions:</b> if you're interested, you can clone/download and review the <a href="https://github.com/toconnell/kdm-manager" target="top">source code for the manager</a> from GitHub. <a href="https://github.com/toconnell/kdm-manager/wiki" target="top">The development wiki</a> also has some good stuff.</p>
                <p><b>Issues and Errors:</b> feel free to mention any issues/errors on the blog comments or, if you use GitHub, you may also submit issues to <a href="https://github.com/toconnell/kdm-manager/issues" target="top">the project's issues tracker</a>.</p>
            </div>
        </div><!-- modal-content -->
    </div> <!-- modalReportError -->

    \n"""
    error_report_email = Template("""\n\
    Greetings!<br/><br/>&ensp;User $user_email [$user_id] has submitted an error report!<br/><br/>The report goes as follows:<hr/>$body<hr/>&ensp;...and that's it. Good luck!<br/><br/>Your friend,<br/>&ensp; meta.error_report_email
    \n""")
    view_render_fail_email = Template("""\n
    Greetings!<br/><br/>&ensp;User $user_email [$user_id] was logged out of the webapp instance on <b>$hostname</b> due to a render failure at $error_time.<br/><br/>&ensp;The traceback from the exception was this:<hr/><code>$exception</code><hr/>&ensp;The session object was this:<hr/><code>$session_obj</code><hr/>&ensp;Good hunting!<br/><br/>Your friend,<br/>meta.view_render_fail_email()
    \n""")
    safari_warning = Template("""\n\
    <div class="safari_warning">
    <p>It looks like you're using Safari $vers. Unfortunately, the current version
    of this application uses some presentation elements that are not fully
    supported by your browser.</p>
    <p>If you experience disruptive presentation and/or functionality issues while
    using the manager, <a href="https://www.google.com/chrome/browser"
    target="top">Chrome</a> is fully supported on Windows and OSX.</p>
    </div>
    \n""")




#
#   render() funcs are the only thing that goes below here.
#

def render_burger(session_object=None):
    """ This renders hamburger ('side nav') menu and controls based on the
    'view' kwarg value.

    Returns "" (i.e. an empty string) if the view is not dashboard
    """

    # first, handle all situations in which we don't return a burger button or
    #   even write the menu
    no_burger_string = "\n<!-- no burger in this view! -->\n\n"
    if session_object is None:
        return no_burger_string
    elif session_object.session is None:
        return no_burger_string
    elif session_object.Settlement is None and session_object.session is None:
        return no_burger_string
    elif session_object.Settlement is None and session_object.session is not None:
        if session_object.session["current_view"] == "new_settlement":
            pass
        else:
            return no_burger_string
    elif not hasattr(session_object.Settlement, "settlement"):
        return no_burger_string
    elif session_object.Settlement.settlement is None:
        return no_burger_string

    view = session_object.session["current_view"]

    if view not in ["view_campaign","view_settlement","view_survivor","new_survivor","new_settlement"]:
        return "\n<!-- no burger in '%s' view -->\n\n" % view

    signout_button = meta.burger_signout_button.safe_substitute(
        session_id=session_object.session["_id"],
        login=session_object.User.user["login"],
    )

    # first, create the mini-burger for the new_settlement view
    if view == "new_settlement":
        burger_panel = Template("""\n
            <!-- $current_view burger -->

            <div id="mySidenav" class="sidenav">
              $dash
              <hr/>
              $report_error
              $signout
            </div>

            <button id="floating_dashboard_button" class="gradient_silver" onclick="openNav()">
                &#9776;
            </button>

            <!-- end $current_view burger -->
        """)

        output = burger_panel.safe_substitute(
            dash=meta.burger_top_level_button.safe_substitute(
                link_text = "Return to Dashboard",
                view = "dashboard",
            ),
            report_error=meta.report_error_button,
            signout=signout_button,
        )

        return output


    # now, create a settlement burger.
    # first, set defaults:


    new_settlement = meta.burger_top_level_button.safe_substitute(
        link_text = "+ New Settlement",
        view = "new_settlement",
    )

    # create a list of action buttons based on view/session info
    actions = '<button id="newSurvivorButton" class="sidenav_button">+ Create New Survivor</button>'
    if session_object.User.is_settlement_admin():
        actions += '<button id="bulkAddOpenerButton" class="sidenav_button">+ Create Multiple Survivors</button>'
        actions += '<button id="bulkExpansionsManagerButton" class="sidenav_button"> Expansion Content</button>'
    if view in ["view_campaign","view_survivor"]:
        if session_object.User.is_settlement_admin():
            actions += meta.burger_change_view_button.safe_substitute(
                link_text = "Settlement Sheet",
                target_view = "view_settlement",
                settlement_id = session_object.session["current_settlement"],
            )
    if view in ["view_settlement","view_survivor"]:
        actions += meta.burger_change_view_button.safe_substitute(
            link_text = "Campaign Summary",
            target_view = "view_campaign",
            settlement_id = session_object.session["current_settlement"]
        )

    if view in ["view_survivor","view_campaign","view_settlement"]:
        actions += '<button id="timelineOpenerButton" class="sidenav_button">Timeline</button>'
        actions += '<button id="settlementNotesOpenerButton" class="sidenav_button">Notes and Players</button>'


    burger_panel = Template("""\n
        <!-- $current_view burger -->

        <div id="mySidenav" class="sidenav" ng-controller="sideNavController">
          $dash
          $new_settlement_button
            <hr/>
            <h3>$settlement_name:</h3>
            $action_map

            <h3 ng-if="countSurvivors('departing') > 0">Departing</h3>
            <form
                method="POST"
                action="/"
                ng-repeat="s in settlement.user_assets.survivors | filter: departingFilter"
            >
                <input type="hidden" name="view_survivor" value="{{s.sheet._id.$oid}}" />
                <button class="sidenav_button" onclick="showFullPageLoader(); closeNav()">{{s.sheet.name}} ({{s.sheet.effective_sex}})</button>
            </form>

            <h3 ng-if="countSurvivors('favorite') > 0">Favorites</h3>
            <form
                method="POST"
                action="/"
                ng-repeat="s in settlement.user_assets.survivors | filter: favoriteFilter"
            >
                <input type="hidden" name="view_survivor" value="{{s.sheet._id.$oid}}" />
                <button class="sidenav_button" onclick="showFullPageLoader(); closeNav()">{{s.sheet.name}} ({{s.sheet.effective_sex}})</button>
            </form>

            <hr/>
          $report_error
          $signout
        </div> <!-- mySidenav -->

        <button id="floating_dashboard_button" class="gradient_silver" onclick="openNav()">
            &#9776;
        </button>

        <!-- end $current_view burger -->
    """)

    output = burger_panel.safe_substitute(
        application_version = settings.get('application', 'version'),
        settlement_name=session_object.Settlement.settlement["name"],
        current_view=view,
        dash=meta.burger_top_level_button.safe_substitute(
            link_text = "Return to Dashboard",
            view = "dashboard",
        ),
        new_settlement_button = new_settlement,
        report_error=meta.report_error_button,
        signout=signout_button,
        action_map=actions,
    )

    return output



def render(view_html, head=[], http_headers=None, body_class=None, session_object=None):
    """ This is our basic render: feed it HTML to change what gets rendered. """

    output = http_headers
    if http_headers is None:
        output = meta.basic_http_header
    else:
        print http_headers
        try:
            print view_html.read()  # in case we're returning StringIO
        except AttributeError:
            print view_html
        sys.exit()

    output += meta.start_head

    output += """\n\
    <!-- android mobile desktop/app stuff -->
    <link rel="manifest" href="/manifest.json">

    <!-- fucking jquery's dumb ass -->
    <script src="http://ajax.googleapis.com/ajax/libs/jquery/1.7/jquery.js"></script> 

    <!-- angular app -->
    <script src="https://ajax.googleapis.com/ajax/libs/angularjs/1.5.4/angular.min.js"></script>

    <script src="/media/kdmManager.js?v=%s"></script>
    \n""" % settings.get("application", "version")

    output += """\n\
    <script>
      (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
      (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
      m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
      })(window,document,'script','//www.google-analytics.com/analytics.js','ga');
      ga('create', 'UA-71038485-1', 'auto');
      ga('send', 'pageview');
    </script>
    \n"""

    for element in head:
        output += element


    #
    # now close the head elements and start writing the body, preparing to print
    #   it to stdout (i.e. render it as a response
    #

    output += '</head>\n<body class="%s" ng-app="kdmManager" ng-controller="rootController">\n' % body_class

    output += render_burger(session_object) # burger goes before container

    output += """\n
    <div
        id="container"
        onclick="closeNav()"
    >
    \n"""

    output += view_html
    output += meta.report_error_div
    output += meta.close_body

    # all html we render gets this template substitution
    output = Template(output).safe_substitute(
            api_url = api.get_api_url(),
    )

    print(output.encode('utf8'))

    sys.exit(0)     # this seems redundant, but it's necessary in case we want
                    #   to call a render() in the middle of a load, e.g. to just
                    #   finish whatever we're doing and show a page.
