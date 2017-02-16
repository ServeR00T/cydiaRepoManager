#!/usr/bin/env python3
# Script to maintain a cydia repository, get packages from other repositories, 
# set up a meta file and packages index.

import os, time, shutil, binascii, random, gzip, bz2, argparse
from urllib.request import *
from urllib.error import *

# Correct terminal width
os.environ['COLUMNS'] = str(shutil.get_terminal_size().columns)

# Colors
#Black        0;30     Dark Gray     1;30
#Red          0;31     Light Red     1;31
#Green        0;32     Light Green   1;32
#Brown/Orange 0;33     Yellow        1;33
#Blue         0;34     Light Blue    1;34
#Purple       0;35     Light Purple  1;35
#Cyan         0;36     Light Cyan    1;36
#Light Gray   0;37     White         1;37
RED='\033[0;31m'
YEL='\033[0;33m'
GRN='\033[0;32m'
NOC='\033[0m' # No Color

# Arguments checking
argParser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
argParser.add_argument("-s", "--sources", action="store", help="Location of the sources file as it is in iDevice, check that :-)")
argParser.add_argument("-w", "--wanted", action="store", default=None, help="If wanted to check for specific packages, Specify location of the wanted packages file, contents must be just packages names one per line.")
argParser.add_argument("-d", "--download", action="store", default=None, help="If wanted to download the deb files. Specify directory location to save the debs, it will take time depends on your link speed.")
argParser.add_argument("-dir", "--directory", action="store", default="tmpPackages", help="Default is tmpPackages, Specify a temporary directory to download all Release and Packages files to it.")
argParser.add_argument("-b", "--build", action="store_true", default=False, help="Determine if wanted to build a Packages file from the results, if you're running a repository.")
argParser.add_argument("-v", "--verbose", action="store_true", default=False, help="Increase output verbosity.")
argParser.add_argument("-su", "--skip-update", action="store_true", default=False, help="Skip updating sources.")
args = argParser.parse_args()

# initaiting and checking files and directories
for arg, argValue in vars(args).items():
	if arg != "sources" and argValue == None:
		continue
	if arg == "sources" and argValue == None:
		print(RED+"Error"+NOC+": sources file is necessary\n")
		argParser.print_usage()
		exit()
	if arg in ['download', 'directory']:
		if os.path.isdir(argValue):
			if not os.access(argValue, os.W_OK):
				print(RED+"Error"+NOC+": "+argValue+" is NOT writable")
				exit()
		else:
			try:
				os.makedirs(argValue)
			except FileExistsError as e:
				pass
			except OSError as e:
				if e.errno == errno.EACCES:
					print(RED+"Error"+NOC+": Permission Denied")
				else:
					print(e.strerror)
				exit()
	if arg in ['sources', 'wanted']:
		if os.path.isfile(argValue):
			if not os.access(argValue, os.R_OK):
				print(RED+"Error"+NOC+": "+argValue+" is NOT readable")
				exit()
		else:
			print(RED+"Error"+NOC+": "+argValue+" does NOT exists")
			exit()

# A dummy Exception for breaking nested loops
class BreakMultipleLoops(Exception): pass

# Preparing some vars
# in order - lz not yet implemented
preferedPackagesExtensions=['Packages.gz', 'Packages.bz2', 'Packages', 'Packages.lzma', 'Packages.xz']
#preferedPackagesExtensions=['Packages.gz', 'Packages.bz2', 'Packages', 'Packages.lz', 'Packages.lzma', 'Packages.xz']

# Variable for window width
leftChars=shutil.get_terminal_size().columns-15
rightChars=15

