# **micro\_X Setup Instructions for macOS**

This guide will walk you through setting up the micro\_X intelligent shell environment on your macOS device.

## **Overview**

micro\_X can be run on macOS, leveraging Homebrew for package management and the official Ollama macOS application.

## **Prerequisites**

1. **macOS:** A relatively recent version of macOS.  
2. **Homebrew:** The missing package manager for macOS. If you don't have it, the setup script will attempt to install it, or you can install it from [brew.sh](https://brew.sh/).  
3. **Python 3:** A version installed via Homebrew (e.g., Python 3.9+) is recommended over the system Python. The setup script will handle this.  
4. **tmux:** A terminal multiplexer. The setup script will install this via Homebrew.  
5. **Ollama macOS Application:** Download and install from [ollama.com](https://ollama.com/). Ensure the application is running for micro\_X to function.  
6. **Internet Connection:** For downloading Homebrew, packages, and Ollama models.  
7. **Sufficient Storage:** Ollama models can be several gigabytes.

## **Setup Steps**

The recommended way to set up micro\_X on macOS is by using the provided setup script.

### **Method 1: Using the Setup Script (Recommended)**

1. **Open Terminal.** (You can find it in /Applications/Utilities/Terminal.app or via Spotlight).  
2. **Clone the micro\_X Repository (if you haven't already):**  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X

   *(If you've downloaded the files as a ZIP, navigate to the extracted micro\_X directory).*  
3. Make the macOS Setup Script Executable:  
   (Assuming the script is named setup\_micro\_x\_mac.sh in the repository)  
   chmod \+x setup\_micro\_x\_mac.sh

4. **Run the macOS Setup Script:**  
   ./setup\_micro\_x\_mac.sh

   * The script will guide you through:  
     * Checking for and installing Homebrew if missing.  
     * Installing/updating necessary Homebrew packages (python, tmux).  
     * Guiding you to install the Ollama macOS application if the ollama command isn't found.  
     * Asking if you want to pull the required Ollama models (requires the Ollama app to be running).  
     * Setting up the Python virtual environment (.venv).  
     * Installing Python dependencies (prompt\_toolkit, ollama).  
     * Making main.py and micro\_X.sh executable.  
   * Follow any on-screen prompts. The script might ask for your password for Homebrew installation if it's the first time.

### **Method 2: Manual Setup**

If you prefer manual control or if the script encounters issues:

1. **Open Terminal.**  
2. Install Homebrew (if not installed):  
   Follow instructions at brew.sh.  
   /bin/bash \-c "$(curl \-fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

   Ensure Homebrew is correctly added to your PATH (the installer usually provides instructions).  
3. **Install Prerequisites via Homebrew:**  
   brew install python tmux

   *(This will install a modern version of Python 3 and tmux).*  
4. **Install Ollama macOS Application:**  
   * Download the .dmg from [ollama.com](https://ollama.com/) and install it.  
   * Launch the Ollama application. You should see an Ollama icon in your menu bar.  
5. **Clone the micro\_X Repository (if not done):**  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X

6. Create Python Virtual Environment:  
   Use the Homebrew-installed Python:  
   python3 \-m venv .venv

7. **Activate Virtual Environment:**  
   source .venv/bin/activate

8. Install Python Dependencies:  
   If requirements.txt is not present, create it:  
   \# requirements.txt  
   prompt\_toolkit\>=3.0.0  
   ollama\>=0.1.0

   Then install:  
   pip3 install \-r requirements.txt

9. **Make Scripts Executable:**  
   chmod \+x main.py  
   chmod \+x micro\_X.sh

10. **Pull Ollama Models:**  
    * Ensure the Ollama macOS application is running.  
    * In your terminal (with the virtual environment active):  
      ollama pull llama3.2:3b  
      ollama pull vitali87/shell-commands-qwen2-1.5b  
      ollama pull herawen/lisa:latest

## **Running micro\_X on macOS**

1. **Ensure Ollama Application is Running:** Check for the Ollama icon in your macOS menu bar.  
2. **Launch micro\_X:**  
   * Using the launch script (micro\_X.sh \- Recommended):  
     Navigate to your micro\_X directory in the terminal:  
     cd /path/to/your/micro\_X\_directory  
     ./micro\_X.sh

     *(This script should activate the virtual environment and start micro\_X within a tmux session).*  
   * Running main.py directly:  
     Navigate to your micro\_X directory:  
     cd /path/to/your/micro\_X\_directory  
     source .venv/bin/activate  \# Activate virtual environment  
     python3 main.py            \# Or ./main.py

   * Using a Shell Alias (Convenient):  
     If you followed the setup script's suggestion (or do it manually), you might have an alias.  
     1. Add to your shell configuration file (e.g., \~/.zshrc for Zsh, which is default on modern macOS, or \~/.bash\_profile):  
        alias microx='cd "/path/to/your/micro\_X\_directory" && ./micro\_X.sh'

        (Replace /path/to/your/micro\_X\_directory with the actual absolute path).  
     2. Source your shell config: source \~/.zshrc (or your respective file).  
     3. Now you can just type microx in any new terminal window.

## **Important Notes for macOS Users**

* **Ollama App:** The Ollama macOS application handles running the Ollama server. Keep it running when you want to use micro\_X.  
* **tmux Usage:** micro\_X uses tmux. Your micro\_X.sh script handles session creation/attachment. Basic tmux commands:  
  * Detach from session: Ctrl+b then d  
  * Reattach to session: tmux attach-session \-t micro\_X (or the session name used in micro\_X.sh)

Enjoy using micro\_X on your Mac\!