description = """ a module for performing checks of GraceDB triggered processes. NOTE: the "check" functions return TRUE if the check failed (action is needed) and FALSE if everything is fine """

#=================================================

import time
import numpy as np

#=================================================
# utilities
#=================================================

def report( string ):
    print "%s GMT :  %s"%(time.asctime(time.gmtime()), string)

def datestring_converter( datestring ):
    """
    converts a lalapps_tconvert return string into the correct form for GraceDB queries
    """
    monthD = dict( zip("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), range(1,13)) )
    wkday, month, day, timestamp, timezone, yr = datestring.split()
    return "%s-%s-%s %s"%(yr, __fix_int(monthD[month]), __fix_int(day), timestamp) ### leave off timezone
#    return "%s-%s-%s %s %s"%(yr, __fix_int(monthD[month]), __fix_int(day), timestamp, timezone)

def __fix_int( num ):
    if num < 10:
        return "0%d"%num
    else:
        return "%s"%num

def file_has_tag( gdb, gdb_id, filename, tag, verbose=False ):
    """
    checks whether a filename has the stated tag
    """
    if verbose:
        report( "%s : file_has_tag -> %s %s"%(gdb_id, filename, tag) )

    ### get this event
    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log messages" )
    for log in logs[::-1]: ### iterate through logs in reverse so we get the most recent logs first
                           ### this means we will get the most recent version of files, if multiple exist
        if filename == log['filename']: ### this is the log message associated with that filename
            if verbose:
                report( "\t%s assoicated with log message : %d"%(filename, log['N']) )
            return tag in log['tag_names']
    else:
        raise ValueError( "could not find %s in association with any log messages for %s"%(filename, gdb_id) )

def tags_match( gdb, gdb_id, filename1, filename2, verbose=False ):
    """
    checks to make sure the filenames have the same tags.
    requires an exact match.
    """
    if verbose:
        report( "%s : tags_match -> %s %s"%(gdb_id, filename1, filename2) )

    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log messages" )
    tags1=None
    tags2=None
    for log in logs[::-1]:
        if (tags1==None) and (filename1 == log['filename']):
            if verbose:
                report( "\t%s associated with log message : %d"%(filename1, log['N']) )
            tags1 = log['tag_names']
        if (tags2==None) and (filename2 == log['filename']):
            if verbose:
                report( "\t%s associated with log message : %d"%(filename2, log['N']) )
            tags2 = log['tag_names']
        if (tags1!=None) and (tags2!=None):
            break
    else:
        if tags1==None:
            raise ValueError( "could not find %s in association with any log messages for %s"%(filename1, gdb_id) )
        if tags2==None:
            raise ValueError( "could not find %s in association with any log messages for %s"%(filename2, gdb_id) )

    return sorted(tags1) == sorted(tags2) ### require an exact match

#=================================================
# set up schedule of checks
#=================================================

def get_dt( string ):
    """
    converts dt string from config file into a list of floats
    """
    return [float(l) for l in string.split()]

def config_to_schedule( config, event_type, verbose=False, freq=None ):
    """
    determines the schedule of checks that should be performed for this event
    the checks should be (timestamp, function, kwargs, email) tuples, where timestamp is the amount of time after NOW we wait until performing the check, function is the specific function that performs the check (should have a uniform input argument? just the gracedb connection?) that returns either True or False depending on whether the check was passed, kwargs are any extra arguments needed for function, and email is a list of people to email if the check fails
    """

    ### extract lists of checks
    if verbose:
        report( "reading in default checks" )
    checks = dict( config.items("default") )
    if config.has_section(event_type):
        if verbose:
            report( "reading in extra checks specific for event_type : %s"%(event_type) )
        checks.update( dict( config.items(event_type) ) )
    elif verbose:
        report( "no section found corresponding to event_type : %s"%(event_type) )

    ### construct schedule
    schedule = []

    #=== just let people know
    if checks.has_key("notify"):
        if verbose:
            report( "\tnotify" )
        kwargs = {"verbose":verbose}
        dt = 0.0
        schedule.append( (dt, notify, kwargs, checks['notify'].split(), 'just a notification' ) )

    #=== properties of this event
    if checks.has_key("far"):
        if verbose:
            report( "\tcheck far" )
        kwargs = {"minFAR":config.getfloat("far","minFAR"), "maxFAR":config.getfloat("far","maxFAR"), "verbose":verbose}
        for dt in get_dt( config.get("far", "dt") ):
            schedule.append( (dt, far_check, kwargs, checks['far'].split(), "far") )

    #=== local properties of event streams
    if checks.has_key("local_rates"):
        if verbose:
            report( "\tcheck local_rates (event time)" )
            report( "\tcheck local_rates (creation time)" )
        event_kwargs = {"rate_thr":config.getfloat("local_rates","rate") , "window":config.getfloat("local_rates","window"), "verbose":verbose, "timestamp":"event_time"}
        creation_kwargs = {"rate_thr":config.getfloat("local_rates","rate") , "window":config.getfloat("local_rates","window"), "verbose":verbose, "timestamp":"creation_time"}
        for dt in get_dt( config.get("local_rates", "dt") ):
            schedule.append( (dt, local_rates, event_kwargs, checks["local_rates"].split(), "local_rates at event_time") )
            schedule.append( (dt, local_rates, creation_kwargs, checks["local_rates"].split(), "local_rates at creation_time") )

    #=== event creation
    if checks.has_key('eventcreation'):
        group, pipeline = event_type.split("_")[:2]
        if pipeline == "cwb":
            if verbose:
                report( "\tcheck cWB event creation" )
            kwargs = {'verbose':verbose}
            for dt in get_dt( config.get("eventcreation", "dt") ):
                schedule.append( (dt, cwb_eventcreation, kwargs, checks['eventcreation'].split(), "cwb_eventcreation") )

        elif pipeline == "olib":
            if verbose:
                report( "\tcheck oLIB event creation" )
            kwargs = {'verbose':verbose}
            for dt in get_dt( config.get("eventcreation", "dt") ):
                schedule.append( (dt, olib_eventcreation, kwargs, checks['eventcreation'].split(), "olib_eventcreation") )

        elif pipeline == "gstlal":
            if verbose:
                report( "\tcheck gstlal event creation" )
            kwargs = {'verbose':verbose}
            for dt in get_dt( config.get("eventcreation", "dt") ):
                schedule.append( (dt, gstlal_eventcreation, kwargs, checks['eventcreation'].split(), "gstlal_eventcreation") )

        elif pipeline == "mbtaonline":
            if verbose:
                report( "\tcheck MBTA event creation" )
            kwargs = {'verbose':verbose}
            for dt in get_dt( config.get("eventcreation", "dt") ):
                schedule.append( (dt, mbta_eventcreation, kwargs, checks['eventcreation'].split(), "mbta_eventcreation") )

    #=== idq
    if checks.has_key("idq_start"):
        if verbose:
            report( "\tcheck idq_start" )
        kwargs = {"ifos":config.get("idq","ifos").split(), 'verbose':verbose}
        for dt in get_dt( config.get("idq", "start") ):
            schedule.append( (dt, idq_start, kwargs, checks['idq_start'].split(), "idq_start") )

    if checks.has_key("idq_finish"):
        if verbose:
            report( "\tcheck idq_finish" )
        kwargs = {"ifos":config.get("idq","ifos").split(), 'verbose':verbose}
        for dt in get_dt( config.get("idq", "finish") ):
            schedule.append( (dt, idq_finish, kwargs, checks['idq_finish'].split(), "idq_finish") )

    if checks.has_key("idq_timeseries"):
        if verbose:
            report( "\tcheck idq_timeseries" )
        kwargs = {"ifos":config.get("idq","ifos").split(), 'verbose':verbose}
        for dt in get_dt( config.get("idq", "timeseries") ):
            schedule.append( (dt, idq_timeseries, kwargs, checks['idq_timeseries'].split(), "idq_timeseries") )

    if checks.has_key("idq_tables"):
        if verbose:
            report( "\tcheck idq_tables" )
        kwargs = {"ifos":config.get("idq","ifos").split(), 'verbose':verbose}
        for dt in get_dt( config.get("idq", "tables") ):
            schedule.append( (dt, idq_tables, kwargs, checks['idq_tables'].split(), "idq_tables") )

    #=== cWB
    if checks.has_key("cwb_skymap"):
        if verbose:
            report( "\tcheck cwb_skymap" )
        kwargs = {'verbose':verbose}
        if config.has_option('cwb', 'lvem'):
            kwargs.update( {'lvem':config.getboolean('cwb','lvem')} )
        for dt in get_dt( config.get('cwb', 'skymap') ):
            schedule.append( (dt, cwb_skymap, kwargs, checks['cwb_skymap'].split(), 'cwb_skymap') )

    #=== lib
    if checks.has_key("lib_start"):
        if verbose:
            report( "\tcheck lib_start" )
        kwargs = {'verbose':verbose}
        if config.has_option('lib', 'far'):
            kwargs.update( {'far':config.getfloat('lib', 'far')} )
        for dt in get_dt( config.get("lib", "start") ):
            schedule.append( (dt, lib_start, kwargs, checks['lib_start'].split(), "lib_start") )        

    if checks.has_key("lib_finish"):
        if verbose:
            report( "\tcheck lib_finish" )
        kwargs = {'verbose':verbose}
        if config.has_option('lib', 'far'):
            kwargs.update( {'far':config.getfloat('lib', 'far')} )

        ### divide based on frequency
        if config.has_option('lib', 'freq_thr'): ### we split based on freq_thr
            if freq!=None: ### we know the frequency
                freq_thr = config.getfloat("lib", "freq_thr")
                if freq > freq_thr:
                    if verbose:
                        report( "\t\tfreq = %.3f Hz > %.3f Hz. Using high frequency scheduling"%(freq, freq_thr) )
                    waits = get_dt( config.get("lib", "high_freq_finish") )
                else:
                    if verbose:
                        report( "\t\tfreq = %.3f <= %.3f Hz. Using low frequency scheduling"%(freq, freq_thr) )
                    waits = get_dt( config.get("lib", "low_freq_finish") )

            else: ### we don't know the frquency but we split based on freq_thr
                if verbose:
                    report( "\t\tno frequency specified; using all provided scheduling information" )
                waits = set( get_dt( config.get("lib", "low_freq_finish") ) + get_dt( config.get("lib", "high_freq_finish") ) )

        else: ### we don't split based on freq_thr
            waits = get_dt( config.get("lib", "finish") )

        for dt in waits:
            schedule.append( (dt, lib_finish, kwargs, checks['lib_finish'].split(), "lib_finish") )

    if checks.has_key("lib_skymap"):
        if verbose:
            report( "\tcheck lib_skymap" )
        kwargs = {'verbose':verbose}
        if config.has_option('lib', 'far'):
            kwargs.update( {'far':config.getfloat('lib', 'far')} )
        if config.has_option('lib', 'lvem'):
            kwargs.update( {'lvem':config.getboolean('lib', 'lvem')} )

        ### divide based on frequency
        if config.has_option('lib', 'freq_thr'): ### we split based on freq_thr
            if freq!=None: ### we know the frequency
                freq_thr = config.getfloat("lib", "freq_thr")
                if freq > freq_thr:
                    if verbose:
                        report( "\t\tfreq = %.3f Hz > %.3f Hz. Using high frequency scheduling"%(freq, freq_thr) )
                    waits = get_dt( config.get("lib", "high_freq_skymap") )
                else:
                    if verbose:
                        report( "\t\tfreq = %.3f <= %.3f Hz. Using low frequency scheduling"%(freq, freq_thr) )
                    waits = get_dt( config.get("lib", "low_freq_skymap") )

            else: ### we don't know the frquency but we split based on freq_thr
                if verbose:
                    report( "\t\tno frequency specified; using all provided scheduling information" )
                waits = set( get_dt( config.get("lib", "low_freq_skymap") ) + get_dt( config.get("lib", "high_freq_skymap") ) )

        else: ### we don't split based on freq_thr
            waits = get_dt( config.get("lib", "skymap") )

        for dt in waits:
            schedule.append( (dt, lib_skymap, kwargs, checks['lib_skymap'].split(), "lib_skymap") )

    #=== bayestar
    if checks.has_key("bayestar_start"):
        if verbose:
            report( "\tcheck bayestar_start" )
        kwargs = {'verbose':verbose}
        if config.has_option('bayestar', 'far'):
            kwargs.update( {'far':config.getfloat('bayestar', 'far')} )
        for dt in get_dt( config.get("bayestar", "start") ):
            schedule.append( (dt, bayestar_start, kwargs, checks['bayestar_start'].split(), "bayestar_start") )

    if checks.has_key("bayestar_finish"):
        if verbose:
            report( "\tcheck bayestar_finish" )
        kwargs = {'verbose':verbose}
        if config.has_option('bayestar', 'far'):
            kwargs.update( {'far':config.getfloat('bayestar', 'far')} )
        for dt in get_dt( config.get("bayestar", "finish") ):
            schedule.append( (dt, bayestar_finish, kwargs, checks['bayestar_finish'].split(), "bayestar_finish") )

    if checks.has_key("bayestar_skymap"):
        if verbose:
            report( "\tcheck bayestar_skymap" )
        kwargs = {'verbose':verbose}
        for dt in get_dt( config.get("bayestar", "skymap") ):
            schedule.append( (dt, bayestar_skymap, kwargs, checks['bayestar_skymap'].split(), "bayestar_skymap") )
        if config.has_option('bayestar', 'lvem'):
            kwargs.update( {'lvem':config.getboolean('bayestar', 'lvem')} )

    #=== bayeswave
    if checks.has_key("bayeswave_start"):
        if verbose:
            report( "\tcheck bayeswave_start" )
        kwargs = {'verbose':verbose}
        if config.has_option('bayeswave', 'far'):
            kwargs.update( {'far':config.getfloat('bayeswave', 'far')} )
        for dt in get_dt( config.get("bayeswave", "start") ):
            schedule.append( (dt, bayeswave_start, kwargs, checks['bayeswave_start'].split(), "bayeswave_start") )

    if checks.has_key("bayeswave_finish"):
        if verbose:
            report( "\tcheck bayeswave_finish" )
        kwargs = {'verbose':verbose}
        if config.has_option('bayeswave', 'far'):
            kwargs.update( {'far':config.getfloat('bayeswave', 'far')} )

        ### divide based on frequency
        if config.has_option('bayeswave', 'freq_thr'): ### we split based on freq_thr
            if freq!=None: ### we know the frequency and we split based on freq_thr
                freq_thr = config.getfloat("bayeswave", "freq_thr")
                if freq > freq_thr:
                    if verbose:
                        report( "\t\tfreq = %.3f Hz > %.3f Hz. Using high frequency scheduling"%(freq, freq_thr) )
                    waits = get_dt( config.get("bayeswave", "high_freq_finish") )
                else:
                    if verbose:
                        report( "\t\tfreq = %.3f <= %.3f Hz. Using low frequency scheduling"%(freq, freq_thr) )
                    waits = get_dt( config.get("bayeswave", "low_freq_finish") )
        
            else: ### we don't know the frquency but we split based on freq_thr
                if verbose:
                    report( "\t\tno frequency specified; using all provided scheduling information" )
                waits = set( get_dt( config.get("bayeswave", "low_freq_finish") ) + get_dt( config.get("bayeswave", "high_freq_finish") ) )
        
        else: ### we don't split based on freq_thr
            waits = get_dt( config.get("bayeswave", "finish") )

        for dt in waits:
            schedule.append( (dt, bayeswave_finish, kwargs, checks['bayeswave_finish'].split(), "bayeswave_finish") )

    if checks.has_key("bayeswave_skymap"):
        if verbose:
            report( "\tcheck bayeswave_skymap" )
        kwargs = {'verbose':verbose}
        if config.has_option('bayeswave', 'far'):
            kwargs.update( {'far':config.getfloat('bayeswave', 'far')} )
        if config.has_option('bayeswave', 'lvem'):
            kwargs.update( {'lvem':config.getboolean('bayeswave', 'lvem')} )

        ### divide based on frequency
        if config.has_option('bayeswave', 'freq_thr'): ### we split based on freq_thr
            if freq!=None: ### we know the frequency and we split based on freq_thr
                freq_thr = config.getfloat("bayeswave", "freq_thr")
                if freq > freq_thr:
                    if verbose:
                        report( "\t\tfreq = %.3f Hz > %.3f Hz. Using high frequency scheduling"%(freq, freq_thr) )
                    waits = get_dt( config.get("bayeswave", "high_freq_skymap") )
                else:
                    if verbose:
                        report( "\t\tfreq = %.3f <= %.3f Hz. Using low frequency scheduling"%(freq, freq_thr) )
                    waits = get_dt( config.get("bayeswave", "low_freq_skymap") )

            else: ### we don't know the frquency but we split based on freq_thr
                if verbose:
                    report( "\t\tno frequency specified; using all provided scheduling information" )
                waits = set( get_dt( config.get("bayeswave", "low_freq_skymap") ) + get_dt( config.get("bayeswave", "high_freq_skymap") ) )

        else: ### we don't split based on freq_thr
            waits = get_dt( config.get("bayeswave", "skymap") )

        for dt in waits:
            schedule.append( (dt, bayeswave_skymap, kwargs, checks['bayeswave_skymap'].split(), "bayeswave_skymap") )

    #=== lalinference
    if checks.has_key("lalinference_start"):
        if verbose:
            report( "\tcheck lalinference_start" )
        kwargs = {'verbose':verbose}
        if config.has_option('lalinference', 'far'):
            kwargs.update( {'far':config.getfloat('lalinference', 'far')} )
        for dt in get_dt( config.get("lalinference", "start") ):
            schedule.append( (dt, lalinference_start, kwargs, checks['lalinference_start'].split(), "lalinference_start") )

    if checks.has_key("lalinference_finish"):
        if verbose:
            report( "\tcheck lalinference_finish" )
        kwargs = {'verbose':verbose}
        if config.has_option('lalinference', 'far'):
            kwargs.update( {'far':config.getfloat('lalinference', 'far')} )
        for dt in get_dt( config.get("lalinference", "finish") ):
            schedule.append( (dt, lalinference_finish, kwargs, checks['lalinference_finish'].split(), "lalinference_finish") )

    if checks.has_key("lalinference_skymap"):
        if verbose:
            report( "\tcheck lalinference_skymap" )
        kwargs = {'verbose':verbose}
        if config.has_option('lalinference', 'far'):
            kwargs.update( {'far':config.getfloat('lalinference', 'far')} )
        if config.has_option('lalinference', 'lvem'):
            kwargs.update( {'lvem':config.getboolean('lalinference', 'lvem')} )

        for dt in get_dt( config.get("lalinference", "skymap") ):
            schedule.append( (dt, lalinference_skymap, kwargs, checks['lalinference_skymap'].split(), "lalinference_skymap") )

    #=== externaltriggers
    if checks.has_key("externaltriggers_search"):
        if verbose:
            report( "\tcheck externaltriggers_search" )
        kwargs = {'verbose':verbose}
        for dt in get_dt( config.get("externaltriggers_search", "dt") ):
            schedule.append( (dt, externaltriggers_search, kwargs, checks['externaltriggers_search'].split(), "externaltriggers_search") )

    #=== unblindinjections
    if checks.has_key("unblindinjections_search"):
        if verbose:
            report( "\tcheck unblindinjections_search" )
        kwargs = {'verbose':verbose}
        for dt in get_dt( config.get("unblindinjections_search", "dt") ):
            schedule.append( (dt, unblindinjections_search, kwargs, checks['unblindinjections_search'].split(), "unblindinjections_search") )

    #=== plot_skymaps
    if checks.has_key("plot_skymaps"):
        if verbose:
            report( "\tcheck plot_skymaps" )
        kwargs = {'verbose':verbose, 'check_tags':True}
        for dt in get_dt( config.get("plot_skymaps", "dt") ):
            schedule.append( (dt, plot_skymaps, kwargs, checks['plot_skymaps'].split(), "plot_skymaps") )

    #=== json_skymaps
    if checks.has_key("json_skymaps"):
        if verbose:
            report( "\tcheck json_skymaps" )
        kwargs = {'verbose':verbose, 'check_tags':True}
        for dt in get_dt( config.get("json_skymaps", "dt") ):
            schedule.append( (dt, json_skymaps, kwargs, checks['json_skymaps'].split(), "json_skymaps") )

    #=== approval_processor FAR check
    if checks.has_key("approval_processor_far"):
        if verbose:
            report( "\tcheck approval_processor_far")
        kwargs = {'verbose':verbose}
        for dt in get_dt( config.get("approval_processor_far", "dt") ):
            schedule.append( (dt, approval_processor_far, kwargs, checks['approval_processor_far'].split(), "approval_processor_far") )

    #=== emready_label
    if checks.has_key("emready_label"):
        if verbose:
            report( "\tcheck emready_label" )
        kwargs = {'verbose':verbose}
        for dt in get_dt( config.get("emready_label", "dt") ):
            schedule.append( (dt, emready_label, kwargs, checks['emready_label'].split(), "emready_label") )

    #=== peready_label
    if checks.has_key("peready_label"):
        if verbose:
            report( "\tcheck peready_label" )
        kwargs = {'verbose':verbose, 'pe_pipelines':config.get('peready_label', 'pe_pipelines').split()}
        for dt in get_dt( config.get("peready_label", "dt") ):
            schedule.append( (dt, peready_label, kwargs, checks['peready_label'].split(), "peready_label") )

    #=== dqveto_label
    if checks.has_key("dqveto_label"):
        if verbose:
            report( "\tcheck dqveto_label" )
        kwargs = {'verbose':verbose}
        for dt in get_dt( config.get("dqveto_label", "dt") ):
            schedule.append( (dt, dqveto_label, kwargs, checks['dqveto_label'].split(), "dqveto_label") )

    #=== dqwarning_label
    if checks.has_key("dqwarning_label"):
        if verbose:
            report( "\tcheck dqwarning_label" )
        kwargs = {'verbose':verbose}
        for dt in get_dt( config.get("dqwarning_label", "dt") ):
            schedule.append( (dt, dqwarning_label, kwargs, checks['dqwarning_label'].split(), "dqwarning_label") )

    #=== voevent_creation
    if checks.has_key("voevent_creation"):
        if verbose:
            report( "\tcheck voevent_creation" )
        kwargs = {'verbose':verbose}
        for dt in get_dt( config.get("voevent_creation", "dt") ):
            schedule.append( (dt, voevent_creation, kwargs, checks['voevent_creation'].split(), "voevent_creation") )

    #=== voevent_sent
    if checks.has_key("voevent_sent"):
        if verbose:
            report( "\tcheck voevetn_sent" )
        kwargs = {'verbose':verbose}
        for dt in get_dt( config.get("voevent_sent", "dt") ):
            schedule.append( (dt, voevent_sent, kwargs, checks['voevent_sent'].split(), "voevent_sent") )

    ### order according to dt, smallest to largest
    schedule.sort(key=lambda l:l[0])

    return schedule

#=================================================
# methods that don't check things, just notify humans
#=================================================

def notify( gdb, gdb_id, verbose=False ):
    """
    return True
    """
    if verbose:
        report( "%s : notify"%(gdb_id) )
        report( "\taction required : True" )
    return True

#=================================================
# methods that check the local properties of the stream of events submitted to GraceDB
#=================================================

def local_rates( gdb, gdb_id, verbose=False, window=5.0, rate_thr=5.0, event_type=None, timestamp="event_time" ):
    """
    checks that the local rate of events (around the event gpstime) does not exceed the threshold (rate_thr) over the window
    performs this check for ALL event types and for this event type in particular
        both checks must pass for no action to be required

    time_stamp = "event_time" -> use the gps time associated with an event
    time_stamp = "creation_time" -> use the time associated with the event creation
    """
    if verbose:
        report( "%s : local_rates"%(gdb_id) )

    ### get this event
    if verbose:
        report( "\tretrieving information about this event:" )
    gdb_entry = gdb.event( gdb_id ).json()

    ### get event type
    group = gdb_entry['group']
    pipeline = gdb_entry['pipeline']
    if gdb_entry.has_key('search'):
        search = gdb_entry['search']
        event_type = "%s_%s_%s"%(group, pipeline, search)
    else:
        search = None
        event_type = "%s_%s"%(group, pipeline)
    if verbose:
        report( "\t\tevent_type : %s"%(event_type) )

    ### get event time
    if verbose:
        report( "\t\ttimestamp : %s"%(timestamp) )
    if timestamp=="event_time":
        event_time = float(gdb_entry['gpstime'])
        if verbose:
            report( "\t\tgpstime : %.6f"%(event_time) )
        ### query for neighbors in (t-window, t+window), excluding this event
        if verbose:
            report( "\tretrieving neighbors within [%.6f-%.6f, %.6f+%6f]"%(event_time, window, event_time, window) )
        gdb_entries = [ entry for entry in gdb.events( "%d .. %d"%(np.floor(event_time-window), np.ceil(event_time+window)) ) if entry['graceid'] != gdb_id ]

    elif timestamp=="creation_time":
        import subprocess as sp

        event_time = float(sp.Popen(["lalapps_tconvert", gdb_entry['created']], stdout=sp.PIPE).communicate()[0])
        if verbose:
            report( "\t\tcreated : %s -> %.6f"%(gdb_entry['created'], event_time) )
        ### query for neighbors in (t-window, t+window), excluding this event
#        winstart = datestring_converter( sp.Popen(["lalapps_tconvert", "%d"%np.floor(event_time-window)], stdout=sp.PIPE).communicate()[0].strip() )
#        winstop  = datestring_converter( sp.Popen(["lalapps_tconvert", "%d"%np.ceil(event_time+window)], stdout=sp.PIPE).communicate()[0].strip() )
#        if verbose:
#            report( "\tretrieving neighbors within [%s, %s]"%(winstart, winstop) )

        #===========================================================================================
        #
        report( "WARNING: you are using a hack to correct for peculiarities in querying GraceDB with creation time. We convert GMT -> CST by hand by subtracting 5 hours from the gps time and then converting using lalapps_tconvert. This gives us a time in UTC which we pretend is in CST for the query (string formatted through datestring_converter()" )
        winstart = datestring_converter( sp.Popen(["lalapps_tconvert", "%d"%np.floor(event_time-window - 5*3600 )], stdout=sp.PIPE).communicate()[0].strip() )
        winstop   = datestring_converter( sp.Popen(["lalapps_tconvert", "%d"%np.ceil(event_time+window - 5*3600 )], stdout=sp.PIPE).communicate()[0].strip() )
        if verbose:
            report( "\tretrieving neighbors within [%s CST, %s CST]"%(winstart, winstop) )
        #
        #===========================================================================================

        gdb_entries = [ entry for entry in gdb.events( "created: %s .. %s"%(winstart, winstop) ) if entry['graceid'] != gdb_id ]
        
    else:
        raise ValueError("timestamp=%s not understood"%timestamp)

    ### count numbers of events
    if verbose:
        report( "\tcounting events:" )
    nevents = 1
    nevents_type = 1
    for entry in gdb_entries:
        nevents += 1
        if entry.has_key('search'):
            e_type = "%s_%s_%s"%(entry['group'], entry['pipeline'], entry['search'])
        else:
            e_type = "%s_%s"%(entry['group'], entry['pipeline'])

        nevents_type += (e_type == event_type) ### increment if true

    if verbose:
        report( "\t\t%d %s"%(nevents_type, event_type) )
        report( "\t\t%d total"%(nevents) )

    ### check rates
    count_thr = 2*window*rate_thr
    if (nevents_type) > count_thr:
        if verbose:
            if timestamp=="event_time":
                report( "\tevent rate higher than %.3f observed within [%.6f-%.6f, %.6f+%.6f] for event type : %s"%(rate_thr, event_time, window, event_time, window, event_type) )
                report( "\taction_required : True" )
            elif timestamp=="creation_time":
                report( "\tevent creation rate higher than %.3f within [%s, %s] for event type : %s"%(rate_thr, winstart, winstop, event_type) )
                report( "\taction_required : True" )
            else:
                raise ValueError("timestamp=%s not understood"%timestamp)
        return True

    elif (nevents) > count_thr: 
        if verbose:
            if timestamp=="event_time":
                report( "\tevent rate higher than %.3f observed within [%.6f-%.6f, %.6f+%.6f] for all event types"%(rate_thr, event_time, window, event_time, window) )
                report( "\taction_required : True" )
            elif timestamp=="creation_time":
                report( "\tevent creation rate higher than %.3f within [%s, %s] for all event types"%(rate_thr, winstart, winstop) )
                report( "\taction_required : True" )
            else:
                raise ValueError("timestamp=%s not understood"%timestamp)
        return True

    if verbose:
        report( "\taction_required : False" )
    return False

#=================================================
# methods that check that an event was created successfully and all expected meta-data/information has been uploaded
#=================================================

def far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=1e-6 ):
    """
    check that FAR < FARthr
    """
    if verbose:
        report( "%s : far_check"%(gdb_id) )
        report( "\tretrieving event details" )
    event = gdb.event( gdb_id ).json()

    if not event.has_key("far"):
        if verbose:
            report( "\tno FAR found" )
            report( "\taction required : True" )
        return True

    far = event['far']
    big_enough = minFAR < far
    sml_enough = far < maxFAR
    if verbose:
        if big_enough:
            report( "\tFAR > %.6e"%(minFAR) )
        else:
            report( "\tFAR <= %.3e"%(minFAR) )
        if sml_enough:
            report( "\tFAR < %.3e"%(maxFAR) )
        else:
            report( "\tFAR >= %.3e"%(maxFAR) ) 
        
    action_required = not (big_enough and sml_enough)
    if verbose:
        report( "\taction required : %s"%( action_required) )
    return action_required

def cwb_eventcreation( gdb, gdb_id, verbose=False, fits="skyprobcc.fits.gz" ):
    """
    checks that all expected data is present for newly created cWB events.
    This includes:
        the cWB ascii file uploaded by the pipeline for this event
        the fits file generated as part of the detection processes.
    """
    if verbose:
        report( "%s : cwb_eventcreation"%(gdb_id) )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
#    fit = False
    pe = False
    for log in logs:
        comment = log['comment']
        if "cWB parameter estimation" in comment:
            pe = True
#        elif "cWB skymap fit" in comment:
#            fit = True

#        if (fit and pe):
        if (pe):
            break

    if verbose:
#        report( "\taction required : %s"%( not (fit and pe)) )
        report( "\taction required : %s"%( not (pe)) )

#    return not (fit and pe)
    return not (pe)

def olib_eventcreation( gdb, gdb_id, verbose=False ):
    """
    checks that all expected data is present for newly created oLIB (eagle) events.
    This includes:
        the json dictionary uploaed by the pipeline
    """
#    files = gdb.files( gdb_id )
    if verbose:
        report( "%s : olib_eventcreation"%(gdb_id) )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    prelim = False
    for log in logs:
        comment = log['comment']
        if "Preliminary results: " in comment:
            prelim = True

        if prelim:
            break

    if verbose:
        report( "\taction required : %s"%(not (prelim)) )
    return not (prelim)

def gstlal_eventcreation( gdb, gdb_id, verbose=False ):
    """
    checks that all expected data is present for newly created gstlal events.
    This includes:
        inspiral_coinc table
        psd estimates from the detectors
    """
#    files = gdb.files( gdb_id )
    if verbose:
        report( "%s : gstlal_eventcreation"%(gdb_id) )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    psd = False
    coinc = False
    for log in logs:
        comment = log['comment']
        if "strain spectral densities" in comment:
            psd = True
        elif "Coinc Table Created" in comment:
            coinc = True

        if psd and coinc:
            break

    if verbose:
        report( "\taction required : %s"% (not (psd and coinc)) )
    return not (psd and coinc)

def mbta_eventcreation( gdb, gdb_id, verbose=False ):
    """
    checks that all expected data is present for newly created mbta events.
    This includes:
        the "original data" file
    """
    if verbose:
        report( "%s : mbta_eventcreation"%(gdb_id) )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    psd = False
    coinc = False
    for log in logs:
        comment = log['comment']
        if "Coinc Table Created" in comment:
            coinc = True
        if "PSDs" in comment:
            psd = True

        if (psd and coinc):
            break

    if verbose:
        report( "\taction required : %s"%( not (psd and coinc)) )
    return not (psd and coinc)

#=================================================
# methods that check whether idq processes were triggered and completed
#=================================================

def idq_start( gdb, gdb_id, ifos=['H','L'], verbose=False ):
    """
    check that iDQ processes were started at each of the specified ifos
    """

    if verbose:
        report( "%s : idq_start"%(gdb_id) )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log'] ### retrieve the log messages attached to this event

    if verbose:
        report( "\tparsing log" )
    result = [1]*len(ifos)
    for log in logs:
        comment = log['comment']
        if ("Started searching for iDQ information" in comment):
            for ind, ifo in enumerate(ifos):
                if result[ind] and (ifo in comment):
                    result[ind] = 0
    
    if verbose:
        action_required = False
        for r, ifo in zip(result, ifos):
            if r:
                report( "\tWARNING: no idq_start statement found for ifo : %s"%ifo )
                action_required = True
            else:
                report( "\tidq_start statement found for ifo : %s"%ifo )
        report( "\taction required : %s"% action_required )

    return sum(result) > 0

def idq_finish( gdb, gdb_id, ifos=['H','L'], verbose=False ):
    """
    check that iDQ processes finished at each of the specified ifos
    """
    if verbose:
        report( "%s : idq_finish"%(gdb_id) )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    result = [1]*len(ifos)
    for log in logs:
        comment = log['comment']
        if ("Finished searching for iDQ information" in comment):
            for ind, ifo in enumerate(ifos):
                if result[ind] and (ifo in comment):
                    result[ind] = 0

    if verbose:
        action_required = False
        for r, ifo in zip(result, ifos):
            if r:
                report( "\tWARNING: no idq_finish statement found for ifo : %s"%ifo )
                action_required = True
            else:
                report( "\tidq_finish statement found for ifo : %s"%ifo )
        report( "\taction required : %s"%action_required )

    return sum(result) > 0

def idq_timeseries( gdb, gdb_id, ifos=['H', 'L'], verbose=False, minfap_statement=True ):
    """
    check that iDQ timeseries jobs completed at each site
    checks for the presences of "idq_fap.gwf" files in GDB
    Also checks for absence of FAILED statements 
    """
    if verbose:
        report( "%s : idq_timeseries"%(gdb_id) )
        report( "\tretrieving files" )
    files = gdb.files( gdb_id ).json().keys() ### we only care about filenames

    if verbose:
        report( "\tchecking filenames" )
    result = [1]*len(ifos)
    for filename in files:
        # H1_idq_ovl_fap_T176444-1124114448-16.gwf
        if filename.endswith(".gwf") and ("_idq_" in filename) and ("_fap_" in filename):
            for ind, ifo in enumerate(ifos):
                if result[ind] and (ifo in filename):
                    result[ind] = 0

    if verbose:
        for r, ifo in zip(result, ifos):
            if r:
                report( "\tWARNING: no idq_fap.gwf found for ifo : %s"%ifo )
            else:
                report( "\tidq_fap.gwf found for ifo : %s"%ifo )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    log_result = [0]*len(ifos)
    for log in logs:
        comment = log['comment']
        if ("FAILED: iDQ glitch-rank timeseries for" in comment):
            for ind, ifo in enumerate(ifos):
                if (1 - log_result[ind]) and (ifo in comment):
                    log_result[ind] = 1
                       
    if verbose:
        for r, ifo in zip(log_result, ifos):
            if r:
                report( "\tWARNING: idq timeseries FAILED message found for ifo : %s"%ifo )
            else:
                report( "\tno idq timeseries FAILED message found for ifo : %s"%ifo )

    action_required = sum(result) + sum(log_result) > 0
    if verbose:
        report( "\taction required : %s"% action_required )

    return action_required


def idq_tables( gdb, gdb_id, ifos=['H', 'L'], verbose=False ):
    """
    checks that iDQ tables jobs completed at each site
    checks for the presences of "idq_fap.gwf" files in GDB
    Also checks for absence of FAILED statements 
    """
    if verbose:
        report( "%s : idq_tables"%(gdb_id) )
        report( "\tretrieving files" )
    files = gdb.files( gdb_id ).json().keys() ### we only care about filenames

    if verbose:
        report( "\tchecking filenames" )
    result = [1]*len(ifos)
    for filename in files:
        #  H1_idq_ovl_T176i444-1124114453-10.xml.gz
        if filename.endswith(".xml.gz") and ("_idq_" in filename):
            for ind, ifo in enumerate(ifos):
                if result[ind] and (ifo in filename):
                    result[ind] = 0

    if verbose:
        for r, ifo in zip(result, ifos):
            if r:
                report( "\tWARNING: no idq.xml.gz found for ifo : %s"%ifo )
            else:
                report( "\tidq.xml.gz found for ifo : %s"%ifo )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']  

    if verbose:
        report( "\tparsing log" )
    log_result = [0]*len(ifos)
    for log in logs:
        comment = log['comment']
        if ("FAILED: iDQ glitch tables for" in comment):
            for ind, ifo in enumerate(ifos):
                if (1 - log_result[ind]) and (ifo in comment):
                    log_result[ind] = 1

    if verbose:
        for r, ifo in zip(log_result, ifos):
            if r:
                report( "\tWARNING: idq glitch tables FAILED message found for ifo : %s"%ifo )
            else:
                report( "\tno idq glitch tables FAILED message found for ifo : %s"%ifo )

    action_required = sum(result) + sum(log_result) > 0
    if verbose:
        report( "\taction_required : %s"% action_required )

    return action_required

#=================================================
# methods that check whether cWB processes wer triggered and completed
#=================================================

def cwb_skymap( gdb, gdb_id, lvem=None, verbose=False ):
    """
    checks that cwb skymaps are uploaded
    """
    if verbose:
        report( "%s: cwb_skymap"%(gdb_id) )

    if verbose:
        report( "\tretrieving event files" )
    files = sorted(gdb.files( gdb_id ).json().keys()) ### we really just care about the filenames

    if verbose:
        report( "\tchecking for cWB FITS file" )
    for filename in files:
        if "skyprobcc_cWB.fits" == filename: ### may be fragile
            if verbose:
                report( "\t\tfound : %s"%(filename) )
            if lvem!=None:
                if verbose:
                    report( "\t\tchecking for lvem tag" )
                if file_has_tag( gdb, gdb_id, filename, "lvem", verbose=False ) != lvem:
                    if verbose:
                        report( "\taction required : True" )
                    return True
            if verbose:
                report( "\taction required : False" )
            return False

    if verbose:
        report( "\taction required : True" )
    return True

#=================================================
# methods that check whether lib processes were triggered and completed
#=================================================

def lib_start( gdb, gdb_id, far=None, verbose=False ):
    """
    checks that LIB PE followup processes started (and were tagged correctly?)
    """
    if verbose:
        report( "%s : lib_start"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if "LIB Parameter estimation started." in comment:
            if verbose:
                report( "\taction required : False" )
            return False

    if verbose:
        report( "\taction required : True" )

    return True

def lib_finish( gdb, gdb_id, far=None, verbose=False ):
    """
    checks that LIB PE followup processes finished (and were tagged correctly?)
    """
    if verbose:
        report( "%s : lib_finish"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if "LIB Parameter estimation finished." in comment:
            if verbose:
                report( "\taction required : False" )
            return False
    if verbose:
        report( "\taction required : True" )
    return True

def lib_skymap( gdb, gdb_id, far=None, lvem=None, verbose=False ):
    """
    checks that LIB uploaded the expected FITS file
    """
    if verbose:
        report( "%s: lib_skymap"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving event files" )
    files = sorted(gdb.files( gdb_id ).json().keys()) ### we really just care about the filenames

    if verbose:
        report( "\tchecking for LIB FITS file" )
    for filename in files:
        if "LIB_skymap.fits.gz" == filename: ### may be fragile
            if verbose:
                report( "\t\tfound : %s"%(filename) )
            if lvem!=None:
                if verbose:
                    report( "\t\tchecking for lvem tag" )
                if file_has_tag( gdb, gdb_id, filename, "lvem", verbose=False ) != lvem:
                    if verbose:
                        report( "\taction required : True" )
                    return True
            if verbose:
                report( "\taction required : False" )
            return False

    if verbose:
        report( "\taction required : True" )
    return True

#=================================================
# methods that check whether bayeswave processes were triggered and completed
#=================================================

def bayeswave_start( gdb, gdb_id, far=None, verbose=False ):
    """
    checks that BayesWave PE processes started (and were tagged correctly?)
    """
    if verbose:
        report( "%s : bayeswave_start"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if "BayesWaveBurst launched" in comment:
            if verbose:
                report( "\taction required : False" )
            return False
    if verbose:
        report( "\taction required : True" )
    return True

def bayeswave_finish( gdb, gdb_id, far=None, verbose=False ):
    """
    checks that BayesWave PE processes finished (and were tagged correctly?)
    """
    if verbose:
        report( "%s : bayeswave_finish"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" ) 
            return False

    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if "BWB Follow-up results" in comment:
            if verbose:
                report( "\taction required : False" )
            return False
    if verbose:
        report( "\taction required : True" )
    return True

def bayeswave_skymap( gdb, gdb_id, far=None, lvem=None, verbose=False ):
    """
    checks that BayesWave uploaded the expected FITS file
    """
    if verbose:
        report( "%s: bayeswave_skymap"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False
    
    if verbose:
        report( "\tretrieving event files" )
    files = sorted(gdb.files( gdb_id ).json().keys()) ### we really just care about the filenames

    if verbose:
        report( "\tchecking for BayesWave FITS file" )
    for filename in files:
        if ("skymap_" in filename) and filename.endswith(".fits"): ### may be fragile
            if verbose:
                report( "\t\tfound : %s"%(filename) )
            if lvem!=None:
                if verbose:
                    report( "\t\tchecking for lvem tag" )
                if file_has_tag( gdb, gdb_id, filename, "lvem", verbose=False ) != lvem:
                    if verbose:
                        report( "\taction required : True" )
                    return True
            if verbose:
                report( "\taction required : False" )
            return False

    if verbose:
        report( "\taction required : True" )
    return True

#=================================================
# methods that check whether bayestar processes were triggered and completed
#=================================================

def bayestar_start( gdb, gdb_id, far=None, verbose=False ):
    """
    checks that BAYESTAR processes started (and were tagged correctly?)
    """
    if verbose:
        report( "%s : bayestar_start"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if "INFO:BAYESTAR:starting sky localization" in comment:
            if verbose:
                report( "\taction required : False" )
            return False
    if verbose:
        report( "\taction required : True" )
    return True

def bayestar_finish( gdb, gdb_id, far=None, verbose=False ):
    """
    checks that BAYESTAR processes finished (and were tagged correctly?)
    """
    if verbose:
        report( "%s : bayestar_finish"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if "INFO:BAYESTAR:sky localization complete" in comment:
            if verbose:
                report( "\taction required : False" )
            return False
    if verbose:
        report( "\taction required : True" )
    return True

def bayestar_skymap( gdb, gdb_id, far=None, lvem=None, verbose=False ):
    """
    checks that Bayestar uploaded the expected FITS file
    """
    if verbose:
        report( "%s: bayestar_skymap"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving event files" )
    files = sorted(gdb.files( gdb_id ).json().keys()) ### we really just care about the filenames

    if verbose:
        report( "\tchecking for Bayestar FITS file" )
    for filename in files:
        if "skymap.fits.gz" == filename: ### may be fragile
            if verbose:
                report( "\t\tfound : %s"%(filename) )
            if lvem!=None:
                if verbose:
                    report( "\t\tchecking for lvem tag" )
                if file_has_tag( gdb, gdb_id, filename, "lvem", verbose=False ) != lvem:
                    if verbose:
                        report( "\taction required : True" )
                    return True
            if verbose:
                report( "\taction required : False" )
            return False

    if verbose:
        report( "\taction required : True" )
    return True

#=================================================
# methods that check whether lalinference processes were triggered and completed
#=================================================

def lalinference_start( gdb, gdb_id, far=None, verbose=False ):
    """
    checks that LALInference PE processes started (and were tagged correctly?)
    """
    if verbose:
        report( "%s : lalinference_start"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if "LALInference online parameter estimation started" in comment:
            if verbose:
                report( "\taction required : False" )
            return False
    if verbose:
        report( "\taction required : True" )
    return True

def lalinference_finish( gdb, gdb_id, far=None, verbose=False ):
    """
    checks that LALInference PE processes finished (and were tagged correctly?)
    """
    if verbose:
        report( "%s : lalinference_finish"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if "LALInference online parameter estimation finished" in comment:
            if verbose:
                report( "\taction required : False" )
            return False
    if verbose:
        report( "\taction required : True" )
    return True

def lalinference_skymap( gdb, gdb_id, far=None, lvem=None, verbose=False ):
    """
    checks that LALInference uploaded the expected FITS file
    """
    if verbose:
        report( "%s: lalinference_skymap"%(gdb_id) )

    if far!=None:
        if verbose:
            report( "\tchecking far" )
        if far_check( gdb, gdb_id, verbose=False, minFAR=0.0, maxFAR=far ):
            report( "\tFAR > %.6e or not defined, event will be ignored"%(far) )
            report( "\taction required : False" )
            return False

    if verbose:
        report( "\tretrieving event files" )
    files = sorted(gdb.files( gdb_id ).json().keys()) ### we really just care about the filenames

    if verbose:
        report( "\tchecking for LALInference FITS file" )
    for filename in files:
#        if ("lalinference_" in filename) and filename.endswith(".fits.gz"):
        if "LALInference_skymap.fits.gz" == filename: ### may be fragile
            if verbose:
                report( "\t\tfound : %s"%(filename) )
            if lvem!=None:
                if verbose:
                    report( "\t\tchecking for lvem tag" )
                if file_has_tag( gdb, gdb_id, filename, "lvem", verbose=False ) != lvem:
                    if verbose:
                        report( "\taction required : True" )
                    return True
            if verbose:
                report( "\taction required : False" )
            return False

    if verbose:
        report( "\taction required : True" )
    return True

#=================================================
# tasks managed by gracedb.processor through grinch
#=================================================

def externaltriggers_search( gdb, gdb_id, verbose=False ):
    """
    checks that external trigger searches were performed
    """
    if verbose:
        report( "%s : externaltriggers_search"%(gdb_id) )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if "Coincidence search complete" in comment:
            if verbose:
                report( "\taction required : False" )
            return False
    if verbose:
        report( "\taction required : True" )
    return True

def unblindinjections_search( gdb, gdb_id, verbose=False ):
    """
    checks that unblind injection search was performed
    """
    if verbose:
        report( "%s : unblindinjections_search"%(gdb_id) )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if ("No unblind injections in window" in comment):
            if verbose:
                report( "\taction required : False" )
            return False

    report( "\tWARNING: we do not currently know how to parse out statements when there is an unblind injection...proceeding assuming everything is kosher" )

    if verbose:
        report( "\taction required : False" )
    return False

def plot_skymaps( gdb, gdb_id, check_tags=True, verbose=False ):
    """
    checks that all FITS files attached to this event have an associated png file (produced by gdb_processor)
    """
    if verbose:
        report( "%s : plot_skymaps"%(gdb_id) )
        report( "\tretrieving event files" )
    files = gdb.files( gdb_id ).json().keys() ### we really just care about the filenames

    if verbose:
        report( "\tidentifying all FITS files" )
    fitsfiles = [ filename for filename in files if filename.endswith(".fits") or filename.endswith(".fits.gz") ]

    if verbose:
        report( "\tchecking for corresponding png figures" )
    result = []
    for fitsfile in fitsfiles:
        pngfile = "%s.png"%(fitsfile.split(".")[0])
        if pngfile in files:
            if check_tags:
                result.append( (False, not tags_match( gdb, gdb_id, pngfile, fitsfile, verbose=False ), pngfile, fitsfile) )
            else:
                result.append( (False, False, pngfile, fitsfile) )
        else:
            result.append( (True, True, pngfile, fitsfile) )

    if verbose:
        action_required = False
        for r, m, pngfile, fitsfile in result:
            if r:
                report( "\tWARNING: no png file found for FITS : %s <-> %s"%(fitsfile, pngfile) )
                action_required = True
            elif m:
                report( "\tWARNING: png tags and FITS tags do not match : %s <-> %s"%(fitsfile, pngfile) )
                action_required = True
            else:
                report( "\tpng file found for FITS : %s <-> %s"%(fitsfile, pngfile) )
        report( "\taction required : %s"% action_required )

    return sum([r[0] for r in result]) > 0

#=================================================
# tasks managed by skyviewer and friends
#=================================================

def json_skymaps( gdb, gdb_id, check_tags=True, verbose=False ):
    """
    checks that all FITS files attached to this event have an associated json file
    """
    if verbose:
        report( "%s : json_skymaps"%(gdb_id) )
        report( "\tretrieving event files" )
    files = gdb.files( gdb_id ).json().keys() ### get just the names, not the urls

    if verbose:
        report( "\tidentifying all FITS files" )
    fitsfiles = [filename for filename in files if filename.endswith(".fits") or filename.endswith(".fits.gz") ]

    if verbose:
        report( "\tchecking for corresponding json files" )
    result = []
    for fitsfile in fitsfiles:
        if fitsfile.endswith(".gz"):
            jsonfile = "%sjson"%(fitsfile[:-7])
        else:
            jsonfile = "%sjson"%(fitsfile[:-4])
        if jsonfile in files:
            if check_tags:
                result.append( (False, not tags_match( gdb, gdb_id, jsonfile, fitsfile, verbose=False ), jsonfile, fitsfile) )
            else:
                result.append( (False, False, jsonfile, fitsfile) )
        else: 
            result.append( (True, False, jsonfile, fitsfile) )

    if verbose:
        action_required = False
        for r, m, jsonfile, fitsfile in result:
            if r:
                report( "\tWARNING: no json file found for FITS : %s <-> %s"%(fitsfile, jsonfile) )
                action_required = True
            elif m:
                report( "\tWARNING: json tags and FITS tags do not match : %s <-> %s"%(fitsfile, jsonfile) )
                action_required = True
            else:
                report( "\tjson file found for FITS : %s <-> %s"%(fitsfile, jsonfile) )
        report( "\taction required : %s"% action_required )

    return sum([r[0] for r in result]) > 0

#=================================================
# tasks managed by approval_processor
#=================================================

def approval_processor_far( gdb, gdb_id, verbose=False ):
    """
    checks whether approval_processor has check the FAR of this event and responded in the GraceDB log
    """
    if verbose:
        report( "%s : approval_proccesor_far"%(gdb_id) )
        report( "\tretrieving log messages" )
    logs = gdb.logs( gdb_id ).json()['log']

    if verbose:
        report( "\tparsing log" )
    for log in logs:
        comment = log['comment']
        if ("Candidate event has low enough FAR" in comment) or ("Candidate event rejected due to large FAR" in comment):
            if verbose:
                report( "\taction required : False" )
            return False
    if verbose:
        report( "\taction required : True" )
    return True










def emready_label( gdb, gdb_id, verbose=False ):
    """
    checks whether the event has been labeled emready and if there is at least one FITS file attached to the event

    MISSING LOGIC: iDQ check, FAR check

    """
    if verbose:
        report( "%s : emready_label"%(gdb_id) )
        report( "\tretrieving event files" )
    files = gdb.files( gdb_id ).json().keys()

    if verbose:
        report( "\tidentifying all FITS files" )
    fitsfiles = [filename for filename in files if filename.endswith(".fits") or filename.endswith(".fits.gz")]

    if verbose:
        report( "\tretrieving labels" )
    labels = [label['name'] for label in gdb.labels( gdb_id ).json()['labels']]
    emready = "EM_READY" in labels
    
    if emready and fitsfiles:
        if verbose:
            report( "\t%d FITS files found (%s) and event labeled \"EM_READY\""%(len(fitsfiles), ", ".join(fitsfiles)) )
        action_required = False
    elif emready:
        if verbose:
            report( "\tevent labeled \"EM_READY\" but no FITS files were found" )
        action_required = True
    elif fitsfiles:
        if verbose:
            report( "\t%d FITS files found (%s) but event not labeled \"EM_READY\""%(len(fitsfiles), ", ".join(fitsfiles)) )
        action_required = True
    else:
        if verbose:
            report( "\tno FITS files found and event not labeled \"EM_READY\"" )
        action_required = False

    if verbose:
        report( "\taction required : %s"% action_required )

    report( "WARNING: missing logic" )

    raise StandardError
    return action_required

def peready_label( gdb, gdb_id, verbose=False, pe_pipelines="lib bayeswave lalinference".split() ):
    """
    checks whether the event has been labeled peready and if the associated follow-up jobs have completed

    MISSING LOGIC: iDQ check, FAR check

    """
    if verbose:
        report( "%s : peready_label"%(gdb_id) )

    if len(pe_pipelines) < 1:
        raise ValueError("must specify at least one pe_finish_check")

    ### check pipelines for finish statements
    if verbose:
        report( "\tchecking for pe_finish log messages from:" )
    pe_finish = {}
    for check in pe_pipelines:
        if verbose:
            report( "\t\t%s"%(check) )

        if check == "lib":
            pe_finish['lib'] = not lib_finish( gdb, gdb_id, verbose=False )
        elif check == "bayeswave":
            pe_finish['bayeswave'] = not bayeswave_finish( gdb, gdb_id, verbose=False )
        elif check == "lalinference":
            pe_finish['lalinference'] = not lalinference_finish( gdb, gdb_id, verbose=False )
        else:
            raise ValueError("pe_finish_check=%s not understood"%pe_finish_check)

    pe_finished = np.any(pe_finish.values())
    pe_keys = [key for key, value in pe_finish.items() if value]

    if verbose:
        report( "\tretrieving labels" )
    labels = [label['name'] for label in gdb.labels( gdb_id ).json()['labels']]
    peready = "PE_READY" in labels

    if peready and pe_finished:
        if verbose:
            report( "\t%d PE jobs reporting (%s) and event labeled \"PE_READY\""%(len(pe_keys), ", ".join(pe_keys)) )
        action_required = False
    elif peready:
        if verbose:
            report( "\tevent labeled \"PE_READY\" but no PE jobs reporting" )
        action_required = True
    elif pe_finished:
        if verbose:
            report( "\t%d PE jobs reporting (%s) but event not labeled \"PE_READY\""%(len(pe_keys), ", ".join(pe_keys)) )
        action_required = True
    else:
        if verbose:
            report( "\tno PE jobs reporting and event not labeled \"PE_READY\"" )
        action_required = False

    if verbose:
        report( "\taction required : %s"% action_required )

    report( "WARNING: missing logic" )

    raise StandardError
    return action_required

def dqveto_label( gdb, gdb_id, verbose=False ):
    """

    LOGIC: either iDQ vetoes the event or human sign-off says "FAIL"

    """

    report( "WARNING: WRITE ME" )

    raise StandardError
    return False

def dqwarning_label( gdb, gdb_id, verbose=False ):
    report( "WARING: WRITE ME" )

    raise StandardError
    return False

def voevent_creation( gdb, gdb_id, verbose=False ):
    """

    checks to make sure VOEvents are created as expected 
        if event is created, make sure we've created a preliminary VOEvent (need FAR thresholds?)
        if event is labeled EM_READY, make sure we've created an initial VOEvent
        if event is labeled PE_READY, make sure we've created an updated VOEvent

    instead, just trigger off of FITS files?
        count the number of fits files and check for associated VOEvent xml files.
        check both the number and the types?
        possible exception with "retractions" => num(FITS) != num(VOEvent xml)
    """

    report( "WARNING: WRITE ME" )

    raise StandardError
    return False

def voevent_sent( gdb, gdb_id, verbose=False ):
    """
    NOT YET WRITTEN
    """

    report( "WARNING: WRITE ME" )

    raise StandardError
    return False
