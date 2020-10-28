# basic os functions
import os, sys

# used for copying files
import shutil

# find specific filenames
import glob

# logging
import logging
from logging.handlers import RotatingFileHandler

# scheduling imports
import time
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# connecting to the website - get next show
import urllib.request
from urllib.parse import urlencode

#upload files to s3
import boto3

# json parsing - get next show
import json

# yaml parsing - config
import yaml

# invoke subprocesses
import subprocess

# MP3 tag editing
from mutagen.id3 import ID3NoHeaderError, ID3v1SaveOptions
from mutagen.id3 import ID3, TIT2, TALB, TPE1

#MP3 length checking
from mutagen.mp3 import MP3

__author__ = 'forrest'

# TODO: log to file and console
# TODO: daemonize
# TODO: Auto Rerun (second to last show in podcast RSS)

# main function
def upload_files():
    logger.name = 'bff.upload_files'
    logger.info("Starting process")

    # Config params
    audio_folder = config["audio_folder"]
    station_url = config["station_url"]
    creek_key = config["creek_key"]
    s3_bucket_name = config['s3_bucket_name']
    s3_access_key_id = config['s3_access_key_id']
    s3_secret = config['s3_secret']
    s3_endpoint = config['s3_endpoint']

    # list missing recordings
    # download json
    missing_url = "api/broadcasts/missing_archives"
    full_missing_url = station_url + missing_url
    logger.debug("Missing archives URL: " + full_missing_url)
    response = urllib.request.urlopen(full_missing_url)
    str_response = response.read().decode('utf-8')
    logger.debug("string response: " + str_response)
    broadcasts = json.loads(str_response)
    logger.debug("json response: ")
    logger.debug(broadcasts)

    for broadcast in broadcasts['data']['broadcasts']: # Each missing broadcast
        logger.debug("Working on a broadcast: ")
        logger.debug(broadcast)
        show_name = broadcast['program_title']
        title = broadcast['broadcast_title']
        logger.info("Missing a recording for " + show_name + ", episode: " + title)
        local_filename = broadcast['media_basename']

        # match missing recordings to local recordings
        start_time = broadcast['broadcast_start']
        end_time = broadcast['broadcast_end']
        logger.debug("Looking for files between " + start_time + " and " + end_time)

        # broadcast_start: "2020-10-15 10:00:00"
        date = start_time[0:10] #first 10 characters should be the date
        logger.debug("date: " + date)

        start_hour = int(start_time[11:13])
        logger.debug("starting hour: " + str(start_hour))
        start_min = int(start_time[14:16])
        logger.debug("starting minute: " + str(start_min))

        # broadcast_end: "2020-10-15 12:00:00"
        end_hour = int(end_time[11:13])
        logger.debug("ending hour: " + str(end_hour))
        end_min = int(end_time[14:16])
        logger.debug("starting minute: " + str(end_min))

        # total seconds of broadcast
        time1 = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        time2 = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")


        broadcast_seconds = (time2 - time1).total_seconds()
        logger.debug("broadcast is " + str(broadcast_seconds) + " seconds long")
        short_broadcast_seconds = broadcast_seconds - 900
        long_broadcast_seconds = broadcast_seconds + 900
        logger.debug("shortest acceptable recording is " + str(short_broadcast_seconds) + " seconds and longest is " + str(long_broadcast_seconds))

        #if we can find a stream recording that matches
        #get files from that day, should be less than 50
        file_pattern = audio_folder + "stream_recording*" + date + "*"
        logger.debug("looking for files matching: " + file_pattern)
        file_names = glob.glob(file_pattern) # find matching files
        logger.debug("found files: ")
        logger.debug(file_names)

        if len(file_names) > 0: #found some stream recordings
            #we have some stream recordings to check
            file_names.sort() #lex sort gives us time based sort
            file_list = "" #initialize matching files
            for file_name in file_names:
                # stream_recording-2020-10-13_21-08-38.mp3
                logger.debug("checking " + file_name)
                hour = int(file_name[-12:-10])
                logger.debug("hour: " + str(hour))
                minutes = int(file_name[-9:-7])
                logger.debug("minutes: " + str(minutes))

                # check starting times
                min_minus_ten = start_min - 10
                min_plus_ten = start_min + 10
                if (start_hour, min_minus_ten) <= (hour,minutes) <= (start_hour, min_plus_ten):
                    audio = MP3(file_name) # read in MP3
                    file_seconds = audio.info.length #get length of audio in seconds
                    logger.debug("file is " + str(file_seconds) + " seconds long")
                    if (short_broadcast_seconds <= file_seconds <= long_broadcast_seconds):
                        logger.info("File : " + file_name + " is the file we are looking for, copying to " + local_filename)
                        shutil.copy2(file_name, local_filename) #copy stream recording to new file name
                        break

        if not os.path.exists(local_filename): # no stream recordings, check for timed recordings
            #get files from that day, should be less than 50
            file_pattern = audio_folder + "timed-recording*" + date + "*"
            logger.debug("looking for files matching: " + file_pattern)
            file_names = glob.glob(file_pattern) # find matching files
            logger.debug("found files: ")
            logger.debug(file_names)

            if len(file_names) < 1:
                logger.error("ERROR: No archives for that same day")
                continue #drop out of this broadcast

            #find specific records matching the times
            file_names.sort() #lex sort gives us time based sort
            file_list = "" #initialize matching files
            for file_name in file_names:
                # timed-recording-2020-10-15_14-00-01.mp3
                logger.debug("checking " + file_name)
                hour = int(file_name[-12:-10])
                logger.debug("hour: " + hour)
                minutes = int(file_name[-9:-7])
                logger.debug("minutes: " + minutes)
                if (start_hour, start_min) <= (hour, minutes) < (end_hour, end_min):
                    logger.debug("found a file to add: " + file_name)
                    file_list += "file '" + file_name + "'\n"

            if len(file_list) < 1:
                logger.error("Error: No Recordings match.")
                continue # drop out of this broadcast

            # construct full show from segments
            logger.debug("files to process:")
            logger.debug(file_list)
            logger.debug("writing file list to disk")
            with open("files.txt", "w") as text_file:
                text_file.write(file_list)
            logger.debug("local filename: " + local_filename)
            logger.debug("writing complete file to disk")

            logger.debug("Calling ffmepg")
            p = subprocess.Popen(['ffmpeg','-y','-f','concat','-safe','0','-protocol_whitelist','pipe,file','-hide_banner','-i','files.txt','-c','copy',local_filename])
            logger.debug("sending file names to ffmpeg")
            p.wait()

        # should have a file, local_file, that has a complete show to play

        # add mp3 tags
        if os.path.exists(local_filename):
            # set mp3 tags
            logger.debug("Adding mp3 tag")
            try:
                tags = ID3(local_filename)
            except ID3NoHeaderError:
                logger.debug("Adding ID3 header")
                tags = ID3()
            logger.debug("Constructing tag")
            # title
            title = broadcast['broadcast_title']
            tags["TIT2"] = TIT2(encoding=3, text=title)
            # album
            album = broadcast['program_title']
            tags["TALB"] = TALB(encoding=3, text=album)
            # artist
            artist = broadcast['program_title']
            tags["TPE1"] = TPE1(encoding=3, text=artist)

            logger.debug("Removing tags")
            tags.delete(local_filename)
            logger.debug("Saving tags")
            # v1=2 switch forces ID3 v1 tag to be written
            tags.save(filename=local_filename,
                      v1=ID3v1SaveOptions.CREATE,
                      v2_version=4)
        else:
            # we didn't make a file, nothing else to do for this broadcast
            continue

        # Upload file to S3
        logger.debug("Opening connection to S3")

        session = boto3.session.Session()
        client = session.client('s3',
                        endpoint_url="https://" + s3_endpoint,
                        aws_access_key_id=s3_access_key_id,
                        aws_secret_access_key=s3_secret)

        logger.debug("Uploading file")
        client.upload_file(local_filename,  # Path to local file
                   s3_bucket_name,  # Name of Space
                   broadcast['s3_object_name'])  # Name for remote file
        logger.debug("Upload complete")

        # set file to public
        logger.debug("Setting file to public access")
        response = client.put_object_acl(ACL='public-read', #ACL level
			Bucket=s3_bucket_name, # Bucket/name of space
			Key=broadcast['s3_object_name']) #name for remote file

        # Update creek
        archive_url = "api/media/add_archive?key="
        full_archive_url = station_url + archive_url + creek_key
        logger.debug("Add archives URL: " + full_archive_url)

        # add extra parameters to broadcast
        broadcast['_uploadDone'] = False
        broadcast['_audioFilesFound'] = None
        broadcast['_uploadPercent'] = None
        broadcast['filesize'] = os.path.getsize(local_filename)
        broadcast['file_format'] = 'mp3'

        logger.debug("ready to post to creek, broadcast: ")
        logger.debug(broadcast)

        data = urlencode(broadcast).encode()
        req = urllib.request.Request(full_archive_url, data=data) # this will "POST"
        resp = urllib.request.urlopen(req)
        logger.debug("Finished posting, response:")
        logger.debug(resp.status)
        
        # delete archives, if needed
        if os.path.exists(local_filename):
            logger.info("Removing temporary file: " + local_filename)
            os.remove(local_filename)

    # all broadcasts processed

    # remove files older than 3 months
    old_date = datetime.datetime.now() - datetime.timedelta(days=90)
    logger.debug("90 days ago was:")
    logger.debug(old_date)
    for dirpath, dirnames, filenames in os.walk(audio_folder):
       for file in filenames:
          curpath = os.path.join(dirpath, file)
          file_modified = datetime.datetime.fromtimestamp(os.path.getmtime(curpath))
          logger.debug("file was modified:")
          logger.debug(file_modified)
          if old_date < file_modified:
                logger.info("Removing file older than 3 months: " + curpath)
                os.remove(curpath)

    logger.info("Finished process")
    logger.name = __name__


