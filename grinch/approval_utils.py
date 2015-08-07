import subprocess
import re

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

# Define a function for pulling down and sending out the correct VOEvent depending on label type

def process_alert(client, logger, graceid, voevent_type, skymap_filename=None, 
	skymap_type=None, skymap_image_filename=None):
	logger.info("Processing %s VOEvent for MDC event %s .... " % (voevent_type, graceid))

	# Create the VOEvent.
	voevent = None
	try:
		r = client.createVOEvent(graceid, voevent_type, skymap_filename=skymap_filename, 
			skymap_type=skymap_type, skymap_image_filename=skymap_image_filename)
		voevent = r.json()['text']
	except HTTPError, e:
		logger.info("Caught HTTPError: %s" % str(e))
	if voevent:
		tmpfile = open('/tmp/voevent_%s.tmp' % graceid,"w")
		tmpfile.write(voevent)
		tmpfile.close()
		# Send it out with comet!
		cmd = "comet-sendvo -p 5340 -f /tmp/voevent_%s.tmp" % graceid
		proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		output, error = proc.communicate(voevent)
		logger.debug("output = %s" % output)
		logger.debug("error = %s" % error)

	if proc.returncode == 0:
		message = "%s VOEvent sent to GCN for testing purposes." % voevent_type
		r = client.writeLog(graceid, 'Successfully sent VOEvent of type %s.' % voevent_type, tagname='em_follow')
	else:
		message = "Error sending %s VOEvent! %s" % (voevent_type, error)
		r = client.writeLog(graceid, 'Could not send VOEvent of type %s.' % voevent_type, tagname='em_follow')
	logger.debug(message)
	os.remove('/tmp/voevent_%s.tmp' % graceid)

# Define a function that checks for the human scimon signoffs
def checkSignoffs(client, logger, graceid, detectors):
	log_dicts = client.logs(graceid).json()['log']
	signoffdict = {}
	for message in log_dicts:
		if 'Finished running human signoff checks.' in message['comment']:
			passorfail = re.findall(r'Candidate event (.*?)ed human signoff checks.', message['comment'])
			if passorfail[0]=='pass':
				return 'Pass'
			elif passorfail[0]=='fail':
				return 'Fail'
		else:
			pass 
	for detector in detectors:
		filename = 'signoff_from_{0}.txt'.format(detector)
		try:
			signofftxt = client.files(graceid, filename)
			fails = re.findall(r'Fail',signofftxt.read())
			logger.info('Got the human scimon file for {0} from {1}.'.format(graceid, detector))
			if len(fails) > 0:
				signoffdict[detector] = 'Fail'
			else:
				signoffdict[detector] = 'Pass'
		except Exception, e:
			logger.error('Could not get human scimon file for {0} from {1}:{2}.'.format(graceid,detector, str(e)))
	if (len(signoffdict) < len(detectors)):
		logger.info('Have not gotten all the human signoffs yet but not yet DQV.')
		return 'Unknown'
	elif (len(signoffdict) > len(detectors)):
		logger.info('Too many human signoffs in signoff dictionary.')
		return 'Unknown'
	else:
		logger.info('Ready to run human signoff check for {0}.'.format(graceid))
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

def checkIdqStatus(client):
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
		commentslist = open('/tmp/idqmessages_%s.tmp' % graceid, 'w')
		for message in log_dicts:
			if re.match('minimum glitch-FAP', message['comment']):
				commentslist.write(message['comment'])
				commentslist.write('\n')
		commentslist.close()

		# Now we get the min-FAP values and sort according to which idq_pipeline
		commentslist = open('/tmp/idqmessages_%s.tmp' % graceid)
		for line in commentslist:
			idqinfo = re.findall('minimum glitch-FAP for (.*?) at (.*?) with', line)
			pipeline = idqinfo[0][0]
			detector = idqinfo[0][1]
			min_fap = re.findall('is (\S+)\n', line)
			min_fap = float(min_fap[0])
			detectorstring = '{0}.{1}'.format(pipeline, detector)
			idqvalues[detectorstring] = min_fap
			logger.info('Got the min_fap for {0} {1} using {2} is {3}.'.format(detector, graceid, pipeline, min_fap))
		commentslist.close()

		# Now, even if you did not get all the minfap values for a specific pipeline, 
	    # calculate the joint min-FAP thus far for each pipeline 
		for key in idqvalues.keys(): 
			if pipeline in key:
				pipeline_values.append(idqvalues[key])
		joint_FAP_values[pipeline] = functools.reduce(operator.mul, pipeline_values, 1)

		return idqvalues, joint_FAP_values
	os.remove('/tmp/idqmessages_%s.tmp' % graceid)

