import subprocess
import re
import operator
import functools
import os
import random
import time
import datetime

ts = time.time()
st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

#--------------------------------------------------------------------------------------
# Utilities
#--------------------------------------------------------------------------------------

# A utility to get the FAR threshold given pipeline and search.
# It's probably important to have a default value just in case.
def get_farthresh(config, pipeline, search):
	try:
		return config.getfloat('default', 'farthresh[{0}.{1}]'.format(pipeline, search))
	except:
		return config.getfloat('default', 'default_farthresh')

# A utility to get the iDQ joint min-FAP threshold given pipeline and search.
# It's probably important to have a default value just in case.
def get_idqthresh(config, pipeline, search):
	try:
		return config.getfloat('default', 'idqthresh[{0}.{1}]'.format(pipeline, search))
	except:
		return config.getfloat('default', 'default_idqthresh')

# Define a function for pulling down and sending out the correct VOEvent depending on label type
def process_alert(client, logger, graceid, voevent_type, skymap_filename=None, 
	skymap_type=None, skymap_image_filename=None):
	logger.info("{0} -- {1} -- Processing {2} VOEvent.".format(st, graceid, voevent_type))

	# Create the VOEvent.
	voevent = None
	try:
		r = client.createVOEvent(graceid, voevent_type, skymap_filename=skymap_filename, 
			skymap_type=skymap_type, skymap_image_filename=skymap_image_filename)
		voevent = r.json()['text']
	except Exception, e:
		logger.info("{0} -- {1} -- Caught HTTPError: {2}".format(st, graceid, str(e)))
	number = str(random.random())
	if voevent:
		tmpfile = open('/tmp/voevent_{0}_{1}.tmp'.format(graceid, number),"w")
		tmpfile.write(voevent)
		tmpfile.close()
		# Send it out with comet!
		cmd = 'comet-sendvo -p 5340 -f /tmp/voevent_{0}_{1}.tmp'.format(graceid, number)
		proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		output, error = proc.communicate(voevent)
		logger.debug('{0} -- {1} -- output = {2}.'.format(st, graceid, output))
		logger.debug('{0} -- {1} -- error = {2}.'.format(st, graceid, error))

	if proc.returncode == 0:
		message = '{0} VOEvent sent to GCN for testing purposes.'.format(voevent_type)
		r = client.writeLog(graceid, 'AP: Successfully sent VOEvent of type {0}.'.format(voevent_type), tagname='em_follow')
	else:
		message = 'Error sending {0} VOEvent! {1}.'.format(voevent_type, error)
		r = client.writeLog(graceid, 'AP: Could not send VOEvent of type {0}.'.format(voevent_type), tagname='em_follow')
	logger.debug('{0} -- {1} -- message = {2}.'.format(st, graceid, message))
	os.remove('/tmp/voevent_{0}_{1}.tmp'.format(graceid, number))

# Define a function that checks for the human scimon signoffs
def checkSignoffs(client, logger, graceid, detectors):
	log_dicts = client.logs(graceid).json()['log']
	for message in log_dicts:
		if 'Finished running human signoff checks.' in message['comment']:
			passorfail = re.findall(r'Candidate event (.*)ed human signoff checks.', message['comment'])
			if passorfail[0]=='pass':
				return 'Pass'
			elif passorfail[0]=='fail':
				return 'Fail'
		else:
			pass 
	# Construct the URL for the operator signoff list
	url = client.templates['operatorsignoff-list-template'].format(graceid=graceid)
	# Pull down the operator signoff list
	signoff_list = client.get(url).json()['operator_signoff']
	# Use the list to construct the signoff results dictionary
	signoffdict = {}
	for signoff in signoff_list:
		signoffdict[signoff['instrument']] = 'Pass' if signoff['status']=='OK' else 'Fail'
	# Now use the signoffdict to do the check
	if (len(signoffdict) < len(detectors)):
		if ('Fail' in signoffdict.values()):
			return 'Fail'
		else:
			logger.info('{0} -- {1} -- Have not gotten all the human signoffs yet but not yet DQV.'.format(st, graceid))
			return 'Unknown'
	elif (len(signoffdict) > len(detectors)):
		logger.info('{0} -- {1} -- Too many human signoffs in the signoff dictionary.'.format(st, graceid))
		return 'Unknown'
	else:
		logger.info('{0} -- {1} -- Ready to run human signoff check.'.format(st, graceid))
		if ('Fail' in signoffdict.values()):
			return 'Fail'
		else:
			return 'Pass'

