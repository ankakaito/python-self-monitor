----------------------------------------------------------------------------------------------------------------------------
Read Me IF Your Want This Script Runing Well On Your System
----------------------------------------------------------------------------------------------------------------------------

Tested : Ubuntu 20.04 with Python Virtual Environment ( For Python 3.xx Version)

- Frist Think you want use this script is Creating Telegram BOT with bot Father and get the token and chat ID ( IT MUST )

creating Python Virtual Environment

1. $ python3 venv path_venv
2. $ source path_venv/bin/activate

- after virtual environment activated, install requests psutil

(path_venv) $ pip3 install requests psutil

- edit the .py file ( token, chat_id telegram, path file and log file where you want to place) 
----------------------------------------------------------------------------------------------------------------------------
- The Next Step is open and edit the self-watchdog-monitor.service, change with the path where you place the .py script and
Where the Python Environment was your created.

- After editing the script, now you must Move the .service file to /etc/systemd/system

- reload the daemon
- enable the script
- start 
- done

Knowing Bug You Tell Me
