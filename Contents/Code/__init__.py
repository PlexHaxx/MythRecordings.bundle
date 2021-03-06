# MythRecordings plug-in for Plex
# Copyright (C) 2013 Thomas Schaumburg
#
# This code is heavily inspired by the NextPVR bundle by David Cole.

import xml.etree.ElementTree as ET
import datetime
import urllib2
import json
import re

def L2(key):
	return str(L(key))

def F2(key, *args):
	return str(F(key, *args))

####################################################################################################
NAME = L2("TITLE")
PVR_URL = 'http://%s:%s/' % (Prefs['server'],Prefs['port'])
CACHE_TIME = int(Prefs['cacheTime'])
SERIES_SUPPORT = True

MYTHTV_BACKGROUND = 'mythtv-background.png'
MYTHTV_ICON = 'mythtv-icon.png'

BY_NAME_ICON  = 'by-name-icon.png'
BY_NAME_BACKGROUND  = 'by-name-background.png' # TODO: missing

BY_DATE_ICON  = 'by-date-icon.png'
BY_DATE_BACKGROUND  = 'by-date-background.png' # TODO: missing

BY_CATEGORY_ICON  = 'by-category-icon.png'
BY_CATEGORY_BACKGROUND  = 'by-category-background.png' # TODO: missing

UNKNOWN_SERIES_BACKGROUND = 'unknown-series-background.png' # TODO: missing
UNKNOWN_SERIES_ICON = 'unknown-series-icon.png' # TODO: missing


####################################################################################################
# Developer configurable data:
# ============================
# This section contains configuration that you only need to change if you change the code.
####################################################################################################

# ReadableKeyNames:
# =================
# Key names are XPATH expressions that are used to retrieve values (title, recording start time,
# etc.) from the XML metadata describing a recording.
#
# Sometimes, a screen needs to display the key used to organize data (such as a label saying
# "sort by xxx".
#
# In these cases, we need a simple way of getting a human-readable form of a key (after all,
# "sort by Recording/RecGroup" doesn't sound very approachable...)
#
# So: whenever you add a literal XPATH expression in a call to GroupRecordingsBy, you may
# want to add a human-readableform to the dictionary below.

ReadableKeyNames = \
    {
        "Recording/RecGroup": L2("RECORDING_GROUP"),
        "Channel/ChannelName": L2("CHANNEL_NAME"),
        "StartTime": L2("RECORDING_DATE")
    }

def GetReadableKeyName(keyname):
    if keyname in ReadableKeyNames.keys():
        return ReadableKeyNames[keyname]
    else:
        return keyname

####################################################################################################
# User configurable data:
# =======================
# This section contains configuration that a user may wish to configure according to taste and 
# needs.
# 
# This really belongs in the user preferences. But since preferences only handle simple types
# (bool, text,...), this proved unwieldy (editing a Python list-of-lists using a 4-button Roku
# remote control is ... interesting).
#
# So for now, these settings go in here. If you have a better idea, let me know.
####################################################################################################

# Title splitting
# ===============
# Sometimes the episodes of a series will include the subtitle in the title, which means that
# the episodes cannot be properly combined by title.
#
# For example, I may have recorded two episodes of the 2012 "Sherlock Holmes" season, with the
# following metadata:
#
#    {Title = "Sherlock Holmes - A Scandal in Belgravia", Subtitle = "British series, 2012"}
#    {Title = "Sherlock Holmes - The Hounds of Baskerville", Subtitle = "British series, 2012"}
#
# These do not match by title, and will not immediately be recognized as episodes of the same 
# series.
#
# But if you add "-" to the title splitters list below, the metadata will be reorganized as 
# follows:
#
#    {Title = "Sherlock Holmes", Subtitle = "A Scandal in Belgravia - British series, 2012"}
#    {Title = "Sherlock Holmes", Subtitle = "The Hounds of Baskerville - British series, 2012"}
#
# However, there are titles that SHOULD contain a splitter (such as "CSI: New York"). These
# titles are protected by adding a regular expression to the TITLE_NOSPLITTERS collection
#
TITLE_SPLITTERS = ['-', ':']
TITLE_NOSPLITTERS = ["^CSI: New York"]

