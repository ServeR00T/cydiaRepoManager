#!/usr/bin/env bash
# Construct a Packages file for the wanted packages only

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
columns=`tput cols`
lTS=$(($columns-15))
rTS=15

function printUsage()
{
	printf "Usage: $0 [OPTION] [VALUE] ...\n\n"
	printf "  -s, --sources\n"
	printf "\tSpecify the sources file as it is in iDevice\n\n"
	printf "  -w, --wanted\n"
	printf "\tSpecify the wanted packages file\n\n"
	printf "  -c, --construct\n"
	printf "\tDetermine if wanted to construct a Packages file from the results\n\n"
	printf "  -d, --download\n"
	printf "\tDownload deb files for wanted Packages\n"
	printf "\tfollowed by \"directory\" location to save the debs\n"
	printf "\t** it will tike time depends on your link speed\n\n"
	printf "  -h, --help\n"
	printf "\tShows this\n\n"
	printf "ex.\t$0 -s ./sources.list -w ./packagesInstalled\n\n"
	printf "By Saleem Saad <ir00t@outlook.com>\n"
}

if [ $# -eq 0 ]; then
	printUsage
	exit 1
fi

constructPackagesFile=false
downloadDebs=false
# Parsing arguments
# http://stackoverflow.com/a/14203146/5650671
while [[ $# -gt 0 ]]; do
	case $1 in
		# Sources file
		-s|--sources)
			if [ -r "$2" ]; then
				sourcesFile="$2"
			else
				printf "${RED}ERR${NOC}: invalid value for $1, file not readable or doesn't exists\n"
				exit 1
			fi
			shift # past argument
		;;
		# Wanted packages file
		-w|--wanted)
			if [ -r "$2" ]; then
				neededPackagesFile="$2"
			else
				printf "${RED}ERR${NOC}: invalid value for $1, file not readable or doesn't exists\n"
				exit 1
			fi
			shift # past argument
		;;
		# Construct a Packages file of the results
		-c|--construct)
			if [ ! -e "$2" ]; then
				touch "$2" &/dev/null
				if [ $? -ne 0 ]; then
					printf "${RED}ERR${NOC}: invalid value for $1, file doesn't exists and couldn't be created\n"
					exit 1
				fi
			fi
			constructFile="$2"
			constructPackagesFile=true
			shift # past argument
		;;
		# Download deb files
		-d|--download)
			if [ ! -d "$2" ]; then
				mkdir "$2" &>/dev/null
				if [ $? -ne 0 ]; then
					printf "${RED}ERR${NOC}: invalid value for $1, is NOT directory and couldn't be created\n"
					exit 1
				fi
			fi
			debDirectory="$2"
			downloadDebs=true
			shift # past argument
		;;
		# Print help
		-h|--help)
			printUsage
			exit 0
		;;
		*)
			printf "${RED}ERR${NOC}: invalid option $1\n"
			exit 1
		;;
	esac
	shift # past argument or value
done

if [ -z $sourcesFile ] || [ -z $neededPackagesFile ]; then
	printf "${RED}ERR${NOC}: sources file and wanted packages file are mandatories $1\n"
	exit 1
fi

# random HEX -> openssl rand -hex 20
# Could NOT use a variable to curl it will use it as URL !!!!
# Niether wGET !!!!!!
#curlHttpHeaders='-A "Telesphoreo APT-HTTP/1.0.592" -H "X-Machine: iPhone8,1" -H "X-Firmware: 10.2" -H "X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c"'
#wgetHttpHeaders='-U "Telesphoreo APT-HTTP/1.0.592" --header="X-Machine: iPhone8,1" --header="X-Firmware: 10.2" --header="X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c"'

# Format file sizes
formatNum()
{
	formatedNum=`numfmt --to=iec-i --suffix=B --format="%2f" $1 2>/dev/null`
	if [ $? -eq 0 ]; then
		echo $formatedNum
	else
		echo "unspecified"
	fi
}