if __name__ == '__main__':
    # MAIN PROCESS

    with open('archive_upload.yml', 'r') as f:
        config = yaml.load(f)

    # prep logging system
    log_path = config["log_path"]
    log_file_name = config["log_name"]
    log_level = config["log_level"]

    log_format = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # log to file
    log_file_handler = RotatingFileHandler(filename="{0}/{1}.log".format(log_path, log_file_name),
                                           maxBytes=10 * 1024 * 1024,  # 10 MB
                                           backupCount=20)
    log_file_handler.setFormatter(log_format)
    logger.addHandler(log_file_handler)

    # log to console
    log_console_handler = logging.StreamHandler()
    log_console_handler.setFormatter(log_format)
    logger.addHandler(log_console_handler)

    logger.info("Program Start")

    if(len(sys.argv) > 1):
        if(sys.argv[1] == "now"):
            logger.info("now switch passed, running once and exiting.")
            upload_files()
            sys.exit(0)

    # background scheduler is part of apscheduler class
    scheduler = BackgroundScheduler()
    # add a cron based (clock) scheduler for every 10 minutes, 40 minutes past
    scheduler.add_job(upload_files, 'cron', minute='10,40')
    scheduler.start()

    logger.info('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))

    try:
        # This is here to simulate application activity (which keeps the main thread alive).
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()  # Not strictly necessary if daemonic mode is enabled but should be done if possible

    logger.info("Program Stop")