# Define a function that checks for the advocate signoff
def checkAdvocateSignoff(client, logger, graceid):
	log_dicts = client.logs(graceid).json()['log']
	for message in log_dicts:
		if 'Finished running advocate check.' in message['comment']:
			passorfail = re.findall(r'Candidate event (.*)ed advocate check.', message['comment'])
			if passorfail[0]=='pass':
				return 'Pass'
			elif passorfail[0]=='fail':
				return 'Fail'
		else:
			pass 
	# Construct the URL for the signoff list
	url = client.templates['signoff-list-template'].format(graceid=graceid)
	# Pull down the operator signoff list
	signoff_list = client.get(url).json()['signoff']
	# Use the list to construct the signoff results dictionary
	signoffdict = {}
	for signoff in signoff_list:
		if signoff['instrument']=='':
			signoffdict[signoff['instrument']] = 'Pass' if signoff['status']=='OK' else 'Fail'
		else:
			pass
	# Now use the signoffdict to do the check
	if (len(signoffdict) > 1):
		logger.info('{0} -- {1} -- More than one advocate signoff in the signoff dictionary.'.format(st, graceid))
		return 'Unknown'
	elif (len(signoffdict) < 1):
		logger.info('{0} -- {1} -- No advocate signoff in the signoff dictionary.'.format(st, graceid))
		return 'Unknown'
	else:
		logger.info('{0} -- {1} -- Ready to run advocate signoff check.'.format(st, graceid))
		if ('Fail' in signoffdict.values()):
			return 'Fail'
		else:
			return 'Pass'

# Define a function that disqualifies an event for being and INJ or DQV. 
# This function depends on the value of hardware_inj in the config file
# hardware_inj == 'yes' means we treat hardware injections are real events
def checkLabels(hardware_inj, labels):
	if hardware_inj == 'yes':
		badlabels = ['DQV']
	else:
		badlabels = ['DQV','INJ']
	# Create a list of the intersection of our badlabels list and the event labels
	intersectionlist = list(set(badlabels).intersection(labels))
	# If the length of the intersection list is greater than 0, then our event is either DQV or INJ (if hardware_inj == 'no')
	return len(intersectionlist)

def checkIdqStatus(client, graceid):
	log_dicts = client.logs(graceid).json()['log']
	for log_dict in log_dicts:
		comment = log_dict['comment']
		if 'Candidate event passed iDQ checks.' in comment:
			return 'Pass'
		elif 'Candidate event rejected due to low iDQ FAP' in comment:
			return 'Fail'
	return 'Unknown'

def getIdqAndJointFapValues(idq_pipelines, client, logger, graceid):
	idqvalues = {}
	joint_FAP_values = {}
	for pipeline in idq_pipelines:
		pipeline_values = []
		log_dicts = client.logs(graceid).json()['log']
		commentslist = open('/tmp/idqmessages_{0}.tmp'.format(graceid), 'w')
		for message in log_dicts:
			if re.match('minimum glitch-FAP', message['comment']):
				commentslist.write(message['comment'])
				commentslist.write('\n')
		commentslist.close()

		# Now we get the min-FAP values and sort according to which idq_pipeline
		commentslist = open('/tmp/idqmessages_{0}.tmp'.format(graceid))
		for line in commentslist:
			idqinfo = re.findall('minimum glitch-FAP for (.*) at (.*) with', line)
			pipeline = idqinfo[0][0]
			detector = idqinfo[0][1]
			min_fap = re.findall('is (.*)\n', line)
			min_fap = float(min_fap[0])
			detectorstring = '{0}.{1}'.format(pipeline, detector)
			idqvalues[detectorstring] = min_fap
			logger.info('{0} -- {2} -- Got the min_fap for {1} using {3} is {4}.'.format(st, detector, graceid, pipeline, min_fap))
		commentslist.close()

		# Now, even if you did not get all the minfap values for a specific pipeline, 
	    # calculate the joint min-FAP thus far for each pipeline 
		for key in idqvalues.keys(): 
			if pipeline in key:
				pipeline_values.append(idqvalues[key])
		joint_FAP_values[pipeline] = functools.reduce(operator.mul, pipeline_values, 1)

		return idqvalues, joint_FAP_values
	os.remove('/tmp/idqmessages_{0}.tmp'.format(graceid))