# Category aliases
# ================
# When grouping recordings by category, the category names are not always consistent -
# often the category values deoend on the channel the recording was made from.
# 
# To avoid having the category list filled up with categories that only vary in spelling
# or language, the CategoryAliases list-of-lists below is used.
# 
# CategoryAliases is a list of alias lists. Each alias list consists of the canonical 
# name, followed by aliases.
#
# Whenever an alias value is met, it is reolaced with the corresponding canonical name.

CategoryAliases = \
	[
		[str(L2("SERIES")), "series", "serie"],
		[str(L2("CHILDREN")), "Children", "kids"], 
		[str(L2("DOCUMENTARY")), "documentary", "educational"], 
		[str(L2("UNCATEGORIZED")), "Uncategorized", ""]
	]



####################################################################################################

def Start():
    
	ObjectContainer.title1 = NAME
	Log('%s Started' % NAME)
	Log('URL set to %s' % PVR_URL)
	ValidatePrefs()

####################################################################################################
# MainMenu:
# =========
# Sets up the top-level menu.
#
# Returns:
#    ObjectContainer
####################################################################################################
@handler('/video/mythrecordings','MythTV recordings')
def MainMenu():
    dir=ObjectContainer(art = R(MYTHTV_BACKGROUND))

    # By title:
    dir.add(
        DirectoryObject(
            key=Callback(GroupRecordingsBy, groupByList=['Title'], staticBackground=BY_NAME_BACKGROUND), 
            title=L2('BY_TITLE'), 
            thumb=R(BY_NAME_ICON)
        )
    )
    
    # By category, then by title:
    dir.add(
        DirectoryObject(
            key=Callback(GroupRecordingsBy, groupByList=['Category', 'Title'], staticBackground=BY_CATEGORY_BACKGROUND), 
            title=L2('BY_CATEGORY'), 
            thumb=R(BY_CATEGORY_ICON)
        )
    )

    # By recording group:
    showByRecordingGroup = Prefs['showByRecordingGroup']
    if showByRecordingGroup:
        dir.add(
            DirectoryObject(
                key=Callback(GroupRecordingsBy, groupByList=['Recording/RecGroup']), 
                title=L2('BY_RECORDING_GROUP')
            )
        )

    # By channel name:
    showByChannelName = Prefs['showByChannelName']
    if showByChannelName:
        dir.add(
            DirectoryObject(
                key=Callback(GroupRecordingsBy, groupByList=['Channel/ChannelName']), 
                title=L2('BY_CHANNEL')
            )
        )

    # By recording date:
    dir.add(
        DirectoryObject(
            key=Callback(GetRecordingList, sortKeyName='StartTime', staticBackground=BY_DATE_BACKGROUND), 
            title=L2('BY_RECORDING_DATE'), 
            thumb=R(BY_DATE_ICON)
        )
    )

    # Preferences:
    dir.add(
        PrefsObject(
            title=L2("PREFERENCES"), 
            summary=L2("PREFERENCES_SUMMARY"), 
            thumb=R("icon-prefs.png")
        )
    )

    return dir