# download Packages file and extract it if compressed
downloadPackagesFile()
{
	# usage downloadPackagesFile $url $filePath $sourceDomain $sourceCountPadded $fileExt $count(if any)
	# url = url + file path
	local url="$1/$2"
	local sourceDomain=$3
	local sourceCountPadded=$4
	local fileExt=$5
	if [ $# -eq 6 ]; then
		count="_${6}"
	else
		count=""
	fi
	local fileName=$sourceDomain"_Packages"$count$fileExt

	# Downloading Packages File
	if [[ ! `wget -U "Telesphoreo APT-HTTP/1.0.592" --header="X-Machine: iPhone8,1" --header="X-Firmware: 10.2" --header="X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" -S --spider $url  2>&1 | grep 'HTTP/1.1 200 OK'` ]]; then
		printf "%-${lTS}s${RED}%+${rTS}s${NOC}\n" "[$sourceCountPadded] $sourceDomain Packages file is NOT online" "FAILED"
		return 1
	else
		pacSize=$(wget -U "Telesphoreo APT-HTTP/1.0.592" --header="X-Machine: iPhone8,1" --header="X-Firmware: 10.2" --header="X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" --spider $url 2>&1 | grep "^Length" | awk '{print $2}')
		lPaSize=$(ls -l tmp/$fileName 2>/dev/null | awk '{print $5}')
		if [[ $pacSize -eq $lPaSize ]] && [[ -f tmp/$fileName ]]; then
			printf "%-${lTS}s%+${rTS}s\n" "[$sourceCountPadded] $sourceDomain's $fileName already exists" `formatNum $pacSize`
		else
			printf "%-${lTS}s%+${rTS}s\n" "[$sourceCountPadded] downloading `echo $sourceDomain` Packages file" `formatNum $pacSize`
			curl --connect-timeout 3 -m 180 -L -A "Telesphoreo APT-HTTP/1.0.592" -H "X-Machine: iPhone8,1" -H "X-Firmware: 10.2" -H "X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" -# $url --output "tmp/$fileName"
			if [ $? -ne 0 ]; then
				continue
			fi
			# wget -U "Telesphoreo APT-HTTP/1.0.592" --header="X-Machine: iPhone8,1" --header="X-Firmware: 10.2" --header="X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" -q --show-progress $url -O tmp/$fileName
		fi

		uncompressedFileName=$(basename $fileName $fileExt)
		if [[ $fileExt == ".bz2" ]]; then
			uncompressedNotExists=$(ls -l tmp/$uncompressedFileName 2>/dev/null | wc -l)
			if [[ $uncompressedNotExists -eq 0 ]]; then
				bzip2 -dkfq tmp/$fileName
			fi
		elif [[ $fileExt == ".gz" ]]; then
			uncompressedNotExists=$(ls -l tmp/$uncompressedFileName 2>/dev/null | wc -l)
			if [[ $uncompressedNotExists -eq 0 ]]; then
				gunzip -dkfq tmp/$fileName
			fi
		fi
		# write the uncompressed Packages file name to temporary file
		echo $uncompressedFileName >> tmp/PackagesFiles
	fi

	return 0
}

# Create a temporary folder
mkdir tmp &>/dev/null

sourceCount=0
packageAllCount=0
while read -r line; do
	packageCount=0
	((sourceCount++))
	sourceCountPadded=$(printf "%03d" $sourceCount)
	rootURL=$(echo $line | awk '{print $2}')
	distrib=$(echo $line | awk '{print $3}')
	compon1=$(echo $line | awk '{print $4}')
	sourceDomain=$(echo $rootURL | awk -F'/' '{print $3}')
	releaseFileExistsOnline=false
	crawling=false
	packagesFileExtension=""

	if [[ $distrib == './' ]] || [[ $distrib == '.' ]]; then
		url=$rootURL
	else
		url=$rootURL"dists/"$distrib
	fi

	# Check if Release file exists online
	if [[ ! `wget -U "Telesphoreo APT-HTTP/1.0.592" --header="X-Machine: iPhone8,1" --header="X-Firmware: 10.2" --header="X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" -S --spider $url/Release  2>&1 | grep 'HTTP/1.1 200 OK'` ]]; then
		printf "%-${lTS}s${YEL}%+${rTS}s${NOC}\n" "[$sourceCountPadded] $sourceDomain Release file is NOT online" "NOTICE"
	else
		# Release File detected online
		releaseFileExistsOnline=true
		onlineReleaseFileSize=$(wget -U "Telesphoreo APT-HTTP/1.0.592" --header="X-Machine: iPhone8,1" --header="X-Firmware: 10.2" --header="X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" --spider $url/Release 2>&1 | grep "^Length" | awk '{print $2}')
		localReleaseFileSize=$(ls -l tmp/$sourceDomain"_Release" 2>/dev/null | awk '{print $5}')
		if [[ $onlineReleaseFileSize -eq $localReleaseFileSize ]] && [[ -f tmp/$sourceDomain"_Release" ]]; then
			printf "%-${lTS}s%+${rTS}s\n" "[$sourceCountPadded] $sourceDomain's Release already exists" `formatNum $onlineReleaseFileSize`
		else
			# save release file as $sourceDomain"_Release"
			printf "%-${lTS}s%+${rTS}s\n" "[$sourceCountPadded] downloading $sourceDomain Release file" `formatNum $onlineReleaseFileSize`
			curl --connect-timeout 3 -m 180 -L -A "Telesphoreo APT-HTTP/1.0.592" -H "X-Machine: iPhone8,1" -H "X-Firmware: 10.2" -H "X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" -# $url/Release --output "tmp/$sourceDomain"_Release""
			if [ $? -ne 0 ]; then
				continue
			fi
		fi
	fi

	# if Release file exists
	if $releaseFileExistsOnline; then
		# Determining the extension of the Packages file in according to priority (compressed or not) ***in Release file***
		bz2MatchesNum=$(cat tmp/$sourceDomain"_Release" | grep "Packages.bz2$" | awk 'NF>1{print $NF}' | uniq | wc -l)
		gzMatchesNum=$(cat tmp/$sourceDomain"_Release" | grep "Packages.gz$" | awk 'NF>1{print $NF}' | uniq | wc -l)
		plainMatchesNum=$(cat tmp/$sourceDomain"_Release" | grep "Packages$" | awk 'NF>1{print $NF}' | uniq | wc -l)
		if [ $bz2MatchesNum -gt 0 ]; then
			packagesFileExtension=".bz2"
			matchesNum=$bz2MatchesNum
		elif [ $gzMatchesNum -gt 0 ]; then
			packagesFileExtension=".gz"
			matchesNum=$gzMatchesNum
		elif [ $plainMatchesNum -gt 0 ]; then
			packagesFileExtension=""
			matchesNum=$plainMatchesNum
		else
			crawling=true
		fi
	else
		# there is no Release file
		crawling=true
	fi

	# if NOT crawling
	if ! $crawling; then
		if [ $matchesNum -eq 1 ]; then
			pacFile=$(cat tmp/$sourceDomain"_Release" | grep "Packages$packagesFileExtension$" | awk 'NF>1{print $NF}' | uniq)
			downloadPackagesFile $url $pacFile $sourceDomain $sourceCountPadded $packagesFileExtension
		elif [ $matchesNum -gt 1 ]; then
			cat tmp/$sourceDomain"_Release" | grep "Packages$packagesFileExtension$" | awk 'NF>1{print $NF}' | uniq 2>/dev/null >tmp/PackagesFileInfo
			count=0
			while read -r pacFile; do
				downloadPackagesFile $url $pacFile $sourceDomain $sourceCountPadded $packagesFileExtension $count
				((count++))
			done<tmp/PackagesFileInfo
			rm -f tmp/PackagesFileInfo &>/dev/null
		fi
	else
		# Crawling HERE
		# Check if Packages file exists online *** Crawling ***
		# if no Release file OR no entry in it for Packages file
		if [[ `wget -U "Telesphoreo APT-HTTP/1.0.592" --header="X-Machine: iPhone8,1" --header="X-Firmware: 10.2" --header="X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" -S --spider $url/Packages.bz2  2>&1 | grep 'HTTP/1.1 200 OK'` ]]; then
			pacFile="Packages.bz2"
			packagesFileExtension=".bz2"
		else
			if [[ `wget -U "Telesphoreo APT-HTTP/1.0.592" --header="X-Machine: iPhone8,1" --header="X-Firmware: 10.2" --header="X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" -S --spider $url/Packages.gz  2>&1 | grep 'HTTP/1.1 200 OK'` ]]; then
				pacFile="Packages.gz"
				packagesFileExtension=".gz"
			else
				if [[ `wget -U "Telesphoreo APT-HTTP/1.0.592" --header="X-Machine: iPhone8,1" --header="X-Firmware: 10.2" --header="X-Unique-ID: 11dfe7e2d339e8a595b5f73e0c888926f2dac21c" -S --spider $url/Packages  2>&1 | grep 'HTTP/1.1 200 OK'` ]]; then
					pacFile="Packages"
					packagesFileExtension=""
				else
					printf "%-${lTS}s${RED}%+${rTS}s${NOC}\n" "[$sourceCountPadded] Couldn't find $sourceDomain Packages file" "FAILED"
					echo $url
					continue
				fi
			fi
		fi

		# After its found download it
		downloadPackagesFile $url $pacFile $sourceDomain $sourceCountPadded $packagesFileExtension
	fi

	# Here will search in Packages files for needed packages
	#: <<'end_long_comment'
	needed=false
	packageName=Null
	readPackageName=true
	while read -r PackagesFileName; do
		while read -r lineInPackages; do
			# if the line is empty (between packages)
			if [ -z "$lineInPackages" ]; then
				packageName=""
				readPackageName=true
				needed=false # Don't know, check next
				continue
			fi
			
			# if the line is NOT needed and doesn't require reading the package name (the last line is not empty)
			if ! $needed && ! $readPackageName; then
				continue
			fi

			if $readPackageName; then
				packageNameTMP=$(echo $lineInPackages | grep "^Package" | awk -F': ' '{print $2}')
				if [ $? -eq 0 ]; then
					packageName=$packageNameTMP
					readPackageName=false

					while read -r lineInNeededPackages; do
						if [[ $lineInNeededPackages == $packageName ]]; then
							if $constructPackagesFile; then
								echo "" >> $constructFile
							fi
							needed=true
							((packageCount++))
							break
						fi
					done <$neededPackagesFile
				else
					continue
				fi
			fi

			if $needed && $constructPackagesFile; then
				echo "$lineInPackages" >> $constructFile
			fi

			if $needed && $downloadDebs; then # and begins with Filename
				######################################################## Download deb
			fi
		done < tmp/$PackagesFileName
	done < tmp/PackagesFiles
	rm -f tmp/PackagesFiles
	printf "%-${lTS}s${GRN}%+${rTS}s${NOC}\n" "[$sourceCountPadded] $packageCount Packages needed at $sourceDomain" "FOUND"
	packageAllCount=$((packageAllCount+packageCount))
#end_long_comment
done <$sourcesFile

printf "%s\n" "[+++] Found $packageAllCount Packages needed"