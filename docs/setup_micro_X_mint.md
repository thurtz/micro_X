## **micro\_X Setup Instructions**

Welcome to micro\_X\! This guide will help you set up the micro\_X intelligent shell environment.

**Primary Method for Linux Mint Users: Using the Setup Script (Recommended)**

If you are on Linux Mint (or a compatible Debian-based system), the easiest way to set up micro\_X is by using the provided setup script.

1. **Download Files:**  
   * Ensure you have the following files in the same directory (e.g., \~/micro\_x/):  
     * main.py (the main application)  
     * micro\_X.sh (the launch script)  
     * micro\_X.desktop (the desktop shortcut file)  
     * setup.sh (or setup\_micro\_x\_mint.sh \- the setup script itself)  
2. **Open Your Terminal:**  
   * Navigate to the directory where you downloaded the files:  
     cd /path/to/your/micro\_x\_directory

3. **Make the Setup Script Executable:**  
   chmod \+x setup.sh

   (If your script is named setup\_micro\_x\_mint.sh, use that name instead).  
4. **Run the Setup Script:**  
   ./setup.sh

   * The script will guide you through the process, which includes:  
     * Checking and offering to install system prerequisites like Python 3, pip, python3-venv, and tmux.  
     * Checking for Ollama and advising on its installation if missing.  
     * Attempting to pull the required Ollama language models (llama3.2:3b, vitali87/shell-commands-qwen2-1.5b, herawen/lisa:latest).  
     * Creating a Python virtual environment named .venv in the current directory.  
     * Creating a requirements.txt file if it doesn't exist.  
     * Installing necessary Python packages (prompt\_toolkit, ollama) into the virtual environment.  
     * Making main.py and micro\_X.sh executable.  
     * Asking if you want to install the micro\_X.desktop file to your local applications menu for easy launching.  
5. **Follow On-Screen Prompts:**  
   * The script may ask for your password (sudo) to install system packages.

**Manual Setup (For other Linux distributions or if you prefer manual control)**

1. **Prerequisites:**  
   * **Python:** Version 3.8+ (python3 \--version).  
   * **pip:** (pip3 \--version).  
   * **python3-venv:** (e.g., sudo apt install python3-venv on Debian/Ubuntu).  
   * **tmux:** (e.g., sudo apt install tmux).  
   * **Ollama:** Install from [ollama.com](https://ollama.com/) and ensure the service is running.  
2. **Download micro\_X Files:**  
   * Place main.py, micro\_X.sh (if using), and micro\_X.desktop (if using) in your desired project directory.  
3. Install Ollama Models:  
   Open your terminal and run:  
   ollama pull llama3.2:3b  
   ollama pull vitali87/shell-commands-qwen2-1.5b  
   ollama pull herawen/lisa:latest

4. **Create Python Virtual Environment:**  
   cd /path/to/your/micro\_x\_directory  
   python3 \-m venv .venv

5. **Activate Virtual Environment:**  
   source .venv/bin/activate

   *(You'll need to do this every time you open a new terminal to run micro\_X manually).*  
6. Install Python Dependencies:  
   Create a requirements.txt file in your project directory:  
   prompt\_toolkit\>=3.0.0  
   ollama\>=0.1.0

   Then install:  
   pip3 install \-r requirements.txt

7. **Make Scripts Executable:**  
   chmod \+x main.py  
   chmod \+x micro\_X.sh  \# If you have this launch script

8. **Install Desktop File (Optional Manual):**  
   * If you have micro\_X.desktop and micro\_X.sh:  
     1. Edit micro\_X.desktop. Change the Exec= line to use the absolute path to your micro\_X.sh script. For example:  
        Exec=/home/your\_user/path/to/micro\_x\_directory/micro\_X.sh  
     2. If your Icon= line uses a relative path, change it to an absolute path to your icon file.  
     3. Copy the modified micro\_X.desktop to \~/.local/share/applications/.  
     4. Run update-desktop-database \~/.local/share/applications/ if the command is available.

**Running micro\_X**

1. **Ensure Ollama is Running:** The Ollama application/service must be active.  
2. **Launching:**  
   * **If you used the setup script and installed the desktop entry:** Look for "micro\_X" in your desktop's application menu.  
   * Using the micro\_X.sh launch script (Recommended for terminal):  
     Navigate to your micro\_X directory in the terminal and run:  
     ./micro\_X.sh

     *(This script should handle activating the virtual environment).*  
   * Running main.py directly (Manual):  
     Navigate to your micro\_X directory:  
     cd /path/to/your/micro\_x\_directory  
     source .venv/bin/activate  \# Activate virtual environment  
     ./main.py                  \# Or python3 main.py

**First Run and Configuration Files**

micro\_X will automatically create the following in its directory:

* logs/micro\_x.log: For logging.  
* config/command\_categories.json: Stores command categorizations.  
* .micro\_x\_history: Stores command history.

Enjoy using micro\_X\!