####################################################################################################
# GroupRecordingsBy:
# ==================
# Returns a tree-structure of all the recordings matching the specified filter.
#
# The recordings will be sorted into sub-directories according to the value of
# the group-by key. The group-by key is the first element of the groupBy
# list.
#
# Each sub-directory will have an icon (thumb) or background image (art) associated 
# with it.
#
# These images will be loaded from 
#    MythRecordings.bundle/Contents/Resources/${groupKey}Icon_%{groupValue}.png 
# and 
#    MythRecordings.bundle/Contents/Resources/${groupKey}Background_%{groupValue}.png 
# respectively.
#
# Returns:
#    ObjectContainer
#
#
# Experimental series handling:
# ------------------------------
# In case the group-by key is "Title", the set of recordings for each value of title
# will be searched for the "inetref" key, indicating that this is the episode of
# a series.
#
# If inetref exists, the icon and background images for that series will be retrieved
# from the MythTV server
#
####################################################################################################
@route('/video/mythrecordings/GroupRecordingsBy', filterBy = dict, groupByList = list, allow_sync=True) 
def GroupRecordingsBy(groupByList = [], filterBy = {}, seriesInetRef = None, staticBackground = None):
	Log("GroupRecordingsBy(groupByList = %s, filterBy = %s, seriesInetRef = %s, staticBackground = %s)" % (groupByList, filterBy, seriesInetRef, staticBackground))
	if groupByList is None:
		groupByList = []

	if filterBy is None:
		filterBy = {}

	if len(groupByList)==0:
		return GetRecordingList(filterBy=filterBy, sortKeyName='StartTime', seriesInetRef = seriesInetRef, staticBackground = staticBackground)
	
	groupByKey = groupByList[0]
	del groupByList[0]

	iconPrefix = "%sIcon_" % CamelCase(GetReadableKeyName(groupByKey))
	backgroundPrefix = "%sBackground_" % CamelCase(GetReadableKeyName(groupByKey))
	
	# Determine a good top-of-page title:
        title = MakeTitle(filterBy, groupByKey)

	# Find a background image:
	backgroundUrl = GetSeriesBackground(seriesInetRef, staticBackground)

	oc = ObjectContainer(title2=title, art=backgroundUrl) # title1 is not displayed (on most clients, anyway)
	
	# Get the recordings metadata from the MythTV backend:
	recordings = GetMythTVRecordings(filterBy)
	
	# Sort the recordings into a {string : list} dictionary
	entries = {}
	for recording in recordings:
		keyValue = GetField(recording, groupByKey)

		if not entries.has_key(keyValue):
			entries[keyValue] = []
		entries[keyValue].append(recording)

	# Loop through each of the keys and create a subdirectory entry:
	for subdirName in entries.keys():
                subdirFilterBy = filterBy.copy()
                subdirFilterBy[groupByKey] = subdirName

		subdirContents = entries[subdirName]
		entryTitle = "%s (%s)" % (subdirName, len(subdirContents))
		
		# Static background image for subdirectory entry:
		subdirStaticBackground = '%s%s.png' % (backgroundPrefix, CamelCase(subdirName))
		subdirStaticIcon = '%s%s.png' % (iconPrefix, CamelCase(subdirName))
		
		# Special case: see if this is the list of episodes in a series
		subSeriesInetRef = None
		if groupByKey == "Title":
			subSeriesInetRef = GetInetref(subdirContents)

		# Icon for subdirectory entry:		
		iconUrl = GetSeriesIcon(subSeriesInetRef, subdirStaticIcon)

		if len(subdirContents) == 1 and groupByKey == "Title": 
                        # Experimental:
                        # =============
                        # If the subdirectory we're about to create only contains a
                        # single entry, we'll save the extra level and just put the
                        # recording in.
			recording = subdirContents[0]
			oc.add(Recording(recording, seriesInetRef=subSeriesInetRef))
		else:
                        # Otherwise, we'll play it straight and put in a DirectoryObject
                        # referencing the next level down
			oc.add(
                            DirectoryObject(
                                key=
                                    Callback(
                                        GroupRecordingsBy,
                                        filterBy=subdirFilterBy,
                                        groupByList=groupByList,
                                        seriesInetRef=subSeriesInetRef,
					staticBackground = subdirStaticBackground
                                    ), 
                                title=entryTitle, 
                                thumb=iconUrl
                            )
                        )
		
	oc.objects.sort(key=lambda obj: obj.title)
	return oc


####################################################################################################
# Series meta-data:
# =================
# Get metadata about a series, as recorded by MythTV
####################################################################################################

def GetInetref(recordings):
	if not SERIES_SUPPORT:
		return None

	for recording in recordings:
		val = GetField(recording, 'Inetref')
		if not val is None:
			return val
	return None

