## **6\. Developer Mode & Code Integrity**

To enhance reliability and security, micro\_X implements a branch-aware system that adjusts its behavior based on the current Git branch.

### **Purpose**

This system ensures that users running micro\_X from its stable (main) or testing branches are using verified and synchronized code. For developers, it provides a seamless and unrestricted experience on the development (dev) branch.

### **Developer Mode (dev branch)**

* **Activation**: Automatically activated when micro\_X detects it is running from the dev Git branch, or if the Git context is unavailable (e.g., not a Git repository).  
* **Behavior**: In this mode, startup integrity checks are informational or bypassed. micro\_X will run even if there are local uncommitted changes, allowing for active development without interruption.

### **Protected Mode (main and testing branches)**

* **Activation**: Active when micro\_X detects it is running from the main or testing Git branches.  
* **Integrity Checks Performed at Startup**:  
  1. **Clean Working Directory**: Verifies there are no uncommitted modifications to tracked files.  
  2. **Sync with Remote**: Verifies the local branch is synchronized with its remote-tracking branch on origin.  
* **Consequences of Failure**:  
  * If critical integrity issues are found (e.g., uncommitted local changes), micro\_X will display an error message and **halt execution**.  
  * If the local branch is merely behind the remote, a warning will be displayed, and /update will be suggested. micro\_X will continue to run.

### **Behavior on Other Branches**

If you are on a feature branch (not dev, main, or testing), micro\_X assumes a developer-like mode where integrity checks are informational and do not halt execution.