# Preparing HTTP headers
iDeviceIdentifiers = ['iPad1,1', 'iPad2,1', 'iPad2,2', 'iPad2,3', 'iPad2,4', 'iPad3,1', 'iPad3,2', 'iPad3,3', 'iPad3,4', 'iPad3,5',
					'iPad3,6', 'iPad4,1', 'iPad4,2', 'iPad4,3', 'iPad4,4', 'iPad4,5', 'iPad4,6', 'iPad4,7', 'iPad4,8', 'iPad4,9', 
					'iPad5,1', 'iPad5,2', 'iPad5,3', 'iPad5,4', 'iPad6,3', 'iPad6,4', 'iPad6,7', 'iPad6,8', 'iPad5,2', 'iPad5,3', 
					'iPad5,4', 'iPad6,3', 'iPad6,4', 'iPad6,7', 'iPad6,8', 'iPhone6,1', 'iPhone6,2', 'iPhone7,1', 'iPhone7,2', 
					'iPhone8,1', 'iPhone8,2', 'iPhone8,4', 'iPhone9,1', 'iPhone9,2', 'iPhone9,3', 'iPhone9,4']
iOSVersions = ['9.0.1', '9.0.2', '9.1', '9.2', '9.2.1', '9.3', '9.3.1', '9.3.2', '9.3.3', '10.0.1', '10.0.2', '10.0.3', '10.1', '10.1.1', '10.2']
randonHex40 = binascii.b2a_hex(os.urandom(20)) # 40 hex digits = 20 bytes
deviceIdentifier = random.choice(iDeviceIdentifiers)
iOSVersion = random.choice(iOSVersions)

# *********************** Defining useful functions

# Human readable link speed given bytes
# http://stackoverflow.com/a/1094933/5650671
def humanReadableLinkSpeed(num, suffix='B/s'):
	if not isinstance(num, int) and not isinstance(num, float):
		return "unspecified"

	for unit in ['','K','M','G','T','P','E','Z']:
		if abs(num) < 1024.0:
			return "%3.2f%s%s" % (num, unit, suffix)
		num /= 1024.0
	return "%.1f%s%s" % (num, 'Y', suffix)