def GetSeriesIcon(inetref, staticBackground):
	# We MUST have a fallback image:
	if staticBackground is None:
		staticBackground = UNKNOWN_SERIES_ICON

	result = InternalGetImage(inetref, staticBackground, UNKNOWN_SERIES_ICON)
	Log("ICON: %s" % result)
	return result

def GetSeriesBackground(inetref, staticBackground):
	# We MUST have a fallback image:
	if staticBackground is None:
		staticBackground = UNKNOWN_SERIES_BACKGROUND

	result = InternalGetImage(inetref, staticBackground, UNKNOWN_SERIES_BACKGROUND)
	Log("BACKGROUND: %s" % result)
	return result

def InternalGetImage(inetref, staticBackground, fallback):
	Log("InternalGetImage:")
	Log("   1: %s" % inetref)
	Log("   2: %s" % staticBackground)
	Log("   3: %s" % fallback)
	# We MUST have a fallback image:
	#if staticBackground is None:
	#	staticBackground = MYTHTV_BACKGROUND

	# If this is not defined as a series, return the static image:
	if inetref is None:
		#Log("InternalGetImage:")
		#Log("   1: %s" % staticBackground)
		#Log("   2: %s" % fallback)
		return R2(staticBackground, fallback)
		#return Resource.ContentsOfURLWithFallback(url = R(staticBackground), fallback = fallback)

	# OK, so it's a series - let's look for artwork:
	url = "%sContent/GetRecordingArtwork?Inetref=%s&Type=fanart" % (PVR_URL, inetref)

	#return Resource.ContentsOfURLWithFallback(url = [url, staticBackground], fallback = fallback)
	#return Resource.ContentsOfURLWithFallback(url = url, fallback = staticBackground)
	
	# Test if URL responds - otherwise fall back to static background:
	try:
		resourceVal = HTTP.Request(url, cacheTime = CACHE_TIME).content
	except:
		return R2(staticBackground, fallback)
		#return Resource.ContentsOfURLWithFallback(url = R(staticBackground), fallback = fallback)

	# If no artwork is defined on the MythTV server, an XML error message
	# is returned instead of an image.
	try:
		# To detect this, we try to parse the returned data as XML - which
		# will fail if it's a proper image:
		detail = ET.fromstring(resourceVal)
	except:
		# If parsing as XML failed, we'll assume it's binary image data,
		# and everything is OK:
		return url
	
	# We shouldn't ever get here, but to be on the safe side:
	return R2(staticBackground, fallback)
	#return Resource.ContentsOfURLWithFallback(url = R(staticBackground), fallback = fallback)
	
def R2(resource, fallback):
	return Callback(MakeImage2, resource=resource, fallback=fallback)

@route('/video/mythrecordings/MakeImage2') 
def MakeImage2(resource, fallback):
	try: 
		data = Resource.Load(resource) #HTTP.Request(R(resource), cacheTime = CACHE_1MONTH).content 
		if not data:
			Log("IMAGE: %s doesn't exist - falling back to %s" % (R(resource), fallback))
			return Redirect(R(fallback)) #Redirect(R(fallback))
		Log("IMAGE: returning %s" % resource)
		return Redirect(R(resource)) #DataObject(data, 'image/jpeg') 
	except:
		Log("IMAGE: %s doesn't exist - falling back to %s" % (R(resource), fallback))
 		return Redirect(R(fallback)) #Redirect(R(fallback))

####################################################################################################
# Title handling:
# ===============
####################################################################################################

def MakeTitle(filterBy, groupByKey):
    readableGroupByKey = GetReadableKeyName(groupByKey)
    if len(filterBy) == 0:
        title = F("BY1", readableGroupByKey)
    else:
        title = ""
        for filterKeyName, filterKeyNameValue in filterBy.items():
            readableFilterKeyName = GetReadableKeyName(filterKeyName)
            title = title + ', %s "%s"' % (readableFilterKeyName, filterKeyNameValue)
        title = title + ', ' + F2("BY2", readableGroupByKey)
        title = title[2:] # remove starting ", "
    return title

