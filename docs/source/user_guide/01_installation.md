# **1. Installation and Setup**

micro_X can be run either through Docker (recommended for stability and ease of setup) or via a native installation.

## **Step 1: Docker Setup (Recommended)**

The fastest way to get started with a perfectly stable environment is using Docker.

1. **Launch the Docker Wrapper**:  
   ./docker-micro_X.sh

   The first time you run this, it will build a Debian Trixie image with all required dependencies (Python 3.13, Git, GitHub CLI, tmux).

2. **Host System Control**:  
   By default, micro_X in Docker is configured for **Host Breakout Mode**. Commands you run (including those from AI) will execute natively on your host system. Use the `!` prefix to force a host breakout for any manual command.

## **Step 2: Native Setup (Alternative)**

If you prefer to run micro_X directly on your operating system, follow these steps:

1. **Clone the Repository**:  
   git clone https://github.com/thurtz/micro_X.git  
   cd micro_X

2. **Run the Setup Script**:  
   ./setup.sh

   The script will guide you through installing all necessary dependencies for your operating system, including Python, tmux, and the required Ollama models.

## **Step 2: Activating the Development Environment (Optional)**

If you are a developer or want to test new features, you can easily set up the testing and dev branches from your stable main branch installation.

1. **Launch micro_X**: Start the application from your main branch installation directory:  
   ./micro_X.sh

2. **Run the Activation Utility**: Inside the running micro_X shell, type the following command:  
   /dev --activate

   This command will automatically:  
   * Clone the testing and dev branches into new subdirectories (micro_X-testing/ and micro_X-dev/).  
   * Run the complete setup process for each new installation.

You will now have three separate, managed installations of micro_X.