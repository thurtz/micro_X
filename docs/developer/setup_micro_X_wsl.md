# **micro\_X Setup Instructions for WSL (Windows Subsystem for Linux)**

This guide will walk you through setting up the micro\_X intelligent shell environment within your WSL (Windows Subsystem for Linux) instance, configured to communicate with an Ollama server running on your Windows host.

## **Overview**

This setup allows you to run micro\_X in a Linux environment (WSL) while leveraging Ollama running natively on your Windows host, which can be beneficial for performance, especially if Ollama on Windows has GPU access.

**Key Assumptions:**

* You have WSL (preferably WSL2) installed and a Linux distribution (e.g., Ubuntu) set up.  
* Ollama will be installed and run on your **Windows host machine**, not directly inside WSL for serving models.  
* micro\_X and its Python environment will be set up **inside your WSL distribution**.

## **Prerequisites**

1. **WSL Installed:** Ensure WSL is installed and you have a Linux distribution running.  
2. **Ollama for Windows:**  
   * Download and install Ollama for Windows from [ollama.com](https://ollama.com/).  
   * After installation, **run the Ollama application on Windows**. It should run in the background (often with an icon in the Windows system tray).  
3. **Windows Firewall (Potential Step):**  
   * Ensure your Windows Firewall allows inbound connections to the Ollama server (default port 11434\) from your WSL instance. WSL2 generally has good networking integration with localhost, but if you encounter connection issues from WSL to Ollama on Windows, you might need to create a firewall rule.  
     * Open Windows Defender Firewall.  
     * Go to "Advanced settings".  
     * "Inbound Rules" \-\> "New Rule..."  
     * Rule Type: Port, Protocol: TCP, Specific local ports: 11434\.  
     * Action: Allow the connection.  
     * Profile: Choose appropriate profiles (Private is usually sufficient, Domain if applicable).  
     * Name: e.g., "Ollama WSL Access".  
4. **Internet Connection:** For downloading packages and Ollama models.

## **Setup Steps**

The recommended way to set up the WSL portion of micro\_X is by using the provided setup script *inside your WSL terminal*.

### **Method 1: Using the Setup Script (Recommended for WSL part)**

1. **Open your WSL Terminal.** (e.g., Ubuntu).  
2. **Ensure Ollama is Installed and Running on Windows Host:** Before running the WSL setup script, confirm Ollama is installed and the application is running on your Windows machine.  
3. **Pull Ollama Models (on Windows Host):**  
   * The micro\_X setup script for WSL will remind you, but it's best to do this from your Windows host where the Ollama server is running.  
   * Open PowerShell or Command Prompt on Windows and run:  
     ollama pull llama3.2:3b  
     ollama pull vitali87/shell-commands-qwen2-1.5b  
     ollama pull herawen/lisa:latest

   * These models are required by micro\_X.  
4. Clone the micro\_X Repository into WSL:  
   If you haven't already, clone the repository into your WSL filesystem (e.g., in your WSL home directory):  
   \# Inside WSL terminal  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X

5. Make the WSL Setup Script Executable:  
   (Assuming the script is named setup\_micro\_x\_wsl.sh in the repository)  
   \# Inside WSL terminal, in the micro\_X directory  
   chmod \+x setup\_micro\_x\_wsl.sh

6. **Run the WSL Setup Script:**  
   \# Inside WSL terminal, in the micro\_X directory  
   ./setup\_micro\_x\_wsl.sh

   * The script will guide you through:  
     * Updating WSL package lists and installing necessary packages (python3, python3-pip, python3-venv, tmux).  
     * Reminding you about Ollama on the Windows host and model pulling.  
     * Setting up the Python virtual environment (.venv) within WSL.  
     * Installing Python dependencies (prompt\_toolkit, ollama) into the virtual environment.  
     * Making main.py and micro\_X.sh executable.  
     * Providing crucial reminders about the OLLAMA\_HOST environment variable.  
   * Follow any on-screen prompts. The script may ask for your password (sudo) to install system packages within WSL.

### **Method 2: Manual Setup (Inside WSL)**

If you prefer or if the script encounters issues:

1. **Open your WSL Terminal.**  
2. **Ensure Ollama is Installed and Running on Windows Host** and that you have **Pulled the Required Models on the Windows Host** (see steps 2 & 3 from Method 1).  
3. **Update WSL Packages:**  
   sudo apt update && sudo apt upgrade \-y

4. **Install Prerequisites in WSL:**  
   sudo apt install python3 python3-pip python3-venv tmux git \-y

5. **Clone the micro\_X Repository into WSL (if not done):**  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X

6. **Create Python Virtual Environment in WSL:**  
   python3 \-m venv .venv

7. **Activate Virtual Environment in WSL:**  
   source .venv/bin/activate

8. Install Python Dependencies in WSL:  
   If requirements.txt is not present, create it:  
   \# requirements.txt  
   prompt\_toolkit\>=3.0.0  
   ollama\>=0.1.0

   Then install:  
   pip3 install \-r requirements.txt

9. **Make Scripts Executable in WSL:**  
   chmod \+x main.py  
   chmod \+x micro\_X.sh

## **Crucial: Configuring OLLAMA\_HOST in WSL**

For micro\_X running in WSL to communicate with the Ollama server running on your Windows host, the ollama Python library needs to know the server's address. You do this by setting the OLLAMA\_HOST environment variable **inside your WSL environment**.

* **For WSL2 (most common):** The Windows host is typically accessible at http://localhost:11434 from within WSL.  
* **For older WSL1 or specific network configurations:** You might need to use the IP address of your Windows machine's virtual Ethernet adapter for WSL. localhost should be tried first.

**How to set OLLAMA\_HOST:**

1. **Temporarily (for the current WSL session):**  
   export OLLAMA\_HOST=http://localhost:11434

   You'll need to do this every time you open a new WSL terminal to run micro\_X, unless your micro\_X.sh script sets it.  
2. Permanently (Recommended):  
   Add the export line to your WSL shell's configuration file.  
   * If using bash (default for Ubuntu in WSL):  
     echo 'export OLLAMA\_HOST=http://localhost:11434' \>\> \~/.bashrc  
     source \~/.bashrc

   * If using zsh:  
     echo 'export OLLAMA\_HOST=http://localhost:11434' \>\> \~/.zshrc  
     source \~/.zshrc

This ensures the variable is set every time you open a WSL terminal.

3. Verify Connectivity:  
   After setting OLLAMA\_HOST and ensuring Ollama is running on Windows, you can test connectivity from WSL:  
   \# Install curl if you don't have it: sudo apt install curl \-y  
   curl http://localhost:11434

   You should see a response like "Ollama is running". If not, troubleshoot your OLLAMA\_HOST setting, Ollama server status on Windows, and Windows Firewall.

## **Running micro\_X (from WSL)**

1. **Ensure Ollama is Running on your Windows Host.**  
2. **Ensure OLLAMA\_HOST is correctly set in your WSL environment.**  
3. **Open your WSL Terminal.**  
4. **Navigate to the micro\_X directory:**  
   cd /path/to/your/micro\_X \# e.g., cd micro\_X if cloned in WSL home

5. **Launch micro\_X:**  
   * **Using the launch script (micro\_X.sh \- Recommended):**  
     ./micro\_X.sh

     *(This script should activate the virtual environment and start micro\_X within a tmux session. It might also be a good place to set OLLAMA\_HOST if not done globally).*  
   * **Running main.py directly:**  
     source .venv/bin/activate  \# If not already active  
     python3 main.py            \# Or ./main.py

Enjoy using micro\_X with WSL and Ollama on Windows\!