def CamelCase(src):
    result = re.sub(r'\W+', '', src.title())
    return result


####################################################################################################
# GetRecordingList:
# =================
# Creates a directory (ObjectContainer) listing all the recordings where the contents of the element
# identified by the filterKeyNames parameter (a lis of XPATH expressions) matches filterKeyValues. The
# values are subject to the same aliasing mechanism described for GroupRecordingsBy above.
#
# Each entry in the recording list will have an icon (thumb) that is a Preview Image from the recording,
# as supplied by MythTV.
#
# The resulting list of recordings is sorted by the element identified by the sortKeyName parameter
# (another XPATH expression)
####################################################################################################
@route('/video/mythrecordings/GetRecordingList', filterBy = dict, allow_sync=True)
def GetRecordingList(filterBy = {}, sortKeyName = None, sortReverse = True, seriesInetRef = None, staticBackground = None):
	#url = PVR_URL + 'Dvr/GetRecordedList'

	backgroundUrl = GetSeriesBackground(seriesInetRef, staticBackground)
	oc = ObjectContainer(title2 = MakeTitle(filterBy, sortKeyName), art = backgroundUrl)
	
	recordings = GetMythTVRecordings(filterBy)

	# Sorting the list:
	if (sortKeyName is not None):
		recordings.sort(key=lambda rec: rec.find(sortKeyName).text, reverse=sortReverse)
	
	for recording in recordings:
		recordingEntry = Recording(recording, seriesInetRef = seriesInetRef)
		oc.add(recordingEntry)
			
	return oc



