E-Ink 7.5 inch Display Project

*******************************************************************************************************
This repo includes a file named:

    'dummy.env'

this file must be populated with personal values/IP's/etc. and renamed to:

    '.env' 

for this project to fully function.

This project is also reliant on a number of external python modules. I recommend just cloning and attempting to run
the main.py program and seeing which libraries you do/dont have installed, and installing any missing libs as needed
*******************************************************************************************************

This project is designed to display the following items on a waveshare 7.5 inch e ink display
- Date
- Time
- current Temperature
- current Chance of precipitation
- Desktop statistics
    - CPU % utilized
    - CPU temperature
    - GPU % utilized
    - GPU temperature
    - Memory % utilized
- Server Statistics
    - CPU % utilized
    - CPU temperature
    - Memory % utilized
- Statistics for the Pi the program/display is running from
    - CPU % utilized
    - CPU temperature
    - Memory % utilized
- 3D Printing Job statuses
    - Displays whether the printer is Idle,Paused,Printing,or Finished with a job
    - When printing, progress bar that reflects job % complete
    - Also displays numerical job % complete value
    - Displays remaining time in 'Xh Xm left' format
    - Displays current layer as a fraction out of the total layer count
- Container Statistics
    - 2 columns are present, one for the local raspberry pi device and 1 for the Server
    - Each column will display a bulleted list of all docker containers running on that respective device
    - If the container is in an unhealthy state, its bullet will show as a white circle instead of solid black.
    - if a container is gracefully stopped it will drop from the list

    Note:
    Upon completion of the core development of the project, 
    non-necessary files were moved to 'extra' for ease of use of the project.
    These files may need to be moved to the base dir to function
