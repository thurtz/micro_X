# **micro\_X Setup Instructions for Termux (Android)**

This guide will walk you through setting up the micro\_X intelligent shell environment on your Android device using Termux.

## **Overview**

Termux is a powerful terminal emulator and Linux environment for Android. This guide will help you install micro\_X and its dependencies within Termux.

**Note:** Running large language models directly on a mobile device can be resource-intensive (CPU, RAM, storage). Performance will vary depending on your device's capabilities. Ensure you have sufficient free storage before proceeding.

## **Prerequisites**

1. **Termux App:** Install Termux from F-Droid. It's recommended to get it from F-Droid to ensure you have the latest updates and avoid issues with the Play Store version.  
2. **Internet Connection:** For downloading packages and Ollama models.  
3. **Sufficient Storage:** Ollama models can be several gigabytes in size.

## **Setup Steps**

You can either follow the automated setup script (recommended) or perform a manual setup.

### **Method 1: Using the Setup Script (Recommended)**

1. **Open Termux.**  
2. Update Termux Packages:  
   It's always a good idea to start with up-to-date packages:  
   pkg update \-y && pkg upgrade \-y

3. **Install Git (if not already installed):**  
   pkg install git \-y

4. **Clone the micro\_X Repository:**  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X

5. Make the Termux Setup Script Executable:  
   (Assuming the script is named setup\_micro\_x\_termux.sh in the repository)  
   chmod \+x setup\_micro\_x\_termux.sh

6. **Run the Termux Setup Script:**  
   ./setup\_micro\_x\_termux.sh

   * The script will guide you through:  
     * Installing necessary Termux packages (python, tmux).  
     * Guiding you through the manual steps for Ollama installation if ollama is not detected.  
     * Asking if you want to pull the required Ollama models.  
     * Setting up the Python virtual environment (.venv).  
     * Installing Python dependencies (prompt\_toolkit, ollama).  
     * Making main.py and micro\_X.sh executable.  
   * Follow any on-screen prompts.

### **Method 2: Manual Setup**

If you prefer or if the script encounters issues, follow these manual steps:

1. **Open Termux.**  
2. **Update Termux Packages:**  
   pkg update \-y && pkg upgrade \-y

3. **Install Prerequisites:**  
   pkg install python python-pip tmux git \-y

   *(Note: python-pip might be installed as part of python in recent Termux versions).*  
4. **Install Ollama on Termux:**  
   * As of now, Ollama doesn't have an official pkg release for Termux. You'll likely need to install it manually.  
   * **Check for Community Packages (Optional First Step):**  
     pkg search ollama

     If a community package exists and you trust it, you might try installing it. Otherwise, proceed with manual installation.  
   * **Manual Installation (ARM64 Example):**  
     1. Go to the Ollama releases page: [https://github.com/ollama/ollama/releases](https://github.com/ollama/ollama/releases)  
     2. Find the latest release and look for the ollama-linux-arm64 binary. Copy its download URL.  
     3. In Termux, download it (replace \<URL\> with the actual URL):  
        curl \-Lo ollama-linux-arm64 \<URL\_TO\_OLLAMA\_LINUX\_ARM64\_BINARY\>

        Example (this URL will become outdated, always get the latest from GitHub releases):  
        curl \-Lo ollama-linux-arm64 https://github.com/ollama/ollama/releases/download/v0.1.30/ollama-linux-arm64  
     4. Make it executable:  
        chmod \+x ollama-linux-arm64

     5. Move it to a directory in your PATH, for example $PREFIX/bin:  
        mv ollama-linux-arm64 $PREFIX/bin/ollama

     6. Verify installation:  
        ollama \--version

5. **Clone the micro\_X Repository:**  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X

6. **Create Python Virtual Environment:**  
   python \-m venv .venv

7. **Activate Virtual Environment:**  
   source .venv/bin/activate

8. Install Python Dependencies:  
   If requirements.txt is not present in the cloned repository, create it:  
   \# requirements.txt  
   prompt\_toolkit\>=3.0.0  
   ollama\>=0.1.0

   Then install:  
   pip install \-r requirements.txt

9. **Make Scripts Executable:**  
   chmod \+x main.py  
   chmod \+x micro\_X.sh

10. **Pull Ollama Models:**  
    * **First, start the Ollama server.** Open a **new Termux session** (swipe from the left edge and tap "New session") and run:  
      ollama serve

      Leave this session running in the background.  
    * **In your original Termux session** (where you cloned micro\_X and activated the venv), pull the models:  
      ollama pull llama3.2:3b  
      ollama pull vitali87/shell-commands-qwen2-1.5b  
      ollama pull herawen/lisa:latest

      *(Note: llama3.2:3b is \~1.6GB. Consider smaller models if storage/performance is a concern, but ensure they are compatible with micro\_X's prompting.)*

## **Running micro\_X in Termux**

1. **Start Ollama Server:**  
   * Open a **new Termux session**.  
   * Run ollama serve.  
   * **Keep this session running in the background.** micro\_X needs to connect to this server.  
2. **Launch micro\_X:**  
   * Open **another Termux session** (or use your existing one where you did the setup).  
   * Navigate to the micro\_X directory:  
     cd /path/to/your/micro\_X \# e.g., cd micro\_X if you cloned it in $HOME

   * **Using the launch script (micro\_X.sh \- Recommended):**  
     ./micro\_X.sh

     This script should activate the virtual environment and start micro\_X within a tmux session.  
   * **Running main.py directly:**  
     source .venv/bin/activate  \# If not already active or if micro\_X.sh doesn't handle it  
     python main.py             \# Or ./main.py

## **Important Notes for Termux Users**

* **Background Processes:** Termux can be aggressive in killing background processes to save battery. You might need to acquire a partial wakelock for the session running ollama serve if you find it's being stopped.  
  * Long-press in Termux, tap "More...", then "Wakelock".  
* **Performance:** LLM performance will heavily depend on your device's CPU and available RAM. Smaller models are generally recommended for on-device use.  
* **Storage:** Models take up significant storage space.  
* **tmux Usage:** micro\_X uses tmux. Familiarize yourself with basic tmux commands if needed (e.g., Ctrl+b d to detach, tmux attach-session \-t micro\_X to reattach). Your micro\_X.sh script handles session creation/attachment.

Enjoy using micro\_X on Termux\!