####################################################################################################
def Recording(recording, seriesInetRef = None, staticBackground = None):
	Log("Recording(recording = %s, seriesInetRef = %s, staticBackground = %s)" % (recording, seriesInetRef, staticBackground))
	
	# Mandatory properties: Title, Channel, StartTime, EndTime:
	# =========================================================
	showname = GetField(recording, 'Title')
	chanId = recording.find('Channel').find('ChanId').text
	programStart = GetField(recording, 'StartTime')
	programEnd = GetField(recording, 'EndTime')
	recordingStart = GetField(recording, 'Recording/StartTs')
	recordingEnd = GetField(recording, 'Recording/EndTs')

	shouldStart = datetime.datetime.strptime(programStart,"%Y-%m-%dT%H:%M:%SZ")
	didStart = datetime.datetime.strptime(recordingStart,"%Y-%m-%dT%H:%M:%SZ")
	shouldEnd = datetime.datetime.strptime(programEnd,"%Y-%m-%dT%H:%M:%SZ")
	didEnd = datetime.datetime.strptime(recordingEnd,"%Y-%m-%dT%H:%M:%SZ")

	fileName = GetField(recording, 'FileName')
	storageGroup = GetField(recording, 'Recording/StorageGroup')

	# Playback URL:
	# =============
	# MythTV setting 'Master Backend Override'definition: If enabled, the master backend will stream and 
	# delete files if it finds them in the video directory. Useful if you are using a central storage 
	# NFS share, and your slave backend isn’t running.
	#
	# Note from user sammyjayuk on the Plex forums: GetRecording doesn't respect this setting (it sends
	# an HTTP redirect sending you to the recording backend). GetFile works as expected.
	#
	# For experimental purposes, we'll use GetFile, but only if the user sets this in the settings.
	respectMasterBackendOverride = Prefs['respectMasterBackendOverride']
	
	if respectMasterBackendOverride:
		testURL = PVR_URL + 'Content/GetFile?StorageGroup=%s&FileName=%s' % (storageGroup,fileName,)
	else:
		testURL = PVR_URL + 'Content/GetRecording?ChanId=%s&StartTime=%s' % (chanId,recordingStart,)
	
	#Log('Recording: Name "%s" => URL="%s"' % (showname, testURL))


	# Optional properties:
	# ====================	

	
	# SubTitle:
	# =========

	try:
		#epname = recording.find('SubTitle').text
		epname = GetField(recording, 'SubTitle')
		epname = "%s (%s)" % (epname, shouldStart.strftime('%Y-%m-%d'))
	except:
		Warning('Recording: Recording: "%s" had no SubTitle - using date' % showname)
		epname = shouldStart.strftime('%Y-%m-%d')

	#Log("EPNAME = %s" % epname)

	# Still recording?
	# ================

	utcnow = datetime.datetime.utcnow()
	timeSinceEnd = utcnow - didEnd
	stillRecording = timeSinceEnd < datetime.timedelta(hours=0, minutes=0,seconds=30)

	# Duration:
	# =========

	try:
		if stillRecording:
			delta = didEnd - didStart
		else:
			delta = shouldEnd - didStart + datetime.timedelta(hours=0, minutes=5,seconds=0)

	except:
		Warning('Recording: Recording: "%s", Duration error, Unexpected error' % showname)
		delta = datetime.timedelta(hours=3, minutes=0,seconds=0)

	duration = str(int(delta.seconds * 1000))
	
	# Check for missing start or end:
	# ===============================

	try:
		missedAtStart = didStart - shouldStart # negative means OK
		missedAtEnd = shouldEnd - didEnd # negative means OK
		# generate warning:
		missedStart = missedAtStart > datetime.timedelta(hours=0, minutes=0,seconds=0)
		missedEnd = missedAtEnd > datetime.timedelta(hours=0, minutes=0,seconds=0)

		if stillRecording:
			missedEnd = False

		if (missedStart and missedEnd):
			warning = F("ERROR_MISSED_BOTH", str(missedAtStart),str(missedAtEnd)) + "\n"
		elif (missedStart):
			warning = F("ERROR_MISSED_START", str(missedAtStart)) + "\n"
		elif (missedEnd):
			warning = F("ERROR_MISSED_END", str(missedAtEnd)) + "\n"
		else:
			warning = ""

		if stillRecording:
			warning = L("STATUS_STILL_RECORDING") + '\n' + warning

	except:

		Warning('Recording: Recording: "%s", Duration error, Unexpected error' % showname)
		
	# Description:
	# ============
	try:
		descr = GetField(recording, 'Description').strip() #recording.find('Description').text.strip()
	except:
		Warning('Recording: Recording: "%s", Descr error, Unexpected error' % showname)
		descr = None


	# ChanId:
	# =======
	try:
		channel = recording.find('Channel').find('ChanId').text
		if channel == '0':
			channel = None
	except:
		Warning('Recording: Recording: "%s", Could not get channel ID' % showname)			
		channel = None
	
	# Title:
	# ======
	header = '%s - %s' % (showname,epname)
	if epname is None:
		header = showname
	if stillRecording:
		header = header + " (" + L("STATUS_STILL_RECORDING_2") + ")"
	#status = recording.find('Recording/Status').text
	#header = "(" + status + ") " + header

	# Screenshot:
	# ===========
	if not channel is None and not recordingStart is None:
		thumb = PVR_URL + '/Content/GetPreviewImage?ChanId=%s&StartTime=%s' % (channel, recordingStart,)
		backgroundUrl = PVR_URL + '/Content/GetPreviewImage?ChanId=%s&StartTime=%s' % (channel, recordingStart,)
	else:
		thumb = R(MYTHTV_ICON)
		backgroundUrl = R(MYTHTV_BACKGROUND)

	# Background image:
	# =================
	#backgroundUrl = GetSeriesBackground(seriesInetRef, staticBackground)

	Log("ICON(%s) => %s" % (header, thumb))
	return VideoClipObject(
                title = header,
                summary = str(warning) + str(descr),
                originally_available_at = shouldStart,
                thumb = thumb,
		art = backgroundUrl,
		duration = int(duration),
		key = Callback(RecordingInfo, chanId=chanId, startTime=recordingStart, seriesInetRef=seriesInetRef),
		rating_key= str(int(shouldStart.strftime('%Y%m%d%H%M'))),
		items = [
			MediaObject(
				parts = [
					PartObject(key=testURL, duration=int(duration))
				],
				duration = int(duration),
				container = 'mp2ts',
				#video_codec = VideoCodec.H264,
				#audio_channels = 2,
				optimized_for_streaming = True
			)
		]
        )


