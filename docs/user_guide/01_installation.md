## **1\. Installation and Setup**

Getting started with micro\_X involves cloning the repository and running a unified setup script that handles dependencies for your specific operating system.

### **Step 1: General Setup (All Users)**

For the best experience, all users should start by installing the main branch. This provides the most stable foundation for using micro\_X and for activating the development environment if desired.

1. **Clone the Repository**:  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X

2. **Run the Setup Script**:  
   chmod \+x setup.sh  
   ./setup.sh

   The script will guide you through installing all necessary dependencies for your operating system, including Python, tmux, and the required Ollama models.

### **Step 2: Activating the Development Environment (Optional)**

If you are a developer or want to test new features, you can easily set up the testing and dev branches from your stable main branch installation.

1. **Launch micro\_X**: Start the application from your main branch installation directory:  
   ./micro\_X.sh

2. **Run the Activation Utility**: Inside the running micro\_X shell, type the following command:  
   /dev \--activate

   This command will automatically:  
   * Clone the testing and dev branches into new subdirectories (micro\_X-testing/ and micro\_X-dev/).  
   * Run the complete setup process for each new installation.

You will now have three separate, managed installations of micro\_X.