# download any file
# Progress bar idea from http://stackoverflow.com/a/32300565/5650671
def downloadFile(url, fileExtension='', packagesFileNumberInFileName=-1, response=None):
	'''
	download a file and uncompress it if it's compressed
	Return uncompressed local file name on success or None for whatever reason
	'''
	global sourceDomainName
	global sourceCountPadded
	if 'sourceCountPadded' not in globals(): sourceCountPadded="+++"
	sourceDomainName = url.split("/")[2]

	if url.endswith("Release"):
		localFileName=sourceDomainName+"_Release"
	elif url.endswith('.deb'):
		if "=" in url:
			localFileName = url.split('=')[-1]
		else:
			localFileName = url.split('/')[-1]
		localFilePath = os.path.join(args.download, localFileName)
	else:
		if url.endswith(".gz"):
			fileExtension=".gz"
		elif url.endswith(".bz2"):
			fileExtension=".bz2"
		elif url.endswith(".lz"):
			fileExtension=".lz"
		elif url.endswith(".lzma"):
			fileExtension=".lzma"
		elif url.endswith(".xz"):
			fileExtension=".xz"
		else:
			fileExtension=""

		if packagesFileNumberInFileName == -1:
			packagesFileNumberInFileName=""
		else:
			packagesFileNumberInFileName="_"+packagesFileNumberInFileName

		localFileName=sourceDomainName+"_Packages"+packagesFileNumberInFileName+fileExtension
	
	if response == None:
		response = getResponse(url)
		if response == None:
			return None

	if not url.endswith('.deb'): localFilePath = os.path.join(args.directory, localFileName)
	if url.endswith("Release") or fileExtension == "":
		uncompressedlocalFilePath = localFilePath
	else:
		uncompressedlocalFilePath = localFilePath[:localFilePath.rfind(fileExtension)]

	remoteFileSize=getURLFileSize(response)
	if os.path.isfile(localFilePath):
		localFileSize=os.path.getsize(localFilePath)
		if localFileSize == remoteFileSize:
			if args.verbose: print(getAlignedLine("["+sourceCountPadded+"] "+localFileName+" already exists", "FOUND", GRN))
			return str(uncompressedlocalFilePath)

	if args.verbose:
		dataBlocks = []
		bytesReadSoFar=0
		windowsColumns=shutil.get_terminal_size().columns-26-len(sourceDomainName)
		startTime=time.time()
		while True:
			block = response.read(1024)
			dataBlocks.append(block)
			bytesReadSoFar += len(block)
			linkSpeed=bytesReadSoFar/(time.time()-startTime)
			hash = ((windowsColumns*bytesReadSoFar)//remoteFileSize)
			if not len(block):
				print("[{}] {} [{}{}] {}% {} ".format(sourceCountPadded, sourceDomainName, '#' * windowsColumns, ' ' * 0, 100, humanReadableLinkSpeed(linkSpeed)))
				break
			print("[{}] {} [{}{}] {}% {} ".format(sourceCountPadded, sourceDomainName, '#' * hash, ' ' * (windowsColumns-hash), int(bytesReadSoFar/remoteFileSize*100), humanReadableLinkSpeed(linkSpeed)), end="\r")
		data = b''.join(dataBlocks)
	else:
		data = response.read()
	# Saving response to file
	fileObject = open(localFilePath, "wb")
	fileObject.write(data)
	fileObject.close()
	response.close()

	# uncompressing if compressed and the uncompressed doesn't exists
	if fileExtension != '':
		compress=True
		if os.path.isfile(uncompressedlocalFilePath) and os.path.isfile(localFilePath):
			# if the last modification time difference between the two files is big enough (5m) do uncompress
			if (os.path.getmtime(localFilePath)-os.path.getmtime(uncompressedlocalFilePath)) < 300:
				compress = False
		
		if compress:
			result = uncompressFile(localFilePath, fileExtension)
			if result and args.verbose: print(getAlignedLine("["+sourceCountPadded+"] "+localFileName+" successfully uncompressed", "SUCCESS", GRN))
			if not result: print(getAlignedLine("["+sourceCountPadded+"] "+localFileName+" can NOT be uncompressed", "FAILED"))
	return str(uncompressedlocalFilePath)

# Called by DownloadFile function
# uncompress a local file
def uncompressFile(path, compressionFormat):
	'''
	returns True if success or False
	'''
	uncompressedFileName = path[:path.rfind(compressionFormat)]

	if compressionFormat == ".gz":
		compressedObject = gzip.open(path, 'rb')
	elif compressionFormat == ".bz2":
		compressedObject = bz2.open(path, 'rb')
		#elif compressionFormat == ".lz":
		#compressedObject = gzip.open(path, 'rb') ******************** NOT implemented yet
	elif compressionFormat == ".lzma" or compressionFormat == ".xz":
		compressedObject = lzma.open(path, 'rb')
	else:
		return False

	with open(uncompressedFileName, 'wb') as uncompressedObject:
		try:
			shutil.copyfileobj(compressedObject, uncompressedObject)
			return True
		except OSError as e:
			print(getAlignedLine("["+sourceCountPadded+"] "+e.strerror, "FAILED"))
		else:
			uncompressedObject.close()
			compressedObject.close()

	return False

# Make a HTTP request with specific headers
def getResponse(url):
	'''
	Returns HTTPResponse or None if it can't get the file
	'''
	request = Request(url)
	request.add_header('User-Agent', 'Telesphoreo APT-HTTP/1.0.592')
	request.add_header('X-Machine', deviceIdentifier)
	request.add_header('X-Firmware', iOSVersion)
	request.add_header('X-Unique-ID', randonHex40)
	domainName = url.split('/')[2]
	fileName = url.split('/')[-1]
	response=None

	try:
		response = urlopen(request, timeout=3)
	except HTTPError as e:
		if e.code == 404:
			if args.verbose: print(getAlignedLine("["+sourceCountPadded+"] "+domainName+" "+fileName+" file is NOT online", "NOTICE", YEL))
		else:
			if args.verbose: print(getAlignedLine("["+sourceCountPadded+"] "+domainName+" "+fileName+" HTTPError "+ str(e.code), "ERROR"))
	except URLError as e:
		print(getAlignedLine("["+sourceCountPadded+"] "+domainName+" "+fileName+" URLError "+ str(e.reason), "ERROR"))
	except:
		print(getAlignedLine("["+sourceCountPadded+"] "+domainName+" "+fileName, "ERROR"))
	else:
		return response
	if response != None: response.close()
	return None

# When there is no Release file, this function will trigger, tries common Packages file formats
def crawlingForPackagesFile(url):
	'''
	check existence of multiple Packages files online
	Returns a url if one found or None if nothing found
	'''
	global sourceCountPadded
	domainName = url.split('/')[2]

	for file in preferedPackagesExtensions:
		response = getResponse(url+"/"+file)
		if response != None:
			if args.verbose: print(getAlignedLine("["+sourceCountPadded+"] "+domainName+" "+file+" found by crawling", "FOUND", GRN))
			url = response.geturl()
			response.close()
			return url

	if args.verbose: print(getAlignedLine("["+sourceCountPadded+"] "+domainName+" Packages files is NOT online", "FAILED"))
	return None

# Get online file size
def getURLFileSize(response):
	'''
	Get the file size of HTTPResponse object
	returns 100MB if unspecified
	'''
	if 'Content-Length' not in response.headers:
		# if unspecified make it big enough (100MB) it will work :-)
		return 104857600
	else:
		return int(response.headers['Content-Length'])

# This function will trigger on every line of Packages file
# it will extract from every line the name and the value
def extractInfo(lineOfControlFile):
	'''
	returns a dictonary of one element contains name: value
	EXCEPT with additional description lines, returns String starts with DESC:
	'''
	lineOfControlFile = lineOfControlFile.rstrip()
	lineOfControlFileTMP = lineOfControlFile.lower().capitalize()

	if lineOfControlFileTMP.startswith("Package:"):
		return {'Package': lineOfControlFile[8:].strip()}
	elif lineOfControlFileTMP.startswith("Name:"):
		return {'Name': lineOfControlFile[5:].strip()}
	elif lineOfControlFileTMP.startswith("Version:"):
		return {'Version': lineOfControlFile[8:].strip()}
	elif lineOfControlFileTMP.startswith("Architecture:"):
		return {'Architecture': lineOfControlFile[13:].strip()}
	elif lineOfControlFileTMP.startswith("Description:"):
		return {'Description': lineOfControlFile[12:].strip()}
	elif lineOfControlFileTMP.startswith("Homepage:"):
		return {'Homepage': lineOfControlFile[9:].strip()}
	elif lineOfControlFileTMP.startswith("Depiction:"):
		return {'Depiction': lineOfControlFile[10:].strip()}
	elif lineOfControlFileTMP.startswith("Maintainer:"):
		return {'Maintainer': lineOfControlFile[11:].strip()}
	elif lineOfControlFileTMP.startswith("Author:"):
		return {'Author': lineOfControlFile[7:].strip()}
	elif lineOfControlFileTMP.startswith("Dev:"):
		return {'Dev': lineOfControlFile[4:].strip()}
	elif lineOfControlFileTMP.startswith("Sponsor:"):
		return {'Sponsor': lineOfControlFile[8:].strip()}
	elif lineOfControlFileTMP.startswith("Section:"):
		return {'Section': lineOfControlFile[8:].strip()}
	elif lineOfControlFileTMP.startswith("Filename:"):
		return {'Filename': lineOfControlFile[9:].strip()}
	elif lineOfControlFileTMP.startswith("Size:"):
		return {'Size': lineOfControlFile[5:].strip()}
	elif lineOfControlFileTMP.startswith("Installed-size:"):
		return {'Installed-Size': lineOfControlFile[15:].strip()}
	elif lineOfControlFileTMP.startswith("Md5sum:"):
		return {'MD5Sum': lineOfControlFile[7:].strip()}
	elif lineOfControlFileTMP.startswith("Sha1:"):
		return {'SHA1': lineOfControlFile[5:].strip()}
	elif lineOfControlFileTMP.startswith("Sha256:"):
		return {'SHA256': lineOfControlFile[7:].strip()}
	elif lineOfControlFileTMP.startswith("Sha512:"):
		return {'SHA512': lineOfControlFile[7:].strip()}
	elif lineOfControlFileTMP.startswith("Pre-depends:"):
		return {'Pre-Depends': lineOfControlFile[12:].strip()}
	elif lineOfControlFileTMP.startswith("Depends:"):
		return {'Depends': lineOfControlFile[8:].strip()}
	elif lineOfControlFileTMP.startswith("Conflicts:"):
		return {'Conflicts': lineOfControlFile[10:].strip()}
	elif lineOfControlFileTMP.startswith("Priority:"):
		return {'Priority': lineOfControlFile[9:].strip()}
	elif lineOfControlFileTMP.startswith("Icon:"):
		return {'Icon': lineOfControlFile[5:].strip()}
	elif lineOfControlFileTMP.startswith("Tag:"):
		return {'Tag': lineOfControlFile[4:].strip()}
	elif lineOfControlFileTMP.startswith("Replaces:"):
		return {'Replaces': lineOfControlFile[9:].strip()}
	elif lineOfControlFileTMP.startswith("Breaks:"):
		return {'Breaks': lineOfControlFile[7:].strip()}
	elif lineOfControlFileTMP.startswith("Provides:"):
		return {'Provides': lineOfControlFile[9:].strip()}
	elif lineOfControlFileTMP.startswith("Essential:"):
		return {'Essential': lineOfControlFile[11:].strip()}
	elif lineOfControlFileTMP.startswith("Website:"):
		return {'Website': lineOfControlFile[8:].strip()}
	elif lineOfControlFileTMP.startswith("Suggests:"):
		return {'Suggests': lineOfControlFile[9:].strip()}
	elif lineOfControlFileTMP.startswith("Recommends:"):
		return {'Recommends': lineOfControlFile[12:].strip()}
	elif lineOfControlFileTMP.startswith(" "):
		return 'Description:'+lineOfControlFile.strip()
	else:
		if args.verbose: print(getAlignedLine("[+++] Unknown name and value from Packages file", "NOTICE", YEL))
		print(lineOfControlFile.strip())
		return {}

# Align text with color for the right aligned part
def getAlignedLine(left, right, color=RED):
	return "{4:<{0}}{2}{5:^{1}}{3}".format(leftChars, rightChars, color, NOC, left, "["+right+"]")

# Here what the script is doing

# Updating sources or not
packagesFilesForAllRepos=[]
if not args.skip_update:
	# reading the sources file, update all
	# initiate some variables
	sourceCount=0
	sourcesFileObj = open(args.sources)
	for lineInSources in sourcesFileObj:
		packagesFilesForThisRepo=[]
		response=None
		remotePackagesFilePath=[]
		crawling=True
		lineInSources = lineInSources.strip()
		sourceCount+=1
		sourceCountPadded = "{:0>3}".format(str(sourceCount))
		lineSeparatedBySpace = lineInSources.split(' ')
		sourceRootURL = lineSeparatedBySpace[1]
		sourceDistribution = lineSeparatedBySpace[2]

		# if there is a "component"
		if len(lineSeparatedBySpace) > 3:
			sourceComponent = lineSeparatedBySpace[3]
		else:
			sourceComponent = ""
		
		# Set source url by combining some structure
		if sourceDistribution == "./" or sourceDistribution == ".":
			sourceURL=sourceRootURL
		else:
			sourceURL=sourceRootURL+"dists/"+sourceDistribution+"/"
		
		# Get Release file
		response = getResponse(sourceURL+"Release")
		if response != None:
			localFileName = downloadFile(sourceURL+"Release", response=response)
			# Reading the downloaded Release file
			if localFileName != None:
				fileObject = open(localFileName, "r")
				try:
					for packagesFileExtension in preferedPackagesExtensions:
						for lineInRelease in fileObject:
							if lineInRelease.strip().endswith(packagesFileExtension):
								remotePackagesFilePath.append(lineInRelease.split(' ')[-1].strip())
								crawling = False
								#raise BreakMultipleLoops
						if not crawling: break
						fileObject.seek(0)
				except BreakMultipleLoops:
					pass
				fileObject.close()
		else:
			# if there is no Release file, crawl for Packages file
			crawling = True
		
		# Get Packages file by two methods, path if determined or by crawling
		if crawling:
			url = crawlingForPackagesFile(sourceURL)
			if url != None:
				localFileName = downloadFile(url)
				if localFileName != None:
					packagesFilesForThisRepo.append(localFileName)
		else:
			# Sort and make it unique, because sometimes there are duplicates in Release file
			remotePackagesFilePath = list(set(remotePackagesFilePath))

			# if there is no Package file
			if len(remotePackagesFilePath) < 1:
				continue
			elif len(remotePackagesFilePath) > 1:
				for index, rPFP in enumerate(remotePackagesFilePath):
					localFileName = downloadFile(sourceURL+rPFP, packagesFileNumberInFileName="{:0>3}".format(str(index)))
					if localFileName != None:
						packagesFilesForThisRepo.append(localFileName)
			else:
				# if there is just one Package file
				localFileName = downloadFile(sourceURL+remotePackagesFilePath[0])
				if localFileName != None:
					packagesFilesForThisRepo.append(localFileName)
		packagesFilesForAllRepos += packagesFilesForThisRepo
else:
	# if not updating the sources, get names of the existing files
	contents = os.listdir(args.directory)
	for fileName in contents:
		if ("Packages" in fileName and fileName[-3:].isdigit()) or fileName.endswith("Packages"):
			packagesFilesForAllRepos.append(os.path.join(args.directory, fileName))

# if no process specified then exit
if not args.wanted and not args.download and not args.build:
	exit()

# if there is a wanted packages load them in a list
if args.wanted:
	with open(args.wanted) as fileObject:
		wantedPackages = [line.strip() for line in fileObject]

# if wanted to build Packages file, check for the existance of the Packages file
# if exists => if verbose take the command from user else override the file
if args.build:
	packagesFileToBuild='Packages'
	if os.path.isfile(packagesFileToBuild) and args.verbose:
		userResponse = 'UnrealisticInput:)'
		while userResponse.lower() not in ['y', 'n', 'q']:
			print('The file Packages already exists, Do you want to override it ? (Y/n/q): ', end='')
			userResponse = input().strip()
			if userResponse == 'y' or not userResponse: break
			elif userResponse == 'q': exit()
			elif userResponse == 'n':
				while True:
					print('Enter a name for the Packages file: ', end='')
					packagesFileToBuild = input().strip()
					if not os.path.isfile(packagesFileToBuild):
						break
	buildFileObj = open(packagesFileToBuild, 'w')

# Initiates some variables
packageName=None
packageWanted=False
readPackageName=True
wantedPackagesFoundWithThisSource=0
wantedUniquePackagesFoundWithThisSource=0
uniqueWantedPackages=[]
wantedPackagesFound=0
packageInfo={}
allExtractedPackagesInfo=[]
disableDownloadTemporary={'bool': False, 'value':args.download}

# Processing
for packagesFile in packagesFilesForAllRepos:
	fileObject = open(packagesFile, errors='ignore')

	if disableDownloadTemporary['bool']:
		disableDownloadTemporary['bool']=False
		args.download=disableDownloadTemporary['value']

	domainName = packagesFile.split('/')[-1].split('_')[0]
	# rootURL from sources file
	rootURL=""
	fObj = open(args.sources)
	for line in fObj:
		if line.split('/')[2] == domainName:
			rootURL = line.strip().split(' ')[1]
			break

	if rootURL == "" and args.download:
		print(getAlignedLine("download disabled for " + domainName, "FAILED"))
		disableDownloadTemporary['bool']=True
		args.download=None

	# search in a single Packages file
	for lineInPackagesFile in fileObject:
		# with every single line in every single Packages file

		# if line is empty
		if not packageWanted and packageInfo:
			if packageInfo['Package'] not in uniqueWantedPackages:
				uniqueWantedPackages.append(packageInfo['Package'])
				wantedUniquePackagesFoundWithThisSource+=1
			allExtractedPackagesInfo.append(packageInfo.copy())
			packageInfo.clear()

		# if line is empty be ready for new package description and skip
		if not lineInPackagesFile.strip() and args.wanted:
			readPackageName=True
			# if the previous one is wanted place an empty line
			if args.build and packageWanted: buildFileObj.write('\n')
			packageWanted=False
			continue

		# if wanted and this is new Package
		if args.wanted and readPackageName:
			if lineInPackagesFile.startswith('Package:'):
				packageName = lineInPackagesFile[8:].strip()
				readPackageName=False

				if packageName in wantedPackages:
					wantedPackagesFoundWithThisSource+=1
					packageWanted = True

		# construct a dictonary for the package
		if packageWanted:
			extractedValue = extractInfo(lineInPackagesFile)
			if isinstance(extractedValue, dict):
				packageInfo.update(extractedValue)
			else:
				packageInfo['Description'] += " "+extractedValue[12:]

		# if build and there is nothing wanted ORRRRR if build and wanted and packageWanted then append the line to build file
		if (args.build and not args.wanted) or (args.build and args.wanted and packageWanted):
			buildFileObj.write(lineInPackagesFile)

		# if download and the line start with Filename which is the file path
		# this should execute for every package if wanted not specified of for only wanted
		if args.download and lineInPackagesFile.startswith('Filename:'):
			if args.wanted:
				if packageWanted:
					url = rootURL + lineInPackagesFile[9:].strip()
					print(url)
					print(downloadFile(url))
			else:
				url = rootURL + lineInPackagesFile[9:].strip()
				print(url)
				print(downloadFile(url))
	print("[+++] Found {}{:>3}{} packages in {}.".format(GRN, wantedUniquePackagesFoundWithThisSource, NOC, domainName))
	wantedPackagesFound+=wantedPackagesFoundWithThisSource
	wantedPackagesFoundWithThisSource=0
	wantedUniquePackagesFoundWithThisSource=0

# for i in wantedPackages:
# 	for j in allExtractedPackagesInfo:
# 		if i == j['Package']:
# 			print("{:50}{:10}{}".format(j['Package'], " ", j['Version']))
# 			continue

if args.wanted:
	print("[+++] Found total {}{:>5}{} packages.".format(GRN, wantedPackagesFound, NOC))

if args.wanted:
	print("[+++] Found total {}{:>5}{} unique packages.".format(GRN, len(uniqueWantedPackages), NOC))

# for i in allExtractedPackagesInfo:
# 	print(i['Package'] + "\t\t\t-\t" + i['Version'])


# seen, result = set(), []
# for idx, item in enumerate(allExtractedPackagesInfo):
# 	if item['Package'] not in seen:
# 		seen.add(item['Package'])          # First time seeing the element
# 	else:
# 		#print(item['Package'] +"\t\t"+ item['Version'])
# 		result.append(item)      # Already seen, add the index to the result


# print(allExtractedPackagesInfo)
# [3, 4, 7, 8, 9]

#downloadFile('http://apt.thebigboss.org/repofiles/cydia/dists/stable/main/binary-iphoneos-arm/Packages.bz2', "apt.thebigboss.org", "001", ".bz2")