####################################################################################################
# RecordingInfo:
# ==============
# Returns an ObjectContainer with metadata about a recording, as required by the VideoClipObject.
# The purpose is a bit mysterious, but it's required.
#
# Return:
#    ObjectContainer
####################################################################################################
@route('/video/mythrecordings/GetRecordingInfo', allow_sync=True)
def RecordingInfo(chanId, startTime, seriesInetRef):
	url = PVR_URL + 'Dvr/GetRecorded?StartTime=%s&ChanId=%s' % (startTime, chanId)
	request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	#Log('RecordingInfo(chanId="%s", startTime="%s" seriesInetRef="%s"): opening %s' % (chanId, startTime, seriesInetRef, url))
	u = urllib2.urlopen(request)
	tree = ET.parse(u)
	root = tree.getroot()

	recording = root #.findall('Programs/Program')

	# Background image:
	# =================
	backgroundUrl = GetSeriesBackground(seriesInetRef, None)

	recording_object = Recording(recording, seriesInetRef)
	return ObjectContainer(objects=[recording_object], art=backgroundUrl)


####################################################################################################
# GetMythTVRecordings:
# ====================
# Gets a list of all recording structures matching the specified filters.
#
# Return:
#    list of recording (the structure of a recording is irrelevant - use GetField to
#                       retrieve the value of a field)
####################################################################################################
def GetMythTVRecordings(filterBy, maxCount=None):
	url = PVR_URL + 'Dvr/GetRecordedList'
	if not maxCount is None:
		url = url + "?Count=" + maxCount
	xmlstring = HTTP.Request(url, cacheTime = CACHE_TIME).content
	root = ET.fromstring(xmlstring)
	
	#request = urllib2.Request(url, headers={"Accept" : "application/xml"})
	#u = urllib2.urlopen(request)
	#tree = ET.parse(u)
	#root = tree.getroot()
	
	# Loop through recordings, filtering as specified:
	recordings = root.findall('Programs/Program')
	result = []
	for recording in recordings:
		if recording.find('Recording/RecGroup').text == 'Deleted':
			continue
		if recording.find('Recording/RecGroup').text == 'LiveTV':
			continue
		if recording.find('FileSize').text == '0':
			continue
		#if recording.find('Recording/Status').text == '3':
		#	continue
		if recording.find('Title').text == 'Unknown':
			continue
		if not Match(filterBy, recording):
			continue

		result.append(recording)

	return result

def Match(filterBy, recording):
	for filterKeyName, filterKeyValue in filterBy.items():
		actualFilterKeyValue = GetField(recording, filterKeyName)
		if not actualFilterKeyValue == filterKeyValue:
			return False
	return True


####################################################################################################
# GetField:
# =========
# Gets the value of a field in the recording AFTER having performed alias substitution on it,
#
# The value thus found is passed through an aliasing mechanism, intended to conflate almost-identical
# values (like "Series" and "Serie" or "Tonight Show" and "The Tonight Show"). See the LoadAliases
# function for details.
#
# Return:
#    string
#
####################################################################################################
def GetField(recording, fieldName):
	if fieldName == "Title" or fieldName == "SubTitle":
		subtitle = recording.find('SubTitle').text
		title = recording.find('Title').text
		
		dontSplit = False
		for nosplitter in TITLE_NOSPLITTERS:
			dontSplit = re.search(nosplitter, title)
			if dontSplit:
				break

		if not dontSplit:
			for splitter in TITLE_SPLITTERS:
				splitResult = title.split(splitter, 1)
				if len(splitResult) == 2:
					orgTitle = title
					title,newsubtitle = splitResult
					title = title.strip()
					newsubtitle = newsubtitle.strip()
					if subtitle:
						subtitle = newsubtitle + " - " + subtitle
					#Log('Split title "%s" into ("%s", "%s")' % (orgTitle, title, subtitle))
					break

		if fieldName == "Title":
			return title
		if fieldName == 'SubTitle':
			return subtitle

	if fieldName == "Category":
		keyAliases = LoadAliases('categoryAliases')
		orgKeyValue = recording.find(fieldName).text
		return MapAliases(orgKeyValue, keyAliases)

	return recording.find(fieldName).text


