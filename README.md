# archive_upload
Pure Python tool to upload mp3 archives to a Creek.fm back end

This tool pre-supposes that you have two sets of audio recordings in a single folder:
1. timed-recording: a set of 30 minute long recordings that are always being made
2. stream-recording: a set of recordings made by your streaming client (such as Darkice: http://darkice.org/)

You must have the following components installed, commands apply to raspbian, but any debian based Linux system should use the same commands:

Python 3: the core intepreter for this script
> sudo apt install python3

ffmpeg: a tool used to edit mpeg files such as mp3s, in this case used to properly join together the 30 minute recordings into a full show
Linux/Raspberry Pi:
> sudo apt install ffmpeg
Windows:
- Download from one of the official windows binaries build, and place in the working folder with the .yml and .py file (usually, c:\archive_upload)

The following python libraries are required:
- os: used for finding files on disk
- sys: used for argument handling
- shutil: used for fancy copy routines
- glob: used for searching folders
- logging: used for writing log files
- time: used for sleeping
- datetime: used for timestamp and elapsed time calculations
- apscheduler: used for sleep routines on Windows platforms
- urllib: used for communicating with websites (your Creek.fm backend APIs)
- boto3: used for uploading files to an S3 or digital ocean bucket
- json: used for parsing JSON responses from Creek.fm APIs
- yaml: used to parse the configuration file
- subprocess: used to spawn the ffmpeg concatenation process
- mutagen: used to edit and read MP3 tags

To install:
> sudo pip3 install glob3 apscheduler urllib3 boto3 pyyaml mutagen

The other packages should all come with the base python3 install

To run: 
------
1. Edit the archive_upload.yml file with the correct values for your installation
   a. On linux, the audio_folder config should be the full path, e.g. "/home/user/audio/backup/"
   b. On Windows, the audio_folder config should be the full path, with linux slashes, e.g. "C:/audio/backup/"
3. Test by running once:

> python3 archive_upload.py now

3. Schedule
  - In Linux:
 
> crontab -e

(select an editor, if needed, if you aren't sure, select nano)
Add the following line:

> 15,45 * * * * /home/pi/archive_upload/archive_upload.sh

You may have to modify the line to include the correct path to the installation folder and script.

You can either add a scheduled task to windows, or just execute the script - it will attempt to run 15 minutes past the hour and half hour mark.

**STUDIOS WITH TIMED RECORDINGS MUST BE SCHEDULED AFTER STUDIOS WITH STREAM (ON DEMAND) RECORDINGS, OR THE STUDIO PARAMETERS MUST BE SET IN CREEK AND IN THE CONFIG**
If you don't heed this rule, you will probably get scheduled recordings from the incorrect studio uploaded to creek.