####################################################################################################
# MapAlias:
# =========
# Maps a string into its canonical version (if any), using an alias list loaded by LoadAliases.
#
# Return:
#    string
#
# Example:
#    Assume the JSON formatted alias string from the LoadAliases description:
#       [['Series', 'serie', 'series'], ['Movies', 'film', 'action']]
#    This will produce the following mappings:
#       'action' => 'Movies'
#       'Movies' => 'Movies'
#       'serie'  => 'Series'
#       'xyz'    => 'xyz'
#    Note how a string that doesn't appear in as a synonym ('xyz' above) is passed through
#    unchanged.
####################################################################################################
def MapAliases(keyValue, keyAliases):
	if keyValue is None:
		keyValue = ''

	result = keyValue
	
	#Log('type(keyAliases) = %s', type(keyAliases))
	if isinstance(keyAliases, list): 
		for aliasList in keyAliases:
			#Log('Looking for %s in %s', keyValue, aliasList)
			if (keyValue in aliasList):
				#Log('Mapping %s => %s', keyValue, aliasList[0])
				result = aliasList[0]

	return result


####################################################################################################
# LoadAliases:
# ============
# Loads a list of aliases from the preferences string specified by the parameter aliasPrefName.
#
# The alias list if a JSON formatted list of list of strings. Each list-of-strings is interpreted
# as a canonical name, followed by its synonyms.
#
# Return:
#    list of list of strings
#
# Example:
#    The following JSON formatted alias string defines the canonical names 'Series' and 'Movies', 
#    and two synonyms for each:
#       [['Series', 'serie', 'series'], ['Movies', 'film', 'action']]
####################################################################################################
def LoadAliases(aliasPrefName):
	if aliasPrefName is None:
		return []
	if aliasPrefName == "":
		return []

	# Workaround:
	# =========== 
	# It is really difficult to edit a list-of-lists in the preferences editor
	# - so we're moving the aliases to hardcoded variables for now:
	if aliasPrefName == "categoryAliases":
		return CategoryAliases

	return []
	
	#keyAliasString = Prefs[aliasPrefName]
	#try:
	#	#Log('keyAliasString = %s', keyAliasString)
	#	keyAliases = json.loads(keyAliasString)
	#	#Log('keyAliases = %s', keyAliases)
	#except:
	#	keyAliases = [] # no aliases, then

	#return keyAliases


#####################################################################################################
def ValidatePrefs():
	global PVR_URL
	if Prefs['server'] is None:
		return MessageContainer("Error", L("ERROR_MISSING_SERVER_INFO"))
	elif Prefs['port'] is None:
		return MessageContainer("Error", L("ERROR_MISSING_SERVER_PORT"))
	elif not Prefs['port'].isdigit():
		return MessageContainer("Error", L("ERROR_SERVER_PORT_NON_NUMERIC"))
	else:
		port = Prefs['port']
		PVR_URL = 'http://%s:%s/' % (Prefs['server'], port)
		Log('ValidatePrefs: PVR URL = %s' % PVR_URL)
		try:
			testXML = GetMythTVRecordings({}, 1)
			# Should we test the 
			#    <Version>0.25.20110928-1</Version>
			# element for ver >= 0.27
		except:
			return MessageContainer("Error", F("MYTHSERVER_UNAVAILABLE", "a", "b"))#(Prefs['server'], port))

		return MessageContainer("Success